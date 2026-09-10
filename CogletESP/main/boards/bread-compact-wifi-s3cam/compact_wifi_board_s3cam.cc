#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "esp32_camera.h"
#include "led/led.h"
#include "device_state.h"
#include "mcp_server.h"
#include "uart_component.h"

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

        ESP_LOGW(TAG, "Camera initialized successfully; camera MCP tool is available");
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
