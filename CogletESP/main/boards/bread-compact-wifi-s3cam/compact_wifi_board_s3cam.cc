#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "esp32_camera.h"
#include "led/led.h"
#include "device_state.h"
#include "mcp_server.h"
#include "coglet_reminder.h"
#include "uart_component.h"
#if CONFIG_COGLET_MUSIC
#include "coglet_music.h"
#endif

#include <wifi_station.h>
#include <esp_log.h>
#include <driver/gpio.h>
#include <esp_rom_sys.h>
#include <string>

#define TAG "CompactWifiBoardS3Cam"

// CogNog/Coglet V2.2 RED LED:
//   ESP32-S3 GPIO3 -> Q4 gate -> ordinary red LED.
// This is NOT a WS2812.  The gate has a hardware pulldown, and GPIO HIGH
// turns the N-MOSFET on, so the LED is active HIGH.
//
// Production requirement:
//   listening  -> ON
//   every other device state -> OFF
class ListeningStatusLed : public Led {
public:
    explicit ListeningStatusLed(gpio_num_t gpio) : gpio_(gpio) {
        gpio_config_t io = {};
        io.pin_bit_mask = 1ULL << gpio_;
        io.mode = GPIO_MODE_OUTPUT;
        io.pull_up_en = GPIO_PULLUP_DISABLE;
        io.pull_down_en = GPIO_PULLDOWN_DISABLE;
        io.intr_type = GPIO_INTR_DISABLE;
        ESP_ERROR_CHECK(gpio_config(&io));

        // Deterministic power-up state: red LED off.
        gpio_set_level(gpio_, 0);
    }

    void OnStateChanged() override {
        const auto state = Application::GetInstance().GetDeviceState();
        const bool listening = (state == kDeviceStateListening);

        gpio_set_level(gpio_, listening ? 1 : 0);

        ESP_LOGI("ListeningLed",
                 "GPIO%d red LED -> %s (device_state=%d)",
                 static_cast<int>(gpio_),
                 listening ? "ON" : "OFF",
                 static_cast<int>(state));
    }

private:
    gpio_num_t gpio_;
};

// Camera-board logic transplanted from the known-good CogletESP V1.1 board.
// Keep the current board symbol/path so Kconfig/CMake do not need to change.
// IMPORTANT: camera GPIOs come from config.h and are verified against the
// CogletESP V2.2 PCB, rather than reusing V1.1/V2.0 pin assignments.
class CompactWifiBoardS3Cam : public WifiBoard {
private:
    Button boot_button_;
    Esp32Camera* camera_ = nullptr;

