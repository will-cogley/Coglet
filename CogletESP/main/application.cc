#include "application.h"
#include "board.h"
#include "display.h"
#include "system_info.h"
#include "audio_codec.h"
#include "mqtt_protocol.h"
#include "websocket_protocol.h"
#include "assets/lang_config.h"
#include "mcp_server.h"
#include "assets.h"
#include "settings.h"
#include "coglet_reminder.h"
#include "coglet_sounds.h"

#include <cstring>
#include <algorithm>
#include <esp_log.h>
#include <cJSON.h>
#include <driver/gpio.h>
#include <arpa/inet.h>
#include <font_awesome.h>
#include <uart_component.h>

#define TAG "Application"
#define AUTO_AWAKE_TAG "CogletAutoAwake"

namespace {
// V1: keep this enabled for the clean, no-chime Auto-Awake build.
constexpr bool kAutoAwakeOnBoot = true;
constexpr int kAutoAwakeBootDelayTicks = 4;  // Keep the existing startup sound guard.
constexpr int kAutoAwakePrepareSettleTicks = 2;  // Separate AFE allocation from UDP setup.
// After a physical wake word no boot sound is playing; still use the same
// prepare -> settle -> channel order, with a short initial debounce stage.
constexpr int kManualWakeInitialTicks = 1;
constexpr int kWakeAudioBurstLimit = 2;
constexpr int kWakeAudioPaceMs = 65;  // Opus frame is 60 ms; avoid flooding a new UDP socket.
constexpr int kAudioSendBackoffMs[] = {120, 240, 400};  // Bounded, no task sleeps.
constexpr int kAudioSendBurstLimit = 2;  // Do not burst an entire queued backlog into Wi-Fi.
} // namespace


static const char* const STATE_STRINGS[] = {
    "unknown",
    "starting",
    "configuring",
    "idle",
    "connecting",
    "listening",
    "speaking",
    "upgrading",
    "activating",
    "audio_testing",
    "fatal_error",
    "invalid_state"
};

Application::Application() {
    event_group_ = xEventGroupCreate();

#if CONFIG_USE_DEVICE_AEC && CONFIG_USE_SERVER_AEC
#error "CONFIG_USE_DEVICE_AEC and CONFIG_USE_SERVER_AEC cannot be enabled at the same time"
#elif CONFIG_USE_DEVICE_AEC
    aec_mode_ = kAecOnDeviceSide;
#elif CONFIG_USE_SERVER_AEC
    aec_mode_ = kAecOnServerSide;
#else
    aec_mode_ = kAecOff;
#endif

    esp_timer_create_args_t clock_timer_args = {
        .callback = [](void* arg) {
            Application* app = (Application*)arg;
            xEventGroupSetBits(app->event_group_, MAIN_EVENT_CLOCK_TICK);
        },
        .arg = this,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "clock_timer",
        .skip_unhandled_events = true
    };
    esp_timer_create(&clock_timer_args, &clock_timer_handle_);
}

Application::~Application() {
    if (clock_timer_handle_ != nullptr) {
        esp_timer_stop(clock_timer_handle_);
        esp_timer_delete(clock_timer_handle_);
    }
    vEventGroupDelete(event_group_);
}

void Application::CheckAssetsVersion() {
    auto& board = Board::GetInstance();
    auto display = board.GetDisplay();
    auto& assets = Assets::GetInstance();

    if (!assets.partition_valid()) {
        ESP_LOGW(TAG, "Assets partition is disabled for board %s", BOARD_NAME);
        return;
    }
    
    Settings settings("assets", true);
    // Check if there is a new assets need to be downloaded
    std::string download_url = settings.GetString("download_url");

    if (!download_url.empty()) {
        settings.EraseKey("download_url");

        char message[256];
        snprintf(message, sizeof(message), Lang::Strings::FOUND_NEW_ASSETS, download_url.c_str());
        Alert(Lang::Strings::LOADING_ASSETS, message, "cloud_arrow_down", Lang::Sounds::OGG_UPGRADE);
        
        // Wait for the audio service to be idle for 3 seconds
        vTaskDelay(pdMS_TO_TICKS(3000));
        SetDeviceState(kDeviceStateUpgrading);
        board.SetPowerSaveMode(false);
        display->SetChatMessage("system", Lang::Strings::PLEASE_WAIT);

        bool success = assets.Download(download_url, [display](int progress, size_t speed) -> void {
            std::thread([display, progress, speed]() {
                char buffer[32];
                snprintf(buffer, sizeof(buffer), "%d%% %uKB/s", progress, speed / 1024);
                display->SetChatMessage("system", buffer);
            }).detach();
        });

        board.SetPowerSaveMode(true);
        vTaskDelay(pdMS_TO_TICKS(1000));

        if (!success) {
            Alert(Lang::Strings::ERROR, Lang::Strings::DOWNLOAD_ASSETS_FAILED, "circle_xmark", Lang::Sounds::OGG_EXCLAMATION);
            vTaskDelay(pdMS_TO_TICKS(2000));
            return;
        }
    }

    // Apply assets
    assets.Apply();
    display->SetChatMessage("system", "");
    display->SetEmotion("microchip_ai");
    uart_send_string("configuring");
}

