#pragma once

#include <array>
#include <cstdint>
#include <ctime>
#include <mutex>
#include <string>
#include <vector>

// China UTC+08 demo. ESP-IDF wall clock is kept in UTC by the OTA time fix.
// Reminder entries are persisted in NVS; alarm output is independent of cloud sessions.
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
    static bool ParseChinaLocalTime(const std::string& datetime, time_t& epoch);
};