    void InitializeCamera() {
        esp_log_level_set("Esp32Camera", ESP_LOG_DEBUG);
        esp_log_level_set("esp_video", ESP_LOG_DEBUG);
        esp_log_level_set("video", ESP_LOG_DEBUG);
        esp_log_level_set("gc0308", ESP_LOG_DEBUG);
        esp_log_level_set("sccb", ESP_LOG_DEBUG);
        esp_log_level_set("sccb_i2c", ESP_LOG_DEBUG);
        esp_log_level_set("i2c.master", ESP_LOG_DEBUG);
        esp_log_level_set("i2c.common", ESP_LOG_DEBUG);

        ESP_LOGW(TAG,
                 "CogletESP V2.2 camera pins: "
                 "D0..D7=%d,%d,%d,%d,%d,%d,%d,%d XCLK=%d PCLK=%d "
                 "VSYNC=%d HREF=%d SCL=%d SDA=%d PWDN=%d RESET=%d",
                 CAMERA_PIN_D0, CAMERA_PIN_D1, CAMERA_PIN_D2, CAMERA_PIN_D3,
                 CAMERA_PIN_D4, CAMERA_PIN_D5, CAMERA_PIN_D6, CAMERA_PIN_D7,
                 CAMERA_PIN_XCLK, CAMERA_PIN_PCLK, CAMERA_PIN_VSYNC,
                 CAMERA_PIN_HREF, CAMERA_PIN_SIOC, CAMERA_PIN_SIOD,
                 CAMERA_PIN_PWDN, CAMERA_PIN_RESET);

        // Before esp_video takes ownership, sample the three externally pulled-up
        // camera control lines. The V2.2 board has pull-ups to LDO_3V3 on CAMSIOC,
        // CAMSIOD and CAMRST. With no internal pull-up enabled here, a healthy
        // powered camera connector should normally read 1/1/1 at idle.
        gpio_reset_pin(CAMERA_PIN_SIOC);
        gpio_set_direction(CAMERA_PIN_SIOC, GPIO_MODE_INPUT);
        gpio_pullup_dis(CAMERA_PIN_SIOC);
        gpio_pulldown_dis(CAMERA_PIN_SIOC);

        gpio_reset_pin(CAMERA_PIN_SIOD);
        gpio_set_direction(CAMERA_PIN_SIOD, GPIO_MODE_INPUT);
        gpio_pullup_dis(CAMERA_PIN_SIOD);
        gpio_pulldown_dis(CAMERA_PIN_SIOD);

        int reset_level = -1;
        if (CAMERA_PIN_RESET != GPIO_NUM_NC) {
            gpio_reset_pin(CAMERA_PIN_RESET);
            gpio_set_direction(CAMERA_PIN_RESET, GPIO_MODE_INPUT);
            gpio_pullup_dis(CAMERA_PIN_RESET);
            gpio_pulldown_dis(CAMERA_PIN_RESET);
        }
        esp_rom_delay_us(1000);
        if (CAMERA_PIN_RESET != GPIO_NUM_NC) {
            reset_level = gpio_get_level(CAMERA_PIN_RESET);
        }
        ESP_LOGW(TAG,
                 "Camera idle levels before esp_video: SCL(GPIO%d)=%d SDA(GPIO%d)=%d RESET(GPIO%d)=%d",
                 CAMERA_PIN_SIOC, gpio_get_level(CAMERA_PIN_SIOC),
                 CAMERA_PIN_SIOD, gpio_get_level(CAMERA_PIN_SIOD),
                 CAMERA_PIN_RESET, reset_level);

        // GPIO39..42 are JTAG-capable/default-debug pins on ESP32-S3.
        // Release them before the DVP peripheral claims them. This is exactly
        // the pattern used by the known-good CogletESP V1.1 board.
        gpio_reset_pin(GPIO_NUM_39);
        gpio_reset_pin(GPIO_NUM_40);
        gpio_reset_pin(GPIO_NUM_41);
        gpio_reset_pin(GPIO_NUM_42);

        static esp_cam_ctlr_dvp_pin_config_t dvp_pin_config = {
            .data_width = CAM_CTLR_DATA_WIDTH_8,
            .data_io = {
                [0] = CAMERA_PIN_D0,
                [1] = CAMERA_PIN_D1,
                [2] = CAMERA_PIN_D2,
                [3] = CAMERA_PIN_D3,
                [4] = CAMERA_PIN_D4,
                [5] = CAMERA_PIN_D5,
                [6] = CAMERA_PIN_D6,
                [7] = CAMERA_PIN_D7,
            },
            .vsync_io = CAMERA_PIN_VSYNC,
            .de_io = CAMERA_PIN_HREF,
            .pclk_io = CAMERA_PIN_PCLK,
            .xclk_io = CAMERA_PIN_XCLK,
        };

        esp_video_init_sccb_config_t sccb_config = {
            .init_sccb = true,
            .i2c_config = {
                .port = 0,
                .scl_pin = CAMERA_PIN_SIOC,
                .sda_pin = CAMERA_PIN_SIOD,
            },
            .freq = 100000,
        };

        esp_video_init_dvp_config_t dvp_config = {
            .sccb_config = sccb_config,
            .reset_pin = CAMERA_PIN_RESET,
            .pwdn_pin = CAMERA_PIN_PWDN,
            .dvp_pin = dvp_pin_config,
            .xclk_freq = XCLK_FREQ_HZ,
        };

        esp_video_init_config_t video_config = {
            .dvp = &dvp_config,
        };

        // Same settling delay as the successful V1.1 implementation.
        esp_rom_delay_us(20000);

        camera_ = new Esp32Camera(video_config);
        if (!camera_->IsInitialized()) {
            ESP_LOGE(TAG,
                     "Camera initialization failed; GetCamera() will return null, "
                     "so self.camera.take_photo will not be registered");
            delete camera_;
            camera_ = nullptr;
            return;
        }

        camera_->SetHMirror(false);
        camera_->SetVFlip(false);

        if (!camera_->SetGc0308FactoryAuto()) {
            ESP_LOGW(TAG, "GC0308 factory automatic controls failed");
        }

        // Preserve the camera pointer/MCP registration, but stop continuous
        // capture until a user actually requests a photo.
        if (!camera_->StopStream()) {
            ESP_LOGW(TAG, "Camera could not enter standby; photo capture remains available");
        }
        ESP_LOGW(TAG, "Camera initialized; camera MCP remains available (standby stream)");
    }

