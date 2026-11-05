#include "coglet_reminder.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <nvs.h>
#include <sdkconfig.h>
#include <esp_err.h>
#include <esp_log.h>

static const char* TAG = "CogletReminder";

CogletReminder& CogletReminder::Instance() {
    static CogletReminder instance;
    return instance;
}

void CogletReminder::ApplyTimezoneLocked() {
#if CONFIG_COGLET_REMINDER_TZ_MANUAL
    // Manual POSIX TZ string (supports daylight saving time).
    setenv("TZ", CONFIG_COGLET_REMINDER_TZ, 1);
    tzset();
    tz_label_ = std::string("手动设置的时区 ") + CONFIG_COGLET_REMINDER_TZ;
#else
    // POSIX TZ offsets have the opposite sign: UTC+08:00 is "<+08>-8".
    const int minutes = tz_offset_minutes_;
    const int magnitude = minutes < 0 ? -minutes : minutes;
    const int hh = magnitude / 60;
    const int mm = magnitude % 60;
    char tz[40];
    char label[24];
    if (mm) {
        snprintf(tz, sizeof(tz), "<%c%02d%02d>%s%d:%02d", minutes < 0 ? '-' : '+', hh, mm,
                 minutes < 0 ? "" : "-", hh, mm);
    } else {
        snprintf(tz, sizeof(tz), "<%c%02d>%s%d", minutes < 0 ? '-' : '+', hh,
                 minutes < 0 ? "" : "-", hh);
    }
    snprintf(label, sizeof(label), "UTC%c%02d:%02d", minutes < 0 ? '-' : '+', hh, mm);
    setenv("TZ", tz, 1);
    tzset();
    tz_label_ = std::string(label) +
        (tz_from_server_ ? "（来自小智服务器）" : "（默认值，尚未从服务器获取时区）");
#endif
}

void CogletReminder::SetServerTimezoneOffset(int minutes) {
#if CONFIG_COGLET_REMINDER_TZ_MANUAL
    ESP_LOGI(TAG, "Server timezone_offset=%d min ignored (manual TZ %s)", minutes,
             CONFIG_COGLET_REMINDER_TZ);
#else
    if (minutes < -14 * 60 || minutes > 14 * 60) {
        ESP_LOGW(TAG, "Ignoring invalid server timezone_offset=%d min", minutes);
        return;
    }
    std::lock_guard<std::mutex> lock(mutex_);
    tz_offset_minutes_ = minutes;
    tz_from_server_ = true;
    ApplyTimezoneLocked();
    ESP_LOGI(TAG, "Time zone from server: %s", tz_label_.c_str());
#endif
}

std::string CogletReminder::TimezoneLabel() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return tz_label_;
}

CogletReminder::CogletReminder() {
    ApplyTimezoneLocked();

    nvs_handle_t handle = 0;
    esp_err_t err = nvs_open("cog_rem", NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS open failed: %s", esp_err_to_name(err));
        return;
    }
    nvs_available_ = true;
    size_t length = sizeof(store_);
    Store restored = {};
    err = nvs_get_blob(handle, "tasks", &restored, &length);
    if (err == ESP_OK && length == sizeof(restored) &&
        restored.magic == kMagic && restored.version == kVersion && restored.next_id != 0) {
        store_ = restored;
        ESP_LOGI(TAG, "Restored reminders from NVS, next_id=%lu", (unsigned long)store_.next_id);
    } else if (err == ESP_ERR_NVS_NOT_FOUND) {
        ESP_LOGI(TAG, "No saved reminders yet");
    } else {
        ESP_LOGW(TAG, "Reminders NVS format unavailable; starting empty (err=%s)", esp_err_to_name(err));
    }
    nvs_close(handle);
}

bool CogletReminder::SaveLocked() {
    if (!nvs_available_) return false;
    nvs_handle_t handle = 0;
    esp_err_t err = nvs_open("cog_rem", NVS_READWRITE, &handle);
    if (err != ESP_OK) return false;
    err = nvs_set_blob(handle, "tasks", &store_, sizeof(store_));
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    if (err != ESP_OK) ESP_LOGE(TAG, "NVS commit failed: %s", esp_err_to_name(err));
    return err == ESP_OK;
}