void Application::CheckNewVersion(Ota& ota) {
    const int MAX_RETRY = 10;
    int retry_count = 0;
    int retry_delay = 10; // 初始重试延迟为10秒

    auto& board = Board::GetInstance();
    while (true) {
        SetDeviceState(kDeviceStateActivating);
        auto display = board.GetDisplay();
        display->SetStatus(Lang::Strings::CHECKING_NEW_VERSION);

        esp_err_t err = ota.CheckVersion();
        if (err != ESP_OK) {
            retry_count++;
            if (retry_count >= MAX_RETRY) {
                ESP_LOGE(TAG, "Too many retries, exit version check");
                return;
            }

            char error_message[128];
            snprintf(error_message, sizeof(error_message), "code=%d, url=%s", err, ota.GetCheckVersionUrl().c_str());
            char buffer[256];
            snprintf(buffer, sizeof(buffer), Lang::Strings::CHECK_NEW_VERSION_FAILED, retry_delay, error_message);
            Alert(Lang::Strings::ERROR, buffer, "cloud_slash", Lang::Sounds::OGG_EXCLAMATION);

            ESP_LOGW(TAG, "Check new version failed, retry in %d seconds (%d/%d)", retry_delay, retry_count, MAX_RETRY);
            for (int i = 0; i < retry_delay; i++) {
                vTaskDelay(pdMS_TO_TICKS(1000));
                if (device_state_ == kDeviceStateIdle) {
                    break;
                }
            }
            retry_delay *= 2; // 每次重试后延迟时间翻倍
            continue;
        }
        retry_count = 0;
        retry_delay = 10; // 重置重试延迟时间

        if (ota.HasNewVersion()) {
            if (UpgradeFirmware(ota)) {
                return; // This line will never be reached after reboot
            }
            // If upgrade failed, continue to normal operation (don't break, just fall through)
        }

        // No new version, mark the current version as valid
        ota.MarkCurrentVersionValid();
        if (!ota.HasActivationCode() && !ota.HasActivationChallenge()) {
            xEventGroupSetBits(event_group_, MAIN_EVENT_CHECK_NEW_VERSION_DONE);
            // Exit the loop if done checking new version
            break;
        }

        display->SetStatus(Lang::Strings::ACTIVATION);
        // Activation code is shown to the user and waiting for the user to input
        if (ota.HasActivationCode()) {
            ShowActivationCode(ota.GetActivationCode(), ota.GetActivationMessage());
        }

        // This will block the loop until the activation is done or timeout
        for (int i = 0; i < 10; ++i) {
            ESP_LOGI(TAG, "Activating... %d/%d", i + 1, 10);
            esp_err_t err = ota.Activate();
            if (err == ESP_OK) {
                xEventGroupSetBits(event_group_, MAIN_EVENT_CHECK_NEW_VERSION_DONE);
                break;
            } else if (err == ESP_ERR_TIMEOUT) {
                vTaskDelay(pdMS_TO_TICKS(3000));
            } else {
                vTaskDelay(pdMS_TO_TICKS(10000));
            }
            if (device_state_ == kDeviceStateIdle) {
                break;
            }
        }
    }
}

void Application::ShowActivationCode(const std::string& code, const std::string& message) {
    struct digit_sound {
        char digit;
        const std::string_view& sound;
    };
    static const std::array<digit_sound, 10> digit_sounds{{
        digit_sound{'0', Lang::Sounds::OGG_0},
        digit_sound{'1', Lang::Sounds::OGG_1}, 
        digit_sound{'2', Lang::Sounds::OGG_2},
        digit_sound{'3', Lang::Sounds::OGG_3},
        digit_sound{'4', Lang::Sounds::OGG_4},
        digit_sound{'5', Lang::Sounds::OGG_5},
        digit_sound{'6', Lang::Sounds::OGG_6},
        digit_sound{'7', Lang::Sounds::OGG_7},
        digit_sound{'8', Lang::Sounds::OGG_8},
        digit_sound{'9', Lang::Sounds::OGG_9}
    }};

    // This sentence uses 9KB of SRAM, so we need to wait for it to finish
    Alert(Lang::Strings::ACTIVATION, message.c_str(), "link", Lang::Sounds::OGG_ACTIVATION);

    for (const auto& digit : code) {
        auto it = std::find_if(digit_sounds.begin(), digit_sounds.end(),
            [digit](const digit_sound& ds) { return ds.digit == digit; });
        if (it != digit_sounds.end()) {
            audio_service_.PlaySound(it->sound);
        }
    }
}

void Application::Alert(const char* status, const char* message, const char* emotion, const std::string_view& sound) {
    ESP_LOGW(TAG, "Alert [%s] %s: %s", emotion, status, message);
    auto display = Board::GetInstance().GetDisplay();
    display->SetStatus(status);
    display->SetEmotion(emotion);
    uart_send_string(emotion);
    display->SetChatMessage("system", message);
    if (!sound.empty()) {
        audio_service_.PlaySound(sound);
    }
}

void Application::DismissAlert() {
    if (device_state_ == kDeviceStateIdle) {
        auto display = Board::GetInstance().GetDisplay();
        display->SetStatus(Lang::Strings::STANDBY);
        display->SetEmotion("neutral");
        uart_send_string("idle");
        display->SetChatMessage("system", "");
    }
}

void Application::ToggleChatState() {
    if (device_state_ == kDeviceStateActivating) {
        SetDeviceState(kDeviceStateIdle);
        return;
    } else if (device_state_ == kDeviceStateWifiConfiguring) {
        audio_service_.EnableAudioTesting(true);
        SetDeviceState(kDeviceStateAudioTesting);
        return;
    } else if (device_state_ == kDeviceStateAudioTesting) {
        audio_service_.EnableAudioTesting(false);
        SetDeviceState(kDeviceStateWifiConfiguring);
        return;
    }

    if (!protocol_) {
        ESP_LOGE(TAG, "Protocol not initialized");
        return;
    }

    if (device_state_ == kDeviceStateIdle) {
        Schedule([this]() {
            // Buttons follow the same AFE -> settle -> UDP path as wake words.
            BeginStaggeredWake("", false,
                aec_mode_ == kAecOff ? kListeningModeAutoStop : kListeningModeRealtime,
                false);
        });
    } else if (device_state_ == kDeviceStateSpeaking) {
        Schedule([this]() {
            AbortSpeaking(kAbortReasonNone);
        });
    } else if (device_state_ == kDeviceStateListening) {
        Schedule([this]() {
            protocol_->CloseAudioChannel();
        });
    }
}

void Application::StartListening() {
    if (device_state_ == kDeviceStateActivating) {
        SetDeviceState(kDeviceStateIdle);
        return;
    } else if (device_state_ == kDeviceStateWifiConfiguring) {
        audio_service_.EnableAudioTesting(true);
        SetDeviceState(kDeviceStateAudioTesting);
        return;
    }

    if (!protocol_) {
        ESP_LOGE(TAG, "Protocol not initialized");
        return;
    }
    
    if (device_state_ == kDeviceStateIdle) {
        Schedule([this]() {
            BeginStaggeredWake("", false, kListeningModeManualStop, false);
        });
    } else if (device_state_ == kDeviceStateSpeaking) {
        Schedule([this]() {
            AbortSpeaking(kAbortReasonNone);
            SetListeningMode(kListeningModeManualStop);
        });
    }
}