    void InitializeButtons() {
        boot_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() == kDeviceStateStarting && !WifiStation::GetInstance().IsConnected()) {
                ResetWifiConfiguration();
            }
            app.ToggleChatState();
        });
    }

    void SendCogletAction(const char* action) {
        std::string command = "action:";
        command += action;
        uart_send_string(command.c_str());
        ESP_LOGI(TAG, "Coglet MCP action -> RP2040: %s", command.c_str());
    }

    void InitializeTools() {
        auto& mcp_server = McpServer::GetInstance();

        // These are explicit, one-shot body-part actions.  RP2040 owns the
        // three-cycle animation and temporarily overrides Speaking while the
        // requested action is running.
        mcp_server.AddTool(
            "self.coglet.shake_head",
            "当用户明确要求 Coglet 摇摇头、摇头或动动头时调用。每次调用只执行一次三回合摇头动作。",
            PropertyList(),
            [this](const PropertyList&) -> ReturnValue {
                SendCogletAction("shake_head");
                return true;
            }
        );

        mcp_server.AddTool(
            "self.coglet.blink",
            "当用户明确要求 Coglet 眨眨眼、眨眼或眨三下时调用。每次调用只执行一次三回合眨眼动作。",
            PropertyList(),
            [this](const PropertyList&) -> ReturnValue {
                SendCogletAction("blink");
                return true;
            }
        );

        mcp_server.AddTool(
            "self.coglet.move_left_ear",
            "当用户明确要求 Coglet 动动左耳、摇左耳或只动左耳时调用。每次调用只让左耳执行三回合动作。",
            PropertyList(),
            [this](const PropertyList&) -> ReturnValue {
                SendCogletAction("left_ear");
                return true;
            }
        );

        mcp_server.AddTool(
            "self.coglet.move_right_ear",
            "当用户明确要求 Coglet 动动右耳、摇右耳或只动右耳时调用。每次调用只让右耳执行三回合动作。",
            PropertyList(),
            [this](const PropertyList&) -> ReturnValue {
                SendCogletAction("right_ear");
                return true;
            }
        );

        mcp_server.AddTool(
            "self.coglet.move_ears",
            "当用户明确要求 Coglet 动动耳朵、摇摇耳朵或同时动两只耳朵时调用。每次调用让左右耳同时执行三回合动作。",
            PropertyList(),
            [this](const PropertyList&) -> ReturnValue {
                SendCogletAction("ears");
                return true;
            }
        );


        // Coglet Reminder V1: independent of AEC and active after cloud conversation ends.
        mcp_server.AddTool(
            "self.coglet.reminder.get_time",
            "设置任何提醒之前，先调用本工具获取 Coglet 设备的本地时间和时区。\n"
            "再按这个时区计算用户说的今天、明天、后天或者几分钟后的准确日期时间。",
            PropertyList(),
            [](const PropertyList&) -> ReturnValue {
                return CogletReminder::Instance().Now();
            }
        );

        mcp_server.AddTool(
            "self.coglet.reminder.create",
            "创建一次性设备本地提醒。必须先调用 self.coglet.reminder.get_time 获取设备当前本地时间和时区。\n"
            "datetime 必须为设备本地时间 YYYY-MM-DD HH:MM:SS（按 get_time 返回的时区），不能写模糊时间或 UTC 偏移。\n"
            "message 是用户需要提醒的事情。只有本工具返回已保存，才可告诉用户提醒已成功设置。\n"
#if CONFIG_COGLET_REMINDER_SPEAK
            "到点会先播放提醒音，再由 Coglet 开口说出提醒内容，说完自动回到待机。",
#else
            "实验版到点播放提醒音，提醒内容写入日志，不支持任意文字语音朗读。",
#endif
            PropertyList({
                Property("datetime", kPropertyTypeString),
                Property("message", kPropertyTypeString)
            }),
            [](const PropertyList& p) -> ReturnValue {
                return CogletReminder::Instance().Create(
                    p["datetime"].value<std::string>(), p["message"].value<std::string>());
            }
        );

        mcp_server.AddTool(
            "self.coglet.reminder.list",
            "查询 Coglet 内部存储的全部未触发提醒；需要取消时先查找提醒编号。",
            PropertyList(),
            [](const PropertyList&) -> ReturnValue {
                return CogletReminder::Instance().List();
            }
        );

        mcp_server.AddTool(
            "self.coglet.reminder.cancel",
            "按编号取消 Coglet 的一条提醒。取消前优先调用 self.coglet.reminder.list 确认编号。",
            PropertyList({Property("id", kPropertyTypeInteger, 1, 2147483647)}),
            [](const PropertyList& p) -> ReturnValue {
                return CogletReminder::Instance().Cancel(p["id"].value<int>());
            }
        );
#if CONFIG_COGLET_REMINDER_SPEAK
        mcp_server.AddTool(
            "self.coglet.reminder.last_due",
            "当你收到（有提醒到点了）时，必须先调用本工具获取刚到点的提醒内容，"
            "然后只用一句话自然地提醒主人这件事，说完即可，不要追问或展开别的话题。",
            PropertyList(),
            [](const PropertyList&) -> ReturnValue {
                const std::string text = CogletReminder::Instance().LastFiredText();
                if (text.empty()) {
                    return std::string("最近 15 分钟内没有到点的提醒。");
                }
                Application::GetInstance().OnReminderTextDelivered();
                return text + "请用一句话提醒主人。";
            }
        );
        ESP_LOGI(TAG, "Registered 5 Coglet reminder MCP tools");
#else
        ESP_LOGI(TAG, "Registered 4 Coglet reminder MCP tools");
#endif

#if CONFIG_COGLET_DANCE
        std::string dance_desc =
            "Call when the user asks Coglet to dance / groove / move to music. Coglet ends the current "
            "conversation, plays a song and dances to it, then starts talking again by itself.\n"
            "style (built-in ~30 s tracks): mecha = heavy mecha electro, evil = gloomy gothic, "
            "cat = gentle anime cat pop, random = a random built-in track "
            "(use it when the user did not ask for anything specific).\n";
#if CONFIG_COGLET_MUSIC
        if (CogletMusic::Count() > 0) {
            dance_desc += "The user's own songs (pass the exact name as style, or \"mine\" for a random one "
                          "of them when the user asks for their own / custom music):";
            for (size_t i = 0; i < CogletMusic::Count(); ++i) {
                const auto& song = *CogletMusic::At(i);
                dance_desc += std::string(i ? ", " : " ") + "\"" + song.name + "\" (" + song.PresetName() + ")";
            }
            dance_desc += ".\n";
        }
#endif
        dance_desc +=
            "After calling, reply with one very short line only (e.g. \"Watch this!\" / \"看我的！\").\n"
            "When you later receive \"（跳完舞了）\" it means the dance just finished: ask the user, in "
            "one playful sentence, how they liked it.";
        mcp_server.AddTool(
            "self.coglet.dance",
            dance_desc,
            PropertyList({Property("style", kPropertyTypeString, std::string("random"))}),
            [](const PropertyList& p) -> ReturnValue {
                const std::string style = Application::GetInstance().RequestDance(
                    p["style"].value<std::string>());
                if (style.empty()) {
                    return std::string("Coglet is already dancing, try again in a moment.");
                }
                return std::string("Starting the dance now (") + style + "). Reply with one very short "
                       "line only; the conversation ends automatically. When you receive （跳完舞了）, ask "
                       "the user how they liked it.";
            }
        );
        ESP_LOGI(TAG, "Registered Coglet dance MCP tool");
#endif

        ESP_LOGI(TAG, "Registered 5 Coglet motion MCP tools");
    }

