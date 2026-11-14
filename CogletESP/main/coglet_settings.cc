// See coglet_settings.h. The parser is plain C++ for the host tests
// (tests/song_library).
#include "coglet_settings.h"

#include <cstring>

namespace CogletSettings {

static uint32_t Crc32(const uint8_t* data, size_t size) {
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (int k = 0; k < 8; ++k) crc = (crc & 1) ? (crc >> 1) ^ 0xEDB88320u : crc >> 1;
    }
    return crc ^ 0xFFFFFFFFu;
}

bool ValidWakeWord(const std::string& phrase) {
    if (phrase.size() < 3 || phrase.size() > 40) return false;
    if (phrase.front() == ' ' || phrase.back() == ' ') return false;
    bool letter = false;
    char prev = 0;
    for (char c : phrase) {
        const bool ok = (c >= 'a' && c <= 'z') || c == ' ' || c == '\'';
        if (!ok || (c == ' ' && prev == ' ')) return false;
        letter |= (c >= 'a' && c <= 'z');
        prev = c;
    }
    return letter;
}

bool Parse(const uint8_t* data, size_t size, Values& out, std::string* why) {
    out = Values();
    auto fail = [why](const char* reason) {
        if (why) *why = reason;
        return false;
    };
    if (data == nullptr || size < 12) return fail("too small");
    if (std::memcmp(data, "CGST", 4) != 0) return fail("empty");
    uint16_t version, length;
    uint32_t crc;
    std::memcpy(&version, data + 4, 2);
    std::memcpy(&length, data + 6, 2);
    std::memcpy(&crc, data + 8, 4);
    if (version != 1) return fail("unknown version");
    if (12u + length > size || 12u + length > kSectorSize) return fail("bad length");
    if (Crc32(data + 12, length) != crc) return fail("damaged");

    const std::string text(reinterpret_cast<const char*>(data + 12), length);
    size_t pos = 0;
    while (pos < text.size()) {
        size_t end = text.find('\n', pos);
        if (end == std::string::npos) end = text.size();
        const std::string line = text.substr(pos, end - pos);
        pos = end + 1;
        const size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        const std::string key = line.substr(0, eq);
        const std::string value = line.substr(eq + 1);
        if (key == "wake_word") {
            if (ValidWakeWord(value)) out.wake_word = value;
        } else if (key == "threshold") {
            int v = 0;
            bool digits = !value.empty() && value.size() <= 2;
            for (char c : value) {
                if (c < '0' || c > '9') digits = false;
                v = v * 10 + (c - '0');
            }
            if (digits && v >= 1 && v <= 99) out.threshold = v;
        } else if (key == "startup" || key == "reminder") {
            if (value == "mecha" || value == "evil" || value == "cat") {
                (key == "startup" ? out.startup : out.reminder) = value;
            }
        }
    }
    if (why) why->clear();
    return true;
}

}  // namespace CogletSettings

#ifdef ESP_PLATFORM
#include <esp_log.h>
#include <esp_partition.h>
#include <sdkconfig.h>

namespace CogletSettings {

const Values& Get() {
    static Values values;
    static bool loaded = false;
    if (loaded) return values;
    loaded = true;
    static const char* TAG = "CogletSettings";
    const esp_partition_t* part =
        esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_ANY, "assets");
    if (part == nullptr) return values;
#if defined(CONFIG_COGLET_MUSIC_LIBRARY_KB) && CONFIG_COGLET_DANCE && CONFIG_COGLET_MUSIC
    const uint32_t library = CONFIG_COGLET_MUSIC_LIBRARY_KB * 1024u;
#else
    const uint32_t library = 0;
#endif
    if (part->size < library + kSectorSize * 2) return values;
    const uint32_t offset = part->size - library - kSectorSize;
    static uint8_t sector[kSectorSize];
    if (esp_partition_read(part, offset, sector, sizeof(sector)) != ESP_OK) {
        ESP_LOGW(TAG, "could not read the settings");
        return values;
    }
    std::string why;
    if (!Parse(sector, sizeof(sector), values, &why)) {
        ESP_LOGI(TAG, "settings: %s, using the firmware defaults", why.c_str());
        return values;
    }
    ESP_LOGI(TAG, "settings: wake word \"%s\", threshold %d, startup %s, reminder %s",
             values.wake_word.empty() ? "(default)" : values.wake_word.c_str(), values.threshold,
             values.startup.empty() ? "(default)" : values.startup.c_str(),
             values.reminder.empty() ? "(default)" : values.reminder.c_str());
    return values;
}

}  // namespace CogletSettings
#endif  // ESP_PLATFORM