void Application::StopListening() {
    if (device_state_ == kDeviceStateAudioTesting) {
        audio_service_.EnableAudioTesting(false);
        SetDeviceState(kDeviceStateWifiConfiguring);
        return;
    }

    const std::array<int, 3> valid_states = {
        kDeviceStateListening,
        kDeviceStateSpeaking,
        kDeviceStateIdle,
    };
    // If not valid, do nothing
    if (std::find(valid_states.begin(), valid_states.end(), device_state_) == valid_states.end()) {
        return;
    }

    Schedule([this]() {
        if (device_state_ == kDeviceStateListening) {
            protocol_->SendStopListening();
            SetDeviceState(kDeviceStateIdle);
        }
    });
}

void Application::Start() {
    auto& board = Board::GetInstance();
    SetDeviceState(kDeviceStateStarting);

    /* Setup the display */
    auto display = board.GetDisplay();

    // Print board name/version info
    display->SetChatMessage("system", SystemInfo::GetUserAgent().c_str());

    /* Setup the audio service */
    auto codec = board.GetAudioCodec();
    audio_service_.Initialize(codec);
    audio_service_.Start();

    AudioServiceCallbacks callbacks;
    callbacks.on_send_queue_available = [this]() {
        xEventGroupSetBits(event_group_, MAIN_EVENT_SEND_AUDIO);
    };
    callbacks.on_wake_word_detected = [this](const std::string& wake_word) {
        xEventGroupSetBits(event_group_, MAIN_EVENT_WAKE_WORD_DETECTED);
    };
    callbacks.on_vad_change = [this](bool speaking) {
        xEventGroupSetBits(event_group_, MAIN_EVENT_VAD_CHANGE);
    };
    audio_service_.SetCallbacks(callbacks);

    // Start the main event loop task with priority 3
    xTaskCreate([](void* arg) {
        ((Application*)arg)->MainEventLoop();
        vTaskDelete(NULL);
    }, "main_event_loop", 2048 * 4, this, 3, &main_event_loop_task_handle_);

    /* Start the clock timer to update the status bar */
    esp_timer_start_periodic(clock_timer_handle_, 1000000);

    /* Wait for the network to be ready */
    board.StartNetwork();

    // Update the status bar immediately to show the network state
    display->UpdateStatusBar(true);

    // Check for new assets version
    CheckAssetsVersion();

    // Check for new firmware version or get the MQTT broker address
    Ota ota;
    CheckNewVersion(ota);

    // Initialize the protocol
    display->SetStatus(Lang::Strings::LOADING_PROTOCOL);

    // Add MCP common tools before initializing the protocol
    auto& mcp_server = McpServer::GetInstance();
    mcp_server.AddCommonTools();
    mcp_server.AddUserOnlyTools();

    if (ota.HasMqttConfig()) {
        protocol_ = std::make_unique<MqttProtocol>();
    } else if (ota.HasWebsocketConfig()) {
        protocol_ = std::make_unique<WebsocketProtocol>();
    } else {
        ESP_LOGW(TAG, "No protocol specified in the OTA config, using MQTT");
        protocol_ = std::make_unique<MqttProtocol>();
    }

    protocol_->OnConnected([this]() {
        DismissAlert();
    });

    protocol_->OnNetworkError([this](const std::string& message) {
        last_error_message_ = message;
        xEventGroupSetBits(event_group_, MAIN_EVENT_ERROR);
    });
    protocol_->OnIncomingAudio([this](std::unique_ptr<AudioStreamPacket> packet) {
        if (device_state_ == kDeviceStateSpeaking) {
            audio_service_.PushPacketToDecodeQueue(std::move(packet));
        }
    });
    protocol_->OnAudioChannelOpened([this, codec, &board]() {
        board.SetPowerSaveMode(false);
        if (protocol_->server_sample_rate() != codec->output_sample_rate()) {
            ESP_LOGW(TAG, "Server sample rate %d does not match device output sample rate %d, resampling may cause distortion",
                protocol_->server_sample_rate(), codec->output_sample_rate());
        }
    });
    protocol_->OnAudioChannelClosed([this, &board]() {
        board.SetPowerSaveMode(true);
        Schedule([this]() {
            auto display = Board::GetInstance().GetDisplay();
            display->SetChatMessage("system", "");
            SetDeviceState(kDeviceStateIdle);
            // The server and its LLM decide whether and when to close the
            // session (including a native protocol goodbye). Once closed,
            // boot Auto-Awake never restarts without a fresh user wake.
            auto_awake_boot_pending_ = false;
            auto_awake_sleep_latched_ = true;
            ESP_LOGI(AUTO_AWAKE_TAG, "CHANNEL_CLOSED: waiting for wake word / button");
        });
    });
    protocol_->OnIncomingJson([this, display](const cJSON* root) {
        // Parse JSON data
        auto type = cJSON_GetObjectItem(root, "type");
        if (strcmp(type->valuestring, "tts") == 0) {
            auto state = cJSON_GetObjectItem(root, "state");
            if (strcmp(state->valuestring, "start") == 0) {
                Schedule([this]() {
                    if (auto_awake_sleep_latched_) return;  // Ignore late TTS after sleep.
                    aborted_ = false;
                    if (device_state_ == kDeviceStateIdle || device_state_ == kDeviceStateListening) {
                        SetDeviceState(kDeviceStateSpeaking);
                    }
                });
            } else if (strcmp(state->valuestring, "stop") == 0) {
                Schedule([this]() {
                    if (reminder_session_active_) {
                        reminder_last_tts_stop_us_ = esp_timer_get_time();
                        if (reminder_text_delivered_) {
                            // The reminder has been said: return to idle once
                            // the last audio has finished playing.
                            reminder_close_after_playback_ = true;
                        }
                    }
                    if (auto_awake_sleep_latched_) return;
                    if (device_state_ == kDeviceStateSpeaking) {
                        if (listening_mode_ == kListeningModeManualStop) {
                            SetDeviceState(kDeviceStateIdle);
                        } else {
                            SetDeviceState(kDeviceStateListening);
                        }
                    }
                });
            } else if (strcmp(state->valuestring, "sentence_start") == 0) {
                auto text = cJSON_GetObjectItem(root, "text");
                if (cJSON_IsString(text)) {
                    ESP_LOGI(TAG, "<< %s", text->valuestring);
                    Schedule([this, display, message = std::string(text->valuestring)]() {
                        if (!auto_awake_sleep_latched_) {
                            display->SetChatMessage("assistant", message.c_str());
                        }
                    });
                }
            }
        } else if (strcmp(type->valuestring, "stt") == 0) {
            auto text = cJSON_GetObjectItem(root, "text");
            if (cJSON_IsString(text)) {
                ESP_LOGI(TAG, ">> %s", text->valuestring);
                Schedule([display, message = std::string(text->valuestring)]() {
                    // The cloud's existing language model handles conversational
                    // intent. Device code does not classify farewell phrases.
                    display->SetChatMessage("user", message.c_str());
                });
            }
        } else if (strcmp(type->valuestring, "llm") == 0) {
            auto emotion = cJSON_GetObjectItem(root, "emotion");
            if (cJSON_IsString(emotion)) {
                Schedule([this, display, emotion_str = std::string(emotion->valuestring)]() {
                    display->SetEmotion(emotion_str.c_str());
                    uart_send_string(emotion_str.c_str());
                });
            }
        } else if (strcmp(type->valuestring, "mcp") == 0) {
            auto payload = cJSON_GetObjectItem(root, "payload");
            if (cJSON_IsObject(payload)) {
                McpServer::GetInstance().ParseMessage(payload);
            }
        } else if (strcmp(type->valuestring, "system") == 0) {
            auto command = cJSON_GetObjectItem(root, "command");
            if (cJSON_IsString(command)) {
                ESP_LOGI(TAG, "System command: %s", command->valuestring);
                if (strcmp(command->valuestring, "reboot") == 0) {
                    // Do a reboot if user requests a OTA update
                    Schedule([this]() {
                        Reboot();
                    });
                } else {
                    ESP_LOGW(TAG, "Unknown system command: %s", command->valuestring);
                }
            }
        } else if (strcmp(type->valuestring, "alert") == 0) {
            auto status = cJSON_GetObjectItem(root, "status");
            auto message = cJSON_GetObjectItem(root, "message");
            auto emotion = cJSON_GetObjectItem(root, "emotion");
            if (cJSON_IsString(status) && cJSON_IsString(message) && cJSON_IsString(emotion)) {
                Alert(status->valuestring, message->valuestring, emotion->valuestring, Lang::Sounds::OGG_VIBRATION);
            } else {
                ESP_LOGW(TAG, "Alert command requires status, message and emotion");
            }
#if CONFIG_RECEIVE_CUSTOM_MESSAGE
        } else if (strcmp(type->valuestring, "custom") == 0) {
            auto payload = cJSON_GetObjectItem(root, "payload");
            ESP_LOGI(TAG, "Received custom message: %s", cJSON_PrintUnformatted(root));
            if (cJSON_IsObject(payload)) {
                Schedule([this, display, payload_str = std::string(cJSON_PrintUnformatted(payload))]() {
                    display->SetChatMessage("system", payload_str.c_str());
                });
            } else {
                ESP_LOGW(TAG, "Invalid custom message format: missing payload");
            }
#endif
        } else {
            ESP_LOGW(TAG, "Unknown message type: %s", type->valuestring);
        }
    });
    bool protocol_started = protocol_->Start();

    SystemInfo::PrintHeapStats();
    SetDeviceState(kDeviceStateIdle);

    has_server_time_ = ota.HasServerTime();
    if (protocol_started) {
        std::string message = std::string(Lang::Strings::VERSION) + ota.GetCurrentVersion();
        display->ShowNotification(message.c_str());
        display->SetChatMessage("system", "");
        // Play the Menuconfig-selected startup sound before boot Auto-Awake.
        ESP_LOGI("CogletSounds", "PLAY startup=%s", CogletSounds::BootName());
        audio_service_.PlaySound(CogletSounds::Boot());
        if (kAutoAwakeOnBoot) {
            Schedule([this]() {
                auto_awake_boot_pending_ = true;
                auto_awake_boot_delay_ticks_ = kAutoAwakeBootDelayTicks;
                ESP_LOGI(AUTO_AWAKE_TAG, "BOOT_ARMED: waiting for ready sound");
            });
        }
    }
}