bool CogletReminder::HasValidClock() {
    // A stale 1970 power-up clock is never accepted as a valid wall clock.
    return time(nullptr) >= 1735689600; // UTC 2025-01-01
}

std::string CogletReminder::FormatTime(time_t epoch) {
    struct tm local_tm = {};
    if (!localtime_r(&epoch, &local_tm)) return "time-unavailable";
    char buffer[32];
    strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", &local_tm);
    return buffer;
}

bool CogletReminder::ParseLocalTime(const std::string& value, time_t& epoch) {
    // YYYY-MM-DD HH:MM:SS or YYYY-MM-DDTHH:MM:SS; no ambiguous relative times.
    if (value.size() != 19 || (value[10] != ' ' && value[10] != 'T')) return false;
    for (size_t i = 0; i < value.size(); ++i) {
        if (i == 4 || i == 7) { if (value[i] != '-') return false; }
        else if (i == 13 || i == 16) { if (value[i] != ':') return false; }
        else if (i == 10) continue;
        else if (value[i] < '0' || value[i] > '9') return false;
    }
    const auto read = [&](size_t i, size_t n) {
        int out = 0;
        for (size_t j = 0; j < n; ++j) out = out * 10 + (value[i + j] - '0');
        return out;
    };
    const int year = read(0,4), month = read(5,2), day = read(8,2);
    const int hour = read(11,2), minute = read(14,2), second = read(17,2);
    if (year < 2025 || year > 2099 || month < 1 || month > 12 || day < 1 || day > 31 ||
        hour > 23 || minute > 59 || second > 59) return false;
    struct tm requested = {};
    requested.tm_year = year - 1900;
    requested.tm_mon = month - 1;
    requested.tm_mday = day;
    requested.tm_hour = hour;
    requested.tm_min = minute;
    requested.tm_sec = second;
    requested.tm_isdst = -1;
    epoch = mktime(&requested);
    if (epoch < 0) return false;
    struct tm roundtrip = {};
    if (!localtime_r(&epoch, &roundtrip)) return false;
    return roundtrip.tm_year == year-1900 && roundtrip.tm_mon == month-1 &&
           roundtrip.tm_mday == day && roundtrip.tm_hour == hour &&
           roundtrip.tm_min == minute && roundtrip.tm_sec == second;
}

std::string CogletReminder::Now() const {
    if (!HasValidClock()) return "ERROR: 设备时间尚未同步，不能可靠设置提醒；请检查 OTA server_time 并重新联网。";
    return "设备当前本地时间：" + FormatTime(time(nullptr)) + "，时区：" + TimezoneLabel() +
           "。请按这个时区把用户说的时间换算成 YYYY-MM-DD HH:MM:SS（设备本地时间）再调用 create。"
           "如果用户提到的时区与此不同，先换算到这个时区。";
}

std::string CogletReminder::Create(const std::string& local_datetime, const std::string& message) {
    if (!HasValidClock()) return "ERROR: 未校时，拒绝创建提醒。";
    if (message.empty() || message.size() > kMaxMessageBytes) {
        return "ERROR: 提醒内容不能为空，且 UTF-8 内容不能超过 120 字节。";
    }
    time_t when = 0;
    if (!ParseLocalTime(local_datetime, when)) {
        return "ERROR: 时间格式错误。必须为设备本地时间 YYYY-MM-DD HH:MM:SS，例如 2026-10-27 15:25:00。";
    }
    const time_t now = time(nullptr);
    if (when <= now + 2) return "ERROR: 提醒必须设置在至少 3 秒之后。";
    if (when > now + 366LL * 86400) return "ERROR: 实验版最多提前设置 366 天。";

    std::lock_guard<std::mutex> lock(mutex_);
    size_t slot = kCapacity;
    for (size_t i = 0; i < kCapacity; ++i) {
        if (!store_.items[i].active) { slot = i; break; }
    }
    if (slot == kCapacity) return "ERROR: 提醒已达到 12 条上限，请先取消一条。";
    Store previous = store_;
    Item& item = store_.items[slot];
    item = Item{};
    item.id = store_.next_id++;
    if (!store_.next_id) store_.next_id = 1;
    item.epoch = static_cast<int64_t>(when);
    std::memcpy(item.message, message.data(), message.size());
    item.message[message.size()] = '\0';
    item.active = 1;
    if (!SaveLocked()) { store_ = previous; return "ERROR: 提醒写入 NVS 失败，未创建。"; }
    ESP_LOGI(TAG, "CREATED id=%lu due=%s message=%s", (unsigned long)item.id,
             local_datetime.c_str(), item.message);
    // mutex_ is held here: read tz_label_ directly (TimezoneLabel() would deadlock).
    return "已保存本地提醒：编号 " + std::to_string(item.id) +
           "，设备本地时间 " + FormatTime(when) + "（" + tz_label_ + "），内容：" + message +
#if CONFIG_COGLET_REMINDER_SPEAK
           "。到点会先播放提示音，再由 Coglet 开口说出提醒内容。";
#else
           "。到点设备主动播放提示音；实验版尚不支持朗读任意提醒文字。";
#endif
}