public:
    CompactWifiBoardS3Cam() : boot_button_(BOOT_BUTTON_GPIO) {
        // Deliberately do NOT initialize the legacy LCD/SPI/DummyDisplay/LED
        // path from bread-compact-wifi-s3cam. The successful CogletESP V1.1
        // board is camera + audio + button only, and this avoids unrelated GPIO
        // ownership before esp_video starts.
        InitializeButtons();
        InitializeCamera();
        InitializeTools();
    }

    AudioCodec* GetAudioCodec() override {
        static NoAudioCodecSimplex audio_codec(
            AUDIO_INPUT_SAMPLE_RATE,
            AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_SPK_GPIO_BCLK,
            AUDIO_I2S_SPK_GPIO_LRCK,
            AUDIO_I2S_SPK_GPIO_DOUT,
            AUDIO_I2S_MIC_GPIO_SCK,
            AUDIO_I2S_MIC_GPIO_WS,
            AUDIO_I2S_MIC_GPIO_DIN
        );
#if CONFIG_USE_DEVICE_AEC
        // Coglet has no hardware AEC reference path (SPH0645 + MAX98357A on
        // separate I2S ports), so take the reference digitally from the
        // speaker DMA. Runs once, before AudioService starts the codec.
        static const bool aec_reference_ready = [] {
            const bool ok = audio_codec.EnableSoftwareAecReference(
                CONFIG_COGLET_AEC_REF_DELAY_MS * 1000);
            if (!ok) {
                ESP_LOGE(TAG, "Software AEC reference unavailable: running without echo cancellation");
            }
            return ok;
        }();
        (void)aec_reference_ready;
#endif
        return &audio_codec;
    }

    Camera* GetCamera() override {
        return camera_;
    }

    Led* GetLed() override {
        static ListeningStatusLed led(BUILTIN_LED_GPIO);
        return &led;
    }

    // No LCD override: Board default provides NoDisplay.
};

DECLARE_BOARD(CompactWifiBoardS3Cam);