// Add a async task to MainLoop
void Application::Schedule(std::function<void()> callback) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        main_tasks_.push_back(std::move(callback));
    }
    xEventGroupSetBits(event_group_, MAIN_EVENT_SCHEDULE);
}

// The Main Event Loop controls the chat state and websocket connection
// If other tasks need to access the websocket or chat state,
// they should use Schedule to call this function
void Application::MainEventLoop() {
    while (true) {
        auto bits = xEventGroupWaitBits(event_group_, MAIN_EVENT_SCHEDULE |
            MAIN_EVENT_SEND_AUDIO |
            MAIN_EVENT_WAKE_WORD_DETECTED |
            MAIN_EVENT_VAD_CHANGE |
            MAIN_EVENT_CLOCK_TICK |
            MAIN_EVENT_ERROR, pdTRUE, pdFALSE,
            wake_session_stage_ == WakeSessionStage::Upload ? pdMS_TO_TICKS(kWakeAudioPaceMs) : portMAX_DELAY);

        if (bits & MAIN_EVENT_ERROR) {
            // Failure must fall back to local wake word, not an endless retry.
            auto_awake_boot_pending_ = false;
            auto_awake_sleep_latched_ = true;
            ESP_LOGW(AUTO_AWAKE_TAG, "NETWORK_ERROR: manual wake required");
            SetDeviceState(kDeviceStateIdle);
            Alert(Lang::Strings::ERROR, last_error_message_.c_str(), "circle_xmark", Lang::Sounds::OGG_EXCLAMATION);
        }

        if (bits & MAIN_EVENT_SEND_AUDIO) {
            // Audio callbacks arrive every ~60 ms. Avoid retrying a congested UDP
            // socket at that rate, but never stall the main event loop or queue
            // old speech for later playback at the server.
            const bool uplink_active = device_state_ == kDeviceStateListening ||
                (device_state_ == kDeviceStateSpeaking && listening_mode_ == kListeningModeRealtime);
            if (uplink_active && protocol_ &&
                esp_timer_get_time() >= audio_send_retry_after_us_) {
                for (int sent = 0; sent < kAudioSendBurstLimit; ++sent) {
                    auto packet = audio_service_.PopPacketFromSendQueue();
                    if (!packet) {
                        break;
                    }
                    if (!protocol_->SendAudio(std::move(packet))) {
                        if (audio_send_failure_streak_ < 3) {
                            ++audio_send_failure_streak_;
                        }
                        const int delay_ms = kAudioSendBackoffMs[audio_send_failure_streak_ - 1];
                        audio_send_retry_after_us_ = esp_timer_get_time() +
                            static_cast<int64_t>(delay_ms) * 1000;
                        break;
                    }
                    audio_send_failure_streak_ = 0;
                    audio_send_retry_after_us_ = 0;
                }
            }
        }

        if (bits & MAIN_EVENT_WAKE_WORD_DETECTED) {
            OnWakeWordDetected();
        }

        if (bits & MAIN_EVENT_VAD_CHANGE) {
            if (device_state_ == kDeviceStateListening) {
                auto led = Board::GetInstance().GetLed();
                led->OnStateChanged();
            }
        }

        if (bits & MAIN_EVENT_SCHEDULE) {
            std::unique_lock<std::mutex> lock(mutex_);
            auto tasks = std::move(main_tasks_);
            lock.unlock();
            for (auto& task : tasks) {
                task();
            }
        }

        if (wake_session_stage_ == WakeSessionStage::Upload) {
            PumpStaggeredWakePackets();
        }

        if (bits & MAIN_EVENT_CLOCK_TICK) {
            // Reminder is independent of the cloud voice session. An alarm
            // takes priority over automatic listening or a spoken reply.
            if (CogletReminder::Instance().HasDue() &&
                (device_state_ == kDeviceStateSpeaking ||
                 device_state_ == kDeviceStateListening ||
                 device_state_ == kDeviceStateConnecting)) {
                ESP_LOGW("CogletReminder", "Due during voice session: closing audio channel");
                auto_awake_boot_pending_ = false;
                auto_awake_sleep_latched_ = true;
                if (protocol_ && protocol_->IsAudioChannelOpened()) {
                    protocol_->CloseAudioChannel();
                }
                audio_service_.ResetDecoder();
                SetDeviceState(kDeviceStateIdle);
            }
            if (device_state_ == kDeviceStateIdle) {
                auto display = Board::GetInstance().GetDisplay();
                for (const auto& alarm : CogletReminder::Instance().TakeDueIfIdle()) {
                    ESP_LOGW("CogletReminder", "FIRE id=%lu due=%s message=%s",
                             (unsigned long)alarm.id, alarm.datetime.c_str(), alarm.message.c_str());
                    display->ShowNotification(("提醒：" + alarm.message).c_str());
                    ESP_LOGI("CogletSounds", "PLAY reminder=%s", CogletSounds::ReminderName());
                    audio_service_.PlaySound(CogletSounds::Reminder());
#if CONFIG_COGLET_REMINDER_SPEAK
                    // After the chime Coglet says the reminder out loud.
                    reminder_speech_pending_ = true;
                    reminder_speech_deadline_us_ = esp_timer_get_time() + 5LL * 60 * 1000000;
#endif
                }
            }
            UpdateReminderSpeech();
            // Manual wakes get the same AFE-before-UDP staging every time,
            // not just the first wake after cold boot.
            AdvanceStaggeredWakeTick();
            if (auto_awake_boot_pending_ && device_state_ == kDeviceStateIdle &&
                !auto_awake_sleep_latched_) {
                if (auto_awake_boot_delay_ticks_ > 0) {
                    --auto_awake_boot_delay_ticks_;
                } else if (audio_service_.IsIdle()) {
                    if (!auto_awake_processor_prepared_) {
                        // AFE/model memory allocation can be large. Prepare it
                        // while no UDP audio channel exists, then let Wi-Fi and
                        // the allocator settle before the one-shot boot session.
                        audio_service_.PrepareVoiceProcessing();
                        auto_awake_processor_prepared_ = true;
                        auto_awake_boot_delay_ticks_ = kAutoAwakePrepareSettleTicks;
                        ESP_LOGI(AUTO_AWAKE_TAG, "BOOT_PREPARED: delaying UDP session setup");
                    } else {
                        auto_awake_boot_pending_ = false;  // Boot attempts exactly once.
                        StartAutoAwakeSession("BOOT");
                    }
                }
            }
            clock_ticks_++;
            auto display = Board::GetInstance().GetDisplay();
            display->UpdateStatusBar();
        
            // Print the debug info every 10 seconds
            if (clock_ticks_ % 10 == 0) {
                // SystemInfo::PrintTaskCpuUsage(pdMS_TO_TICKS(1000));
                // SystemInfo::PrintTaskList();
                SystemInfo::PrintHeapStats();
            }
        }
    }
}

