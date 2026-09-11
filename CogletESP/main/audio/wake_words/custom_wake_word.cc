#include "custom_wake_word.h"
#include "audio_service.h"
#include "system_info.h"
#include "assets.h"

#include <esp_log.h>
#include <esp_mn_iface.h>
#include <esp_mn_models.h>
#include <esp_mn_speech_commands.h>
#include <cJSON.h>


#define TAG "CustomWakeWord"


CustomWakeWord::CustomWakeWord()
    : wake_word_pcm_(), wake_word_opus_() {
}

CustomWakeWord::~CustomWakeWord() {
    if (multinet_model_data_ != nullptr && multinet_ != nullptr) {
        multinet_->destroy(multinet_model_data_);
        multinet_model_data_ = nullptr;
    }

    if (wake_word_encode_task_stack_ != nullptr) {
        heap_caps_free(wake_word_encode_task_stack_);
    }

    if (wake_word_encode_task_buffer_ != nullptr) {
        heap_caps_free(wake_word_encode_task_buffer_);
    }

    if (models_ != nullptr) {
        esp_srmodel_deinit(models_);
    }
}

void CustomWakeWord::ParseWakenetModelConfig() {
    // Read index.json
    auto& assets = Assets::GetInstance();
    void* ptr = nullptr;
    size_t size = 0;
    if (!assets.GetAssetData("index.json", ptr, size)) {
        ESP_LOGE(TAG, "Failed to read index.json");
        return;
    }
    cJSON* root = cJSON_ParseWithLength(static_cast<char*>(ptr), size);
    if (root == nullptr) {
        ESP_LOGE(TAG, "Failed to parse index.json");
        return;
    }
    cJSON* multinet_model = cJSON_GetObjectItem(root, "multinet_model");
    if (cJSON_IsObject(multinet_model)) {
        cJSON* language = cJSON_GetObjectItem(multinet_model, "language");
        cJSON* duration = cJSON_GetObjectItem(multinet_model, "duration");
        cJSON* threshold = cJSON_GetObjectItem(multinet_model, "threshold");
        cJSON* commands = cJSON_GetObjectItem(multinet_model, "commands");
        if (cJSON_IsString(language)) {
            language_ = language->valuestring;
        }
        if (cJSON_IsNumber(duration)) {
            duration_ = duration->valueint;
        }
        if (cJSON_IsNumber(threshold)) {
            threshold_ = threshold->valuedouble;
        }
        if (cJSON_IsArray(commands)) {
            for (int i = 0; i < cJSON_GetArraySize(commands); i++) {
                cJSON* command = cJSON_GetArrayItem(commands, i);
                if (cJSON_IsObject(command)) {
                    cJSON* command_name = cJSON_GetObjectItem(command, "command");
                    cJSON* text = cJSON_GetObjectItem(command, "text");
                    cJSON* action = cJSON_GetObjectItem(command, "action");
                    if (cJSON_IsString(command_name) && cJSON_IsString(text) && cJSON_IsString(action)) {
                        commands_.push_back({command_name->valuestring, text->valuestring, action->valuestring});
                        ESP_LOGI(TAG, "Command: %s, Text: %s, Action: %s", command_name->valuestring, text->valuestring, action->valuestring);
                    }
                }
            }
        }
    }
    cJSON_Delete(root);
}


