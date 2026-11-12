#include "coglet_rp2040_sync.h"

#include <cstdio>

namespace CogletRp2040 {
namespace {

constexpr size_t kChunkBytes = 384;          // -> 512 base64 chars per line
constexpr int kVersionTimeoutMs = 1500;
constexpr int kVersionAttempts = 3;
constexpr int kReadyTimeoutMs = 4000;
constexpr int kAckTimeoutMs = 1500;
constexpr int kEndTimeoutMs = 3000;
constexpr int kCommitTimeoutMs = 8000;
constexpr int kRetries = 4;

std::string Base64(const uint8_t* data, size_t len) {
    static const char* const kAlphabet =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    out.reserve((len + 2) / 3 * 4);
    size_t i = 0;
    for (; i + 2 < len; i += 3) {
        const uint32_t v = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
        out += kAlphabet[(v >> 18) & 63];
        out += kAlphabet[(v >> 12) & 63];
        out += kAlphabet[(v >> 6) & 63];
        out += kAlphabet[v & 63];
    }
    if (i < len) {
        uint32_t v = data[i] << 16;
        if (i + 1 < len) v |= data[i + 1] << 8;
        out += kAlphabet[(v >> 18) & 63];
        out += kAlphabet[(v >> 12) & 63];
        out += (i + 1 < len) ? kAlphabet[(v >> 6) & 63] : '=';
        out += '=';
    }
    return out;
}

// Send a line and wait for a reply starting with `expect`. Error replies
// ("upd:err:...") and timeouts are retried up to `retries` times.
bool Exchange(Link& link, const std::string& line, const std::string& expect, int timeout_ms,
              int retries, std::string* reply = nullptr) {
    for (int attempt = 0; attempt <= retries; ++attempt) {
        link.SendLine(line);
        std::string got;
        while (link.ReadLine(got, timeout_ms)) {
            if (got.compare(0, expect.size(), expect) == 0) {
                if (reply) *reply = got;
                return true;
            }
            if (got.compare(0, 8, "upd:err:") == 0) {
                link.Log("RP2040 replied " + got + " to " + line.substr(0, 24));
                break;          // resend
            }
            // anything else (stale ack, version reply): keep waiting
        }
    }
    return false;
}

bool SendFile(Link& link, const BundleFile& file) {
    char header[96];
    snprintf(header, sizeof(header), "upd:file:%s:%u:%08x", file.name,
             static_cast<unsigned>(file.size), static_cast<unsigned>(file.crc32));
    if (!Exchange(link, header, "upd:ok:f", kAckTimeoutMs, kRetries)) {
        link.Log(std::string("no ack for file header ") + file.name);
        return false;
    }
    unsigned seq = 0;
    for (size_t off = 0; off < file.size; off += kChunkBytes, ++seq) {
        const size_t n = file.size - off < kChunkBytes ? file.size - off : kChunkBytes;
        char prefix[24];
        snprintf(prefix, sizeof(prefix), "upd:d:%u:", seq);
        char ack[24];
        snprintf(ack, sizeof(ack), "upd:ok:%u", seq);
        // Exact match on the ack so "upd:ok:1" is not taken for "upd:ok:12".
        bool acked = false;
        for (int attempt = 0; attempt <= kRetries && !acked; ++attempt) {
            link.SendLine(prefix + Base64(file.data + off, n));
            std::string got;
            while (link.ReadLine(got, kAckTimeoutMs)) {
                if (got == ack) { acked = true; break; }
                if (got.compare(0, 8, "upd:err:") == 0) break;
            }
        }
        if (!acked) {
            link.Log(std::string("chunk ") + std::to_string(seq) + " of " + file.name + " not acknowledged");
            return false;
        }
    }
    if (!Exchange(link, "upd:end", "upd:ok:e", kEndTimeoutMs, 1)) {
        link.Log(std::string("RP2040 rejected ") + file.name + " (size/CRC)");
        return false;
    }
    return true;
}

}  // namespace

const char* ToString(SyncResult result) {
    switch (result) {
    case SyncResult::UpToDate: return "up to date";
    case SyncResult::Updated: return "updated";
    case SyncResult::NoUpdater: return "no updater on the RP2040 (one-time setup needed)";
    case SyncResult::Failed: return "failed";
    }
    return "?";
}

SyncResult Sync(Link& link, const char* bundle_id, const BundleFile* files, size_t file_count) {
    std::string reply;
    bool answered = false;
    for (int i = 0; i < kVersionAttempts && !answered; ++i) {
        answered = Exchange(link, "upd:ver?", "upd:ver:", kVersionTimeoutMs, 0, &reply);
    }
    if (!answered) {
        return SyncResult::NoUpdater;
    }
    const std::string current = reply.substr(8);
    if (current == bundle_id) {
        link.Log("RP2040 bundle " + current + " is up to date");
        return SyncResult::UpToDate;
    }
    link.Log("RP2040 bundle " + current + " -> " + bundle_id + ", sending " +
             std::to_string(file_count) + " files");

    if (!Exchange(link, std::string("upd:begin:") + bundle_id + ":" + std::to_string(file_count),
                  "upd:ready", kReadyTimeoutMs, 1)) {
        link.Log("RP2040 did not start the update");
        return SyncResult::Failed;
    }
    for (size_t i = 0; i < file_count; ++i) {
        if (!SendFile(link, files[i])) {
            link.SendLine("upd:abort");
            return SyncResult::Failed;
        }
        link.Log(std::string("sent ") + files[i].name);
    }
    if (!Exchange(link, "upd:commit", "upd:done", kCommitTimeoutMs, 0)) {
        link.Log("RP2040 did not confirm the commit");
        return SyncResult::Failed;
    }
    return SyncResult::Updated;
}

}  // namespace CogletRp2040