bool Application::StartAutoAwakeSession(const char* reason) {
    if (!protocol_ || device_state_ != kDeviceStateIdle || auto_awake_sleep_latched_) {
        return false;
    }
    ESP_LOGI(AUTO_AWAKE_TAG, "%s: opening audio channel", reason);
    SetDeviceState(kDeviceStateConnecting);
    if (!protocol_->OpenAudioChannel()) {
        ESP_LOGW(AUTO_AWAKE_TAG, "%s_FAILED: returning to wake word standby", reason);
        auto_awake_sleep_latched_ = true;
        SetDeviceState(kDeviceStateIdle);
        return false;
    }
    // Without AEC the boot session reuses native VAD (auto-stop). With device
    // AEC it uses realtime mode like every other wake path, so the first
    // conversation after boot can be interrupted too.
    const ListeningMode mode = aec_mode_ == kAecOff ? kListeningModeAutoStop : kListeningModeRealtime;
    SetListeningMode(mode);
    ESP_LOGI(AUTO_AWAKE_TAG, "%s_LISTENING: mode=%s", reason,
             mode == kListeningModeRealtime ? "realtime" : "auto");
    return true;
}

// LOCAL wake path is deliberately different from the boot Auto-Awake path:
// wait until the processor is ready, give the allocator a settling interval,
// open UDP only then, and upload historical wake audio at a measured pace.
// There is no main-event-loop sleep and no change to the MCP protocol.
void Application::CancelStaggeredWake() {
    wake_session_stage_ = WakeSessionStage::None;
    wake_session_delay_ticks_ = 0;
    wake_session_packets_.clear();
    wake_session_word_.clear();
    wake_session_send_data_ = false;
    wake_session_popup_ = false;
    wake_session_next_send_us_ = 0;
    wake_session_failure_streak_ = 0;
    wake_session_proactive_ = false;
}