bool CustomWakeWord::Initialize(AudioCodec* codec, srmodel_list_t* models_list) {
    codec_ = codec;
    commands_.clear();

    if (models_list == nullptr) {
        language_ = "cn";
        models_ = esp_srmodel_init("model");
#ifdef CONFIG_CUSTOM_WAKE_WORD
        threshold_ = CONFIG_CUSTOM_WAKE_WORD_THRESHOLD / 100.0f;
#endif
    } else {
        models_ = models_list;
        ParseWakenetModelConfig();
    }

    // Kconfig is the source of truth for configured custom wake words.
    // Assets/index.json normally contains the same list, but append any
    // missing command here as a runtime safety net.
    auto add_command_if_missing = [this](const char* command, const char* text) {
        if (command == nullptr || text == nullptr || command[0] == '\0' || text[0] == '\0') {
            return;
        }
        for (const auto& item : commands_) {
            if (item.command == command) {
                return;
            }
        }
        commands_.push_back({command, text, "wake"});
        ESP_LOGI(TAG, "Added configured wake command: %s (%s)", command, text);
    };

#ifdef CONFIG_CUSTOM_WAKE_WORD
    add_command_if_missing(CONFIG_CUSTOM_WAKE_WORD, CONFIG_CUSTOM_WAKE_WORD_DISPLAY);
#ifdef CONFIG_USE_SECONDARY_CUSTOM_WAKE_WORD
    add_command_if_missing(CONFIG_SECONDARY_CUSTOM_WAKE_WORD, CONFIG_SECONDARY_CUSTOM_WAKE_WORD_DISPLAY);
#endif
#endif

    if (models_ == nullptr || models_->num == -1) {
        ESP_LOGE(TAG, "Failed to initialize wakenet model");
        return false;
    }

    // 初始化 multinet (命令词识别)
    mn_name_ = esp_srmodel_filter(models_, ESP_MN_PREFIX, language_.c_str());
    if (mn_name_ == nullptr) {
        ESP_LOGW(TAG, "Language '%s' multinet not found, falling back to any multinet model", language_.c_str());
        mn_name_ = esp_srmodel_filter(models_, ESP_MN_PREFIX, NULL);
    }
    if (mn_name_ == nullptr) {
        ESP_LOGE(TAG, "Failed to initialize multinet, mn_name is nullptr");
        ESP_LOGI(TAG, "Please refer to https://pcn7cs20v8cr.feishu.cn/wiki/CpQjwQsCJiQSWSkYEvrcxcbVnwh to add custom wake word");
        return false;
    }

    multinet_ = esp_mn_handle_from_name(mn_name_);
    multinet_model_data_ = multinet_->create(mn_name_, duration_);
    multinet_->set_det_threshold(multinet_model_data_, threshold_);
    esp_mn_commands_clear();

    // Register multiple pronunciation variants for the same wake command ID.
    // MultiNet allows multiple phrases to share one command ID, but the
    // phrase string itself must be unique. Therefore the extra strings
    // below are internal labels; the explicit phoneme sequence is what
    // phoneme-based MultiNet models match against.
    struct WakePhonemeVariant {
        const char* label;
        const char* phonemes;
    };

    static constexpr WakePhonemeVariant kHelloCogletVariants[] = {
        // Baseline / current tuned pronunciation:
        // HH AH L OW  K AA G L EH T
        {"hello coglet",            "hcLb KnGLfT"},

        // British English candidate:
        // LOT vowel -> AO, reduced final -let -> IH
        {"hello coglet british",    "hcLb KeGLgT"},

        // Australian English candidate:
        // LOT vowel -> AO, reduced final -let -> AH
        {"hello coglet australian", "hcLb KeGLcT"},

        // Japanese-accented English candidate:
        // HELLO ~ he-ro; consonant-cluster/final-stop vowel insertion
        // HH EH R OW  K OW G UH R EH T OW
        {"hello coglet japanese",   "hfRb KbGwRfTb"},

        // Korean-accented English candidate:
        // HELLO ~ hel-lo; vowel insertion around the GL cluster
        // HH EH L OW  K OW G UH L L EH T
        {"hello coglet korean",     "hfLb KbGwLLfT"},

        // Mandarin-accented English candidate:
        // Keep HELLO near baseline and allow a schwa in the GL cluster
        // HH AH L OW  K AA G AH L EH T
        {"hello coglet mandarin",   "hcLb KnGcLfT"},
    };

    for (int i = 0; i < commands_.size(); i++) {
        if (commands_[i].command == "hello coglet") {
            for (const auto& variant : kHelloCogletVariants) {
                esp_err_t err = esp_mn_commands_phoneme_add(
                    i + 1,
                    variant.label,
                    variant.phonemes
                );
                if (err != ESP_OK) {
                    ESP_LOGW(TAG,
                             "Failed to add Hello Coglet variant: %s (%s), err=%d",
                             variant.label, variant.phonemes, static_cast<int>(err));
                } else {
                    ESP_LOGI(TAG,
                             "Hello Coglet variant: %s -> %s",
                             variant.label, variant.phonemes);
                }
            }
        } else {
            esp_mn_commands_add(
                i + 1, commands_[i].command.c_str()
            );
        }
    }

    esp_mn_commands_update();
    
    multinet_->print_active_speech_commands(multinet_model_data_);
    return true;
}

void CustomWakeWord::OnWakeWordDetected(std::function<void(const std::string& wake_word)> callback) {
    wake_word_detected_callback_ = callback;
}

void CustomWakeWord::Start() {
    running_ = true;
}

void CustomWakeWord::Stop() {
    running_ = false;
}