std::string CogletReminder::List() {
    std::lock_guard<std::mutex> lock(mutex_);
    std::string text = "本地待触发提醒：";
    unsigned count = 0;
    for (const auto& item : store_.items) {
        if (!item.active) continue;
        text += "\n#" + std::to_string(item.id) + " " +
                FormatTime(static_cast<time_t>(item.epoch)) + " " + item.message;
        ++count;
    }
    if (!count) text += "无";
    return text;
}

std::string CogletReminder::Cancel(int id) {
    if (id <= 0) return "ERROR: 请输入有效的提醒编号。";
    std::lock_guard<std::mutex> lock(mutex_);
    for (auto& item : store_.items) {
        if (!item.active || item.id != static_cast<uint32_t>(id)) continue;
        Store previous = store_;
        item.active = 0;
        if (!SaveLocked()) { store_ = previous; return "ERROR: 取消提醒时 NVS 写入失败。"; }
        ESP_LOGI(TAG, "CANCELLED id=%d", id);
        return "已取消提醒 #" + std::to_string(id);
    }
    return "ERROR: 没有找到这个编号的待触发提醒。请先调用 list。";
}

bool CogletReminder::HasDue() const {
    if (!HasValidClock()) return false;
    const int64_t now = static_cast<int64_t>(time(nullptr));
    std::lock_guard<std::mutex> lock(mutex_);
    for (const auto& item : store_.items) {
        if (item.active && item.epoch <= now) return true;
    }
    return false;
}

std::vector<CogletReminder::Due> CogletReminder::TakeDueIfIdle() {
    std::vector<Due> due;
    if (!HasValidClock()) return due;
    std::lock_guard<std::mutex> lock(mutex_);
    const int64_t now = static_cast<int64_t>(time(nullptr));
    Store previous = store_;
    bool changed = false;
    for (auto& item : store_.items) {
        if (!item.active || now < item.epoch) continue;
        changed = true;
        item.active = 0;
        // Avoid a stale reminder blaring after a long unpowered period.
        if (now - item.epoch <= 300) {
            due.push_back({item.id, item.message,
                          FormatTime(static_cast<time_t>(item.epoch))});
        } else {
            ESP_LOGW(TAG, "MISSED id=%lu late=%lld seconds, skipped",
                     (unsigned long)item.id, (long long)(now - item.epoch));
        }
    }
    if (changed && !SaveLocked()) {
        store_ = previous;
        due.clear(); // Never announce a reminder without having persisted completion.
    }
    if (!due.empty()) {
        // Remember what fired so the LLM can say it (detect texts must be short).
        last_fired_message_.clear();
        for (const auto& d : due) {
            if (!last_fired_message_.empty()) last_fired_message_ += "；";
            last_fired_message_ += d.message;
        }
        last_fired_time_ = FormatTime(static_cast<time_t>(now)).substr(11, 5);  // HH:MM
        last_fired_epoch_ = now;
    }
    return due;
}

std::string CogletReminder::LastFiredText(int max_age_seconds) const {
    std::lock_guard<std::mutex> lock(mutex_);
    const int64_t now = static_cast<int64_t>(time(nullptr));
    if (last_fired_message_.empty() || now - last_fired_epoch_ > max_age_seconds) {
        return "";
    }
    return "刚到点的提醒：" + last_fired_message_ + "（" + last_fired_time_ + " 到点）。";
}