bool Application::StartDeviceSession(const std::string& context_text) {
    if (!protocol_ || device_state_ != kDeviceStateIdle ||
        wake_session_stage_ != WakeSessionStage::None) {
        ESP_LOGW(AUTO_AWAKE_TAG, "PROACTIVE_SKIPPED: state=%s stage=%d",
                 STATE_STRINGS[device_state_], static_cast<int>(wake_session_stage_));
        return false;
    }
    // No cached wake audio (send_data=false) and no popup: Coglet speaks first.
    BeginStaggeredWake(context_text, false,
                       aec_mode_ == kAecOff ? kListeningModeAutoStop : kListeningModeRealtime,
                       false);
    if (wake_session_stage_ != WakeSessionStage::Prepare) {
        ESP_LOGW(AUTO_AWAKE_TAG, "PROACTIVE_SKIPPED: staged wake did not start");
        return false;
    }
    wake_session_proactive_ = true;
    ESP_LOGW(AUTO_AWAKE_TAG, "PROACTIVE_START: text=%s", context_text.c_str());
    return true;
}

void Application::BeginStaggeredWake(const std::string& word, bool send_data,
                                     ListeningMode mode, bool play_popup) {
    if (!protocol_ || device_state_ != kDeviceStateIdle ||
        wake_session_stage_ != WakeSessionStage::None) return;
    auto_awake_boot_pending_ = false;  // User wake overrides pending auto-start.
    auto_awake_sleep_latched_ = false;
    wake_session_word_ = word;
    wake_session_send_data_ = send_data;
    wake_session_mode_ = mode;
    wake_session_popup_ = play_popup;
    if (send_data) audio_service_.EncodeWakeWord();
    audio_service_.EnableWakeWordDetection(false); // Suppress duplicate triggers.
    wake_session_stage_ = WakeSessionStage::Prepare;
    wake_session_delay_ticks_ = kManualWakeInitialTicks;
    SetDeviceState(kDeviceStateConnecting);
    ESP_LOGI(AUTO_AWAKE_TAG, "LOCAL_WAKE_STAGE: prepare word=%s", word.c_str());
}

void Application::CloseReminderSession(const char* reason) {
    ESP_LOGW("CogletReminder", "SPEECH_DONE (%s): closing session -> idle", reason);
    reminder_session_active_ = false;
    reminder_close_after_playback_ = false;
    if (protocol_ && protocol_->IsAudioChannelOpened()) {
        protocol_->CloseAudioChannel();   // OnAudioChannelClosed -> idle
    } else {
        SetDeviceState(kDeviceStateIdle);
    }
}

// Called on the 1-second clock tick.
void Application::UpdateReminderSpeech() {
#if CONFIG_COGLET_REMINDER_SPEAK
    static constexpr const char* kReminderCue = "（有提醒到点了）";  // <= 13 chars for xiaozhi.me
    const int64_t now = esp_timer_get_time();

    if (reminder_session_active_) {
        const bool channel_open = protocol_ && protocol_->IsAudioChannelOpened();
        if (device_state_ == kDeviceStateIdle && wake_session_stage_ == WakeSessionStage::None &&
            !channel_open) {
            // Session ended by itself (server goodbye, open failure, user button).
            reminder_session_active_ = false;
            reminder_close_after_playback_ = false;
            return;
        }
        if (reminder_close_after_playback_ && audio_service_.IsIdle() &&
            device_state_ != kDeviceStateSpeaking) {
            CloseReminderSession("reminder spoken");
        } else if (!reminder_text_delivered_ && reminder_last_tts_stop_us_ > 0 &&
                   now - reminder_last_tts_stop_us_ > 8LL * 1000000 &&
                   audio_service_.IsIdle() && device_state_ != kDeviceStateSpeaking) {
            // The LLM answered without fetching the text: don't hang around.
            CloseReminderSession("answered without last_due");
        } else if (now - reminder_session_started_us_ > 45LL * 1000000) {
            CloseReminderSession("safety timeout");
        }
        return;
    }

    if (!reminder_speech_pending_) {
        return;
    }
    if (now > reminder_speech_deadline_us_) {
        reminder_speech_pending_ = false;
        ESP_LOGW("CogletReminder", "SPEECH_SKIPPED: device stayed busy");
        return;
    }
    const bool ready = protocol_ != nullptr && device_state_ == kDeviceStateIdle &&
                       wake_session_stage_ == WakeSessionStage::None &&
                       !auto_awake_boot_pending_ && audio_service_.IsIdle();  // chime finished
    if (!ready) {
        return;
    }
    reminder_text_delivered_ = false;
    if (StartDeviceSession(kReminderCue)) {
        reminder_speech_pending_ = false;
        reminder_session_active_ = true;
        reminder_session_started_us_ = now;
        reminder_last_tts_stop_us_ = 0;
        reminder_close_after_playback_ = false;
        ESP_LOGW("CogletReminder", "SPEECH_START: opening session to say the reminder");
    }
#endif
}