void CustomWakeWord::Feed(const std::vector<int16_t>& data) {
    if (multinet_model_data_ == nullptr || !running_) {
        return;
    }

    esp_mn_state_t mn_state;
    // If input channels is 2, we need to fetch the left channel data
    if (codec_->input_channels() == 2) {
        auto mono_data = std::vector<int16_t>(data.size() / 2);
        for (size_t i = 0, j = 0; i < mono_data.size(); ++i, j += 2) {
            mono_data[i] = data[j];
        }

        StoreWakeWordData(mono_data);
        mn_state = multinet_->detect(multinet_model_data_, const_cast<int16_t*>(mono_data.data()));
    } else {
        StoreWakeWordData(data);
        mn_state = multinet_->detect(multinet_model_data_, const_cast<int16_t*>(data.data()));
    }
    
    if (mn_state == ESP_MN_STATE_DETECTING) {
        return;
    } else if (mn_state == ESP_MN_STATE_DETECTED) {
        esp_mn_results_t *mn_result = multinet_->get_results(multinet_model_data_);
        for (int i = 0; i < mn_result->num && running_; i++) {
            ESP_LOGI(TAG, "Custom wake word detected: command_id=%d, string=%s, prob=%f", 
                    mn_result->command_id[i], mn_result->string, mn_result->prob[i]);
            const int command_index = mn_result->command_id[i] - 1;
            if (command_index < 0 || command_index >= static_cast<int>(commands_.size())) {
                ESP_LOGW(TAG, "Ignoring invalid MultiNet command_id=%d (registered=%d)",
                         mn_result->command_id[i], static_cast<int>(commands_.size()));
                continue;
            }
            auto& command = commands_[command_index];
            if (command.action == "wake") {
                last_detected_wake_word_ = command.text;
                running_ = false;
                
                if (wake_word_detected_callback_) {
                    wake_word_detected_callback_(last_detected_wake_word_);
                }
            }
        }
        multinet_->clean(multinet_model_data_);
    } else if (mn_state == ESP_MN_STATE_TIMEOUT) {
        ESP_LOGD(TAG, "Command word detection timeout, cleaning state");
        multinet_->clean(multinet_model_data_);
    }
}

size_t CustomWakeWord::GetFeedSize() {
    if (multinet_model_data_ == nullptr) {
        return 0;
    }
    return multinet_->get_samp_chunksize(multinet_model_data_);
}

void CustomWakeWord::StoreWakeWordData(const std::vector<int16_t>& data) {
    // store audio data to wake_word_pcm_
    wake_word_pcm_.push_back(data);
    // keep about 2 seconds of data, detect duration is 30ms (sample_rate == 16000, chunksize == 512)
    while (wake_word_pcm_.size() > 2000 / 30) {
        wake_word_pcm_.pop_front();
    }
}

void CustomWakeWord::EncodeWakeWordData() {
    const size_t stack_size = 4096 * 7;
    wake_word_opus_.clear();
    if (wake_word_encode_task_stack_ == nullptr) {
        wake_word_encode_task_stack_ = (StackType_t*)heap_caps_malloc(stack_size, MALLOC_CAP_SPIRAM);
        assert(wake_word_encode_task_stack_ != nullptr);
    }
    if (wake_word_encode_task_buffer_ == nullptr) {
        wake_word_encode_task_buffer_ = (StaticTask_t*)heap_caps_malloc(sizeof(StaticTask_t), MALLOC_CAP_INTERNAL);
        assert(wake_word_encode_task_buffer_ != nullptr);
    }

    wake_word_encode_task_ = xTaskCreateStatic([](void* arg) {
        auto this_ = (CustomWakeWord*)arg;
        {
            auto start_time = esp_timer_get_time();
            auto encoder = std::make_unique<OpusEncoderWrapper>(16000, 1, OPUS_FRAME_DURATION_MS);
            encoder->SetComplexity(0); // 0 is the fastest

            int packets = 0;
            for (auto& pcm: this_->wake_word_pcm_) {
                encoder->Encode(std::move(pcm), [this_](std::vector<uint8_t>&& opus) {
                    std::lock_guard<std::mutex> lock(this_->wake_word_mutex_);
                    this_->wake_word_opus_.emplace_back(std::move(opus));
                    this_->wake_word_cv_.notify_all();
                });
                packets++;
            }
            this_->wake_word_pcm_.clear();

            auto end_time = esp_timer_get_time();
            ESP_LOGI(TAG, "Encode wake word opus %d packets in %ld ms", packets, (long)((end_time - start_time) / 1000));

            std::lock_guard<std::mutex> lock(this_->wake_word_mutex_);
            this_->wake_word_opus_.push_back(std::vector<uint8_t>());
            this_->wake_word_cv_.notify_all();
        }
        vTaskDelete(NULL);
    }, "encode_wake_word", stack_size, this, 2, wake_word_encode_task_stack_, wake_word_encode_task_buffer_);
}

bool CustomWakeWord::GetWakeWordOpus(std::vector<uint8_t>& opus) {
    std::unique_lock<std::mutex> lock(wake_word_mutex_);
    wake_word_cv_.wait(lock, [this]() {
        return !wake_word_opus_.empty();
    });
    opus.swap(wake_word_opus_.front());
    wake_word_opus_.pop_front();
    return !opus.empty();
}