// ------------------------------------------------------------------ ESP32
#ifdef ESP_PLATFORM
#include <driver/uart.h>
#include <esp_log.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "application.h"
#include "uart_component.h"

namespace CogletRp2040 {
namespace {

constexpr const char* TAG = "CogletRp2040";
constexpr int kBootDelayMs = 5000;            // let the RP2040 finish booting

class UartLink : public Link {
public:
    void SendLine(const std::string& line) override {
        // One write per line: atomic with respect to the main loop's lines.
        std::string out = line + "\r\n";
        uart_write_bytes(UART_PORT_NUM, out.data(), out.size());
    }

    bool ReadLine(std::string& line, int timeout_ms) override {
        const int64_t deadline = esp_timer_get_time() + static_cast<int64_t>(timeout_ms) * 1000;
        for (;;) {
            size_t nl;
            while ((nl = buffer_.find('\n')) != std::string::npos) {
                std::string candidate = buffer_.substr(0, nl);
                buffer_.erase(0, nl + 1);
                while (!candidate.empty() && (candidate.back() == '\r' || candidate.back() == ' ')) {
                    candidate.pop_back();
                }
                if (candidate.compare(0, 4, "upd:") == 0) {
                    line = candidate;
                    return true;
                }
            }
            const int64_t left_us = deadline - esp_timer_get_time();
            if (left_us <= 0) return false;
            uint8_t chunk[128];
            const int wait_ms = left_us > 20000 ? 20 : static_cast<int>(left_us / 1000) + 1;
            const int n = uart_read_bytes(UART_PORT_NUM, chunk, sizeof(chunk), pdMS_TO_TICKS(wait_ms));
            if (n > 0) {
                buffer_.append(reinterpret_cast<const char*>(chunk), n);
                if (buffer_.size() > 4096) buffer_.erase(0, buffer_.size() - 1024);
            }
        }
    }

    void Log(const std::string& message) override {
        ESP_LOGI(TAG, "%s", message.c_str());
    }

private:
    std::string buffer_;
};

void SyncTask(void*) {
    vTaskDelay(pdMS_TO_TICKS(kBootDelayMs));
    uart_flush_input(UART_PORT_NUM);
    UartLink link;
    const int64_t start = esp_timer_get_time();
    const SyncResult result = Sync(link, kBundleId, kBundleFiles, kBundleFileCount);
    const int seconds = static_cast<int>((esp_timer_get_time() - start) / 1000000);
    if (result == SyncResult::NoUpdater) {
        ESP_LOGW(TAG, "RP2040 did not answer: it needs the one-time setup from the web flasher "
                      "(RP2040 program from before automatic updates)");
    } else if (result == SyncResult::Failed) {
        ESP_LOGE(TAG, "RP2040 update failed after %d s; it keeps its current program and the "
                      "update is retried on the next boot", seconds);
    } else {
        ESP_LOGI(TAG, "RP2040 %s (bundle %s, %d s)", ToString(result), kBundleId, seconds);
    }
    if (result == SyncResult::Updated) {
        // The RP2040 restarts with the new files; tell it the current state.
        vTaskDelay(pdMS_TO_TICKS(4000));
        auto& app = Application::GetInstance();
        app.Schedule([&app]() { app.ResendStateToRp2040(); });
    }
    vTaskDelete(nullptr);
}

}  // namespace

void StartSyncTask() {
    xTaskCreate(SyncTask, "rp2040_sync", 6144, nullptr, 2, nullptr);
}

}  // namespace CogletRp2040
#endif  // ESP_PLATFORM
