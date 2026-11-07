#ifndef _APPLICATION_H_
#define _APPLICATION_H_

#include "sdkconfig.h"
#include <freertos/FreeRTOS.h>
#include <freertos/event_groups.h>
#include <freertos/task.h>
#include <esp_timer.h>

#include <cstdint>
#include <atomic>
#include <string>
#include <mutex>
#include <deque>
#include <memory>

#include "protocol.h"
#include "ota.h"
#include "audio_service.h"
#include "device_state_event.h"


#define MAIN_EVENT_SCHEDULE (1 << 0)
#define MAIN_EVENT_SEND_AUDIO (1 << 1)
#define MAIN_EVENT_WAKE_WORD_DETECTED (1 << 2)
#define MAIN_EVENT_VAD_CHANGE (1 << 3)
#define MAIN_EVENT_ERROR (1 << 4)
#define MAIN_EVENT_CHECK_NEW_VERSION_DONE (1 << 5)
#define MAIN_EVENT_CLOCK_TICK (1 << 6)


enum AecMode {
    kAecOff,
    kAecOnDeviceSide,
    kAecOnServerSide,
};

class Application {
public:
    static Application& GetInstance() {
        static Application instance;
        return instance;
    }
    // 删除拷贝构造函数和赋值运算符
    Application(const Application&) = delete;
    Application& operator=(const Application&) = delete;

    void Start();
    void MainEventLoop();
    DeviceState GetDeviceState() const { return device_state_; }
    bool IsVoiceDetected() const { return audio_service_.IsVoiceDetected(); }
    void Schedule(std::function<void()> callback);
    void SetDeviceState(DeviceState state);
    void Alert(const char* status, const char* message, const char* emotion = "", const std::string_view& sound = "");
    void DismissAlert();
    void AbortSpeaking(AbortReason reason);
    void ToggleChatState();
    void StartListening();
    void StopListening();
    void Reboot();
    void WakeWordInvoke(const std::string& wake_word);
    // Open a session from idle without a wake word, using the same staged
    // AFE -> settle -> UDP path, then send `context_text` as the listen/detect
    // text (xiaozhi.me accepts only short texts, ~13 characters). Call from the
    // main loop (Schedule). Returns false if not idle or a wake is in progress.
    bool StartDeviceSession(const std::string& context_text);
    // Spoken reminder: the MCP tool self.coglet.reminder.last_due calls this
    // once the LLM has fetched the reminder text (any thread).
    void OnReminderTextDelivered() { reminder_text_delivered_ = true; }
#if CONFIG_COGLET_DANCE
    // MCP tool self.coglet.dance (any thread). style: mecha/evil/cat/random.
    // Returns the resolved style, or "" if a dance is already in progress.
    std::string RequestDance(const std::string& style);
#endif
    bool UpgradeFirmware(Ota& ota, const std::string& url = "");
    bool CanEnterSleepMode();
    void SendMcpMessage(const std::string& payload);
    void SetAecMode(AecMode mode);
    AecMode GetAecMode() const { return aec_mode_; }
    void PlaySound(const std::string_view& sound);
    AudioService& GetAudioService() { return audio_service_; }

private:
    Application();
    ~Application();

    std::mutex mutex_;
    std::deque<std::function<void()>> main_tasks_;
    std::unique_ptr<Protocol> protocol_;
    EventGroupHandle_t event_group_ = nullptr;
    esp_timer_handle_t clock_timer_handle_ = nullptr;
    volatile DeviceState device_state_ = kDeviceStateUnknown;
    ListeningMode listening_mode_ = kListeningModeAutoStop;
    AecMode aec_mode_ = kAecOff;
    std::string last_error_message_;
    AudioService audio_service_;

    bool has_server_time_ = false;
    bool aborted_ = false;
    // Boot Auto-Awake is one-shot. Once a voice session closes, wake word or
    // button activation is required to start another conversation.
    bool auto_awake_boot_pending_ = false;
    int auto_awake_boot_delay_ticks_ = 0;
    bool auto_awake_processor_prepared_ = false;
    bool auto_awake_sleep_latched_ = false;
    // Every LOCAL wake follows the prepare -> settle -> UDP channel -> paced
    // wake-word audio path. Boot Auto-Awake remains a separate one-shot path.
    enum class WakeSessionStage : uint8_t { None, Prepare, Settle, Upload };
    WakeSessionStage wake_session_stage_ = WakeSessionStage::None;
    int wake_session_delay_ticks_ = 0;
    bool wake_session_send_data_ = false;
    bool wake_session_popup_ = false;
    ListeningMode wake_session_mode_ = kListeningModeAutoStop;
    std::string wake_session_word_;
    std::deque<std::unique_ptr<AudioStreamPacket>> wake_session_packets_;
    int64_t wake_session_next_send_us_ = 0;
    uint8_t wake_session_failure_streak_ = 0;
    bool wake_session_proactive_ = false;

    // Spoken reminder: chime -> device-initiated session -> the LLM fetches
    // the text and says it -> playback finished -> back to idle.
    bool reminder_speech_pending_ = false;
    int64_t reminder_speech_deadline_us_ = 0;
    bool reminder_session_active_ = false;
    int64_t reminder_session_started_us_ = 0;
    int64_t reminder_last_tts_stop_us_ = 0;
    bool reminder_close_after_playback_ = false;
    std::atomic<bool> reminder_text_delivered_{false};
    void UpdateReminderSpeech();
    void CloseReminderSession(const char* reason);

#if CONFIG_COGLET_DANCE
    // Music dance: ack reply -> close session -> track + RP2040 choreography
    // -> device-initiated follow-up ("how was my dance?").
    enum class DanceStage : uint8_t { None, WaitAck, Starting, Playing, FollowUp };
    DanceStage dance_stage_ = DanceStage::None;
    std::string dance_style_;
    int64_t dance_stage_since_us_ = 0;
    int64_t dance_ack_tts_stop_us_ = 0;
    std::atomic<bool> dance_cancel_{false};
    std::atomic<bool> dance_audio_done_{true};
    std::atomic<bool> dance_task_running_{false};
    void UpdateDance();
    void BeginDancePlayback();
    void StopDance(const char* reason);
    bool DanceOwnsDevice() const {
        return dance_stage_ == DanceStage::Starting || dance_stage_ == DanceStage::Playing;
    }
#endif
    // Non-blocking uplink retry gate (monotonic microseconds).
    int64_t audio_send_retry_after_us_ = 0;
    uint8_t audio_send_failure_streak_ = 0;
    int clock_ticks_ = 0;
    TaskHandle_t check_new_version_task_handle_ = nullptr;
    TaskHandle_t main_event_loop_task_handle_ = nullptr;

    bool StartAutoAwakeSession(const char* reason);
    void BeginStaggeredWake(const std::string& word, bool send_data,
                            ListeningMode mode, bool play_popup);
    void AdvanceStaggeredWakeTick();
    void PumpStaggeredWakePackets();
    void CancelStaggeredWake();
    void OnWakeWordDetected();
    void CheckNewVersion(Ota& ota);
    void CheckAssetsVersion();
    void ShowActivationCode(const std::string& code, const std::string& message);
    void SetListeningMode(ListeningMode mode);
};


class TaskPriorityReset {
public:
    TaskPriorityReset(BaseType_t priority) {
        original_priority_ = uxTaskPriorityGet(NULL);
        vTaskPrioritySet(NULL, priority);
    }
    ~TaskPriorityReset() {
        vTaskPrioritySet(NULL, original_priority_);
    }

private:
    BaseType_t original_priority_;
};

#endif // _APPLICATION_H_