void Application::AdvanceStaggeredWakeTick() {
    if (wake_session_stage_ != WakeSessionStage::Prepare &&
        wake_session_stage_ != WakeSessionStage::Settle) return;
    if (device_state_ != kDeviceStateConnecting || !protocol_) {
        CancelStaggeredWake();
        return;
    }
    if (wake_session_delay_ticks_ > 0) {
        --wake_session_delay_ticks_;
        return;
    }
    if (wake_session_stage_ == WakeSessionStage::Prepare) {
        // Initialize AFE only if needed; repeated wakes must not reallocate it.
        audio_service_.PrepareVoiceProcessing();
        auto_awake_processor_prepared_ = true;
        wake_session_stage_ = WakeSessionStage::Settle;
        wake_session_delay_ticks_ = kAutoAwakePrepareSettleTicks;
        ESP_LOGI(AUTO_AWAKE_TAG, "LOCAL_WAKE_PREPARED: settling before UDP");
        return;
    }
    // Settle complete: open the UDP channel before sending either cached
    // wake audio or listen/detect; never burst dozens of packets at once.
    ESP_LOGI(AUTO_AWAKE_TAG, "LOCAL_WAKE_OPEN: opening audio channel");
    if (!protocol_->IsAudioChannelOpened() && !protocol_->OpenAudioChannel()) {
        ESP_LOGW(AUTO_AWAKE_TAG, "LOCAL_WAKE_FAILED: returning to standby");
        CancelStaggeredWake();
        auto_awake_sleep_latched_ = true;
        SetDeviceState(kDeviceStateIdle);
        return;
    }
    if (wake_session_send_data_) {
        // The encoder started before the two settling stages. Its sentinel
        // terminates PopWakeWordPacket(); on normal hardware it has finished
        // by now. Keep historic audio before listen/detect, as in native code.
        while (auto packet = audio_service_.PopWakeWordPacket()) {
            wake_session_packets_.push_back(std::move(packet));
        }
        wake_session_stage_ = WakeSessionStage::Upload;
        wake_session_next_send_us_ = esp_timer_get_time();
        ESP_LOGI(AUTO_AWAKE_TAG, "LOCAL_WAKE_UPLOAD: %u cached frames",
                 (unsigned)wake_session_packets_.size());
        PumpStaggeredWakePackets();
    } else {
        const ListeningMode mode = wake_session_mode_;
        const bool popup = wake_session_popup_;
        const bool proactive = wake_session_proactive_;
        const std::string context_text = wake_session_word_;
        CancelStaggeredWake();
        if (proactive) {
            // Same protocol order as a real wake: detect (with text) -> listen.
            protocol_->SendWakeWordDetected(context_text);
            ESP_LOGW(AUTO_AWAKE_TAG, "PROACTIVE_DETECT_SENT: %s", context_text.c_str());
        }
        SetListeningMode(mode);
        if (popup) audio_service_.PlaySound(Lang::Sounds::OGG_POPUP);
    }
}

void Application::PumpStaggeredWakePackets() {
    if (wake_session_stage_ != WakeSessionStage::Upload) return;
    if (device_state_ != kDeviceStateConnecting || !protocol_ ||
        !protocol_->IsAudioChannelOpened()) {
        CancelStaggeredWake();
        auto_awake_sleep_latched_ = true;
        SetDeviceState(kDeviceStateIdle);
        return;
    }
    int64_t now = esp_timer_get_time();
    if (now < wake_session_next_send_us_) return;
    for (int count = 0; count < kWakeAudioBurstLimit && !wake_session_packets_.empty(); ++count) {
        auto packet = std::move(wake_session_packets_.front());
        wake_session_packets_.pop_front();
        if (!protocol_->SendAudio(std::move(packet))) {
            // Sending consumes the packet even on failure; don't retransmit
            // stale voice data. Back off before the next cached frame.
            if (wake_session_failure_streak_ < 3) ++wake_session_failure_streak_;
            wake_session_next_send_us_ = esp_timer_get_time() +
                static_cast<int64_t>(kAudioSendBackoffMs[wake_session_failure_streak_ - 1]) * 1000;
            return;
        }
        wake_session_failure_streak_ = 0;
    }
    if (!wake_session_packets_.empty()) {
        wake_session_next_send_us_ = esp_timer_get_time() +
            static_cast<int64_t>(kWakeAudioPaceMs) * 1000;
        return;
    }
    // Protocol ordering: cached wake audio -> detect -> listen/start.
    protocol_->SendWakeWordDetected(wake_session_word_);
    ESP_LOGI(AUTO_AWAKE_TAG, "LOCAL_WAKE_LISTENING: %s", wake_session_word_.c_str());
    const ListeningMode mode = wake_session_mode_;
    CancelStaggeredWake();
    SetListeningMode(mode);
}

void Application::OnWakeWordDetected() {
    if (!protocol_) return;
    if (device_state_ == kDeviceStateIdle) {
#if CONFIG_SEND_WAKE_WORD_DATA
        BeginStaggeredWake(audio_service_.GetLastWakeWord(), true,
            aec_mode_ == kAecOff ? kListeningModeAutoStop : kListeningModeRealtime, false);
#else
        BeginStaggeredWake(audio_service_.GetLastWakeWord(), false,
            aec_mode_ == kAecOff ? kListeningModeAutoStop : kListeningModeRealtime, true);
#endif
    } else if (device_state_ == kDeviceStateSpeaking) {
        AbortSpeaking(kAbortReasonWakeWordDetected);
    } else if (device_state_ == kDeviceStateActivating) {
        SetDeviceState(kDeviceStateIdle);
    }
}

void Application::AbortSpeaking(AbortReason reason) {
    ESP_LOGI(TAG, "Abort speaking");
    aborted_ = true;
    if (protocol_) {
        protocol_->SendAbortSpeaking(reason);
    }
}

void Application::SetListeningMode(ListeningMode mode) {
    listening_mode_ = mode;
    SetDeviceState(kDeviceStateListening);
}

void Application::SetDeviceState(DeviceState state) {
    if (device_state_ == state) {
        return;
    }
    
    clock_ticks_ = 0;
    if (state == kDeviceStateIdle && wake_session_stage_ != WakeSessionStage::None) {
        CancelStaggeredWake();
    }
    // A new voice turn or channel must not inherit an earlier send failure.
    if (state != kDeviceStateListening &&
        !(state == kDeviceStateSpeaking && listening_mode_ == kListeningModeRealtime)) {
        audio_send_failure_streak_ = 0;
        audio_send_retry_after_us_ = 0;
    }
    auto previous_state = device_state_;
    device_state_ = state;
    ESP_LOGI(TAG, "STATE: %s", STATE_STRINGS[device_state_]);

    // Send the state change event
    DeviceStateEventManager::GetInstance().PostStateChangeEvent(previous_state, state);

    auto& board = Board::GetInstance();
    auto display = board.GetDisplay();
    auto led = board.GetLed();
    led->OnStateChanged();
    switch (state) {
        case kDeviceStateUnknown:
        case kDeviceStateIdle:
            display->SetStatus(Lang::Strings::STANDBY);
            display->SetEmotion("neutral");
            audio_service_.EnableVoiceProcessing(false);
            audio_service_.EnableWakeWordDetection(true);
            uart_send_string("idle");
            break;
        case kDeviceStateConnecting:
            display->SetStatus(Lang::Strings::CONNECTING);
            display->SetEmotion("neutral");
            display->SetChatMessage("system", "");
            break;
        case kDeviceStateListening:
            display->SetStatus(Lang::Strings::LISTENING);
            display->SetEmotion("neutral");
            uart_send_string("listening");

            // Make sure the audio processor is running
            if (!audio_service_.IsAudioProcessorRunning()) {
                // Send the start listening command
                protocol_->SendStartListening(listening_mode_);
                audio_service_.EnableVoiceProcessing(true);
                audio_service_.EnableWakeWordDetection(false);
            }
            break;
        case kDeviceStateSpeaking:
            display->SetStatus(Lang::Strings::SPEAKING);
            uart_send_string("speaking");
            if (listening_mode_ != kListeningModeRealtime) {
                audio_service_.EnableVoiceProcessing(false);
                // Only AFE wake word can be detected in speaking mode
                audio_service_.EnableWakeWordDetection(audio_service_.IsAfeWakeWord());
            }
            audio_service_.ResetDecoder();
            break;
        default:
            // Do nothing
            break;
    }
}

