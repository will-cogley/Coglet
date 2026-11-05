#pragma once

#include <array>
#include <cstdint>
#include <ctime>
#include <mutex>
#include <string>
#include <vector>

// Local reminders. The ESP-IDF wall clock is kept in UTC (OTA server_time);
// reminders are entered and shown in the device's local time zone, which is
// taken from the OTA server (timezone_offset) or set manually in menuconfig.
// Entries are stored as UTC epochs in NVS, so a time-zone change never moves
// an already-saved reminder.
class CogletReminder {
public:
    struct Due {
        uint32_t id;
        std::string message;
        std::string datetime;
    };

    static CogletReminder& Instance();

    std::string Now() const;
    std::string Create(const std::string& local_datetime, const std::string& message);
    std::string List();
    std::string Cancel(int id);

    // Called on Application's existing 1-second tick, only when idle.
    // Persists removal before handing alarms to the audio playback logic.
    bool HasDue() const;
    std::vector<Due> TakeDueIfIdle();

    // Time zone. Auto mode: called by the OTA check with the server's
    // timezone_offset (minutes east of UTC). Ignored in manual mode.
    void SetServerTimezoneOffset(int minutes);
    std::string TimezoneLabel() const;

    // Text of the reminder(s) that fired most recently, for the LLM to speak
    // (self.coglet.reminder.last_due). Empty if nothing fired recently.
    std::string LastFiredText(int max_age_seconds = 900) const;

private:
    CogletReminder();

    static constexpr uint32_t kMagic = 0x43475231; // CGR1
    static constexpr uint32_t kVersion = 1;
    static constexpr size_t kCapacity = 12;
    static constexpr size_t kMaxMessageBytes = 120;

    struct Item {
        uint32_t id = 0;
        int64_t epoch = 0;
        char message[kMaxMessageBytes + 1] = {};
        uint8_t active = 0;
        uint8_t reserved[7] = {};
    };
    struct Store {
        uint32_t magic = kMagic;
        uint32_t version = kVersion;
        uint32_t next_id = 1;
        uint32_t reserved = 0;
        Item items[kCapacity] = {};
    };

    mutable std::mutex mutex_;
    Store store_ = {};
    bool nvs_available_ = false;

    bool SaveLocked();
    static bool HasValidClock();
    static std::string FormatTime(time_t epoch);
    static bool ParseLocalTime(const std::string& datetime, time_t& epoch);
    void ApplyTimezoneLocked();

    bool tz_from_server_ = false;
    int tz_offset_minutes_ = 480;
    std::string tz_label_;

    std::string last_fired_message_;
    std::string last_fired_time_;
    int64_t last_fired_epoch_ = 0;
};