void Application::Reboot() {
    ESP_LOGI(TAG, "Rebooting...");
    // Disconnect the audio channel
    if (protocol_ && protocol_->IsAudioChannelOpened()) {
        protocol_->CloseAudioChannel();
    }
    protocol_.reset();
    audio_service_.Stop();

    vTaskDelay(pdMS_TO_TICKS(1000));
    esp_restart();
}

bool Application::UpgradeFirmware(Ota& ota, const std::string& url) {
    auto& board = Board::GetInstance();
    auto display = board.GetDisplay();
    
    // Use provided URL or get from OTA object
    std::string upgrade_url = url.empty() ? ota.GetFirmwareUrl() : url;
    std::string version_info = url.empty() ? ota.GetFirmwareVersion() : "(Manual upgrade)";
    
    // Close audio channel if it's open
    if (protocol_ && protocol_->IsAudioChannelOpened()) {
        ESP_LOGI(TAG, "Closing audio channel before firmware upgrade");
        protocol_->CloseAudioChannel();
    }
    ESP_LOGI(TAG, "Starting firmware upgrade from URL: %s", upgrade_url.c_str());
    
    Alert(Lang::Strings::OTA_UPGRADE, Lang::Strings::UPGRADING, "download", Lang::Sounds::OGG_UPGRADE);
    vTaskDelay(pdMS_TO_TICKS(3000));

    SetDeviceState(kDeviceStateUpgrading);
    
    std::string message = std::string(Lang::Strings::NEW_VERSION) + version_info;
    display->SetChatMessage("system", message.c_str());

    board.SetPowerSaveMode(false);
    audio_service_.Stop();
    vTaskDelay(pdMS_TO_TICKS(1000));

    bool upgrade_success = ota.StartUpgradeFromUrl(upgrade_url, [display](int progress, size_t speed) {
        std::thread([display, progress, speed]() {
            char buffer[32];
            snprintf(buffer, sizeof(buffer), "%d%% %uKB/s", progress, speed / 1024);
            display->SetChatMessage("system", buffer);
        }).detach();
    });

    if (!upgrade_success) {
        // Upgrade failed, restart audio service and continue running
        ESP_LOGE(TAG, "Firmware upgrade failed, restarting audio service and continuing operation...");
        audio_service_.Start(); // Restart audio service
        board.SetPowerSaveMode(true); // Restore power save mode
        Alert(Lang::Strings::ERROR, Lang::Strings::UPGRADE_FAILED, "circle_xmark", Lang::Sounds::OGG_EXCLAMATION);
        vTaskDelay(pdMS_TO_TICKS(3000));
        return false;
    } else {
        // Upgrade success, reboot immediately
        ESP_LOGI(TAG, "Firmware upgrade successful, rebooting...");
        display->SetChatMessage("system", "Upgrade successful, rebooting...");
        vTaskDelay(pdMS_TO_TICKS(1000)); // Brief pause to show message
        Reboot();
        return true;
    }
}

void Application::WakeWordInvoke(const std::string& wake_word) {
    // Some boards invoke this from other tasks; serialize all state changes
    // with the main event loop, just like the built-in wake callback.
    Schedule([this, wake_word]() {
        if (!protocol_) return;
        if (device_state_ == kDeviceStateIdle) {
#if CONFIG_USE_AFE_WAKE_WORD || CONFIG_USE_CUSTOM_WAKE_WORD
            BeginStaggeredWake(wake_word, true,
                aec_mode_ == kAecOff ? kListeningModeAutoStop : kListeningModeRealtime, false);
#else
            BeginStaggeredWake(wake_word, false,
                aec_mode_ == kAecOff ? kListeningModeAutoStop : kListeningModeRealtime, true);
#endif
        } else if (device_state_ == kDeviceStateSpeaking) {
            AbortSpeaking(kAbortReasonNone);
        } else if (device_state_ == kDeviceStateListening) {
            protocol_->CloseAudioChannel();
        }
    });
}

bool Application::CanEnterSleepMode() {
    if (device_state_ != kDeviceStateIdle) {
        return false;
    }

    if (protocol_ && protocol_->IsAudioChannelOpened()) {
        return false;
    }

    if (!audio_service_.IsIdle()) {
        return false;
    }

    // Now it is safe to enter sleep mode
    return true;
}

void Application::SendMcpMessage(const std::string& payload) {
    if (protocol_ == nullptr) {
        return;
    }

    // Make sure you are using main thread to send MCP message
    if (xTaskGetCurrentTaskHandle() == main_event_loop_task_handle_) {
        protocol_->SendMcpMessage(payload);
    } else {
        Schedule([this, payload = std::move(payload)]() {
            protocol_->SendMcpMessage(payload);
        });
    }
}

void Application::SetAecMode(AecMode mode) {
    aec_mode_ = mode;
    Schedule([this]() {
        auto& board = Board::GetInstance();
        auto display = board.GetDisplay();
        switch (aec_mode_) {
        case kAecOff:
            audio_service_.EnableDeviceAec(false);
            display->ShowNotification(Lang::Strings::RTC_MODE_OFF);
            break;
        case kAecOnServerSide:
            audio_service_.EnableDeviceAec(false);
            display->ShowNotification(Lang::Strings::RTC_MODE_ON);
            break;
        case kAecOnDeviceSide:
            audio_service_.EnableDeviceAec(true);
            display->ShowNotification(Lang::Strings::RTC_MODE_ON);
            break;
        }

        // If the AEC mode is changed, close the audio channel
        if (protocol_ && protocol_->IsAudioChannelOpened()) {
            protocol_->CloseAudioChannel();
        }
    });
}

void Application::PlaySound(const std::string_view& sound) {
    audio_service_.PlaySound(sound);
}