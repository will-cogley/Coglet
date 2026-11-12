// Coglet song library: songs added from the web flasher, kept in flash outside
// the firmware (see coglet_music.h). The parser is plain C++ so the host tests
// (tests/song_library) can run it on images made by the web page's code.
#include "coglet_music.h"

#include <cstring>

namespace CogletMusic {

uint32_t Crc32(const uint8_t* data, size_t size, uint32_t crc) {
    static uint32_t table[256];
    static bool ready = false;
    if (!ready) {
        for (uint32_t i = 0; i < 256; ++i) {
            uint32_t c = i;
            for (int k = 0; k < 8; ++k) c = (c & 1) ? (c >> 1) ^ 0xEDB88320u : c >> 1;
            table[i] = c;
        }
        ready = true;
    }
    crc ^= 0xFFFFFFFFu;
    for (size_t i = 0; i < size; ++i) crc = table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
    return crc ^ 0xFFFFFFFFu;
}

static bool InRange(uint64_t offset, uint64_t length, uint64_t limit) {
    return offset <= limit && length <= limit - offset;
}

bool ParseLibrary(const uint8_t* data, size_t size, std::vector<Song>& songs, std::string* why,
                  size_t* skipped) {
    auto fail = [why](const char* reason) {
        if (why) *why = reason;
        return false;
    };
    if (skipped) *skipped = 0;
    if (data == nullptr || size < kLibrarySector) return fail("area too small");
    LibraryHeader h;
    std::memcpy(&h, data, sizeof(h));
    if (std::memcmp(h.magic, kLibraryMagic, 4) != 0) return fail("empty");
    if (h.version != kLibraryVersion) return fail("unknown library version");
    if (h.count > kLibraryMaxSongs) return fail("bad song count");
    if (h.total > size) return fail("bad size");
    const uint8_t* table = data + sizeof(LibraryHeader);
    if (Crc32(table, h.count * sizeof(LibraryEntry)) != h.crc32) return fail("damaged song list");

    for (uint16_t i = 0; i < h.count; ++i) {
        LibraryEntry e;
        std::memcpy(&e, table + i * sizeof(LibraryEntry), sizeof(e));
        const bool ok =
            std::memchr(e.name, 0, sizeof(e.name)) != nullptr && e.name[0] != 0 &&
            e.ogg_size >= 64 && e.ogg_offset >= kLibrarySector &&
            InRange(e.ogg_offset, e.ogg_size, h.total) &&
            e.beats_offset % 4 == 0 && e.beat_count <= 20000 &&
            InRange(e.beats_offset, uint64_t(e.beat_count) * sizeof(Beat), h.total) &&
            e.preset <= 1 &&
            std::memcmp(data + e.ogg_offset, "OggS", 4) == 0;
        if (!ok) {
            if (skipped) ++*skipped;
            continue;
        }
        uint32_t crc = Crc32(data + e.ogg_offset, e.ogg_size);
        crc = Crc32(data + e.beats_offset, e.beat_count * sizeof(Beat), crc);
        if (crc != e.crc32) {
            if (skipped) ++*skipped;
            continue;
        }
        const auto* entry_in_data = reinterpret_cast<const LibraryEntry*>(table + i * sizeof(LibraryEntry));
        Song s;
        s.name = entry_in_data->name;           // NUL terminated, checked above
        s.preset = e.preset ? Preset::Energetic : Preset::Calm;
        s.bpm = e.bpm;
        s.duration_ms = e.duration_ms;
        s.ogg = data + e.ogg_offset;
        s.ogg_size = e.ogg_size;
        s.beats = reinterpret_cast<const Beat*>(data + e.beats_offset);
        s.beat_count = e.beat_count;
        songs.push_back(s);
    }
    if (why) why->clear();
    return true;
}

}  // namespace CogletMusic

#ifdef ESP_PLATFORM
#include <esp_log.h>
#include <esp_partition.h>
#include <sdkconfig.h>

#include "assets.h"

namespace CogletMusic {

[[maybe_unused]] static const char* TAG = "CogletMusic";

static std::vector<Song>& Library() {
    static std::vector<Song> songs;
    static bool loaded = false;
    if (loaded) return songs;
    loaded = true;
#if CONFIG_COGLET_MUSIC_LIBRARY_KB > 0
    const esp_partition_t* part =
        esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_ANY, "assets");
    const uint32_t area = CONFIG_COGLET_MUSIC_LIBRARY_KB * 1024u;
    if (part == nullptr || part->size < area * 2) {
        ESP_LOGW(TAG, "song library: no room in the assets partition");
        return songs;
    }
    const uint32_t area_offset = part->size - area;

    // The assets code maps the whole partition already; reuse that mapping.
    auto& assets = Assets::GetInstance();
    const uint8_t* base = nullptr;
    if (assets.mapped_data() != nullptr) {
        const uint8_t* root = reinterpret_cast<const uint8_t*>(assets.mapped_data());
        if (assets.checksum_valid()) {
            uint32_t stored_len = 0;
            std::memcpy(&stored_len, root + 8, 4);
            if (12ull + stored_len > area_offset) {
                ESP_LOGE(TAG, "song library disabled: the assets image (%lu KB) reaches into the "
                         "song area; lower COGLET_MUSIC_LIBRARY_KB",
                         static_cast<unsigned long>((12u + stored_len) / 1024));
                return songs;
            }
        }
        base = root + area_offset;
    } else {
        static esp_partition_mmap_handle_t handle;
        const void* ptr = nullptr;
        if (esp_partition_mmap(part, area_offset, area, ESP_PARTITION_MMAP_DATA, &ptr, &handle) != ESP_OK) {
            ESP_LOGE(TAG, "song library: could not map flash");
            return songs;
        }
        base = static_cast<const uint8_t*>(ptr);
    }

    std::string why;
    size_t skipped = 0;
    if (!ParseLibrary(base, area, songs, &why, &skipped)) {
        ESP_LOGI(TAG, "song library: %s (add songs from the web flasher)", why.c_str());
        return songs;
    }
    ESP_LOGI(TAG, "song library: %u songs at assets+0x%lx", static_cast<unsigned>(songs.size()),
             static_cast<unsigned long>(area_offset));
    for (const auto& s : songs) {
        ESP_LOGI(TAG, "  \"%s\" %s %u BPM, %lu s", s.name, s.PresetName(), static_cast<unsigned>(s.bpm),
                 static_cast<unsigned long>(s.duration_ms / 1000));
    }
    if (skipped) {
        ESP_LOGW(TAG, "song library: %u damaged songs skipped (add them again)", static_cast<unsigned>(skipped));
    }
#endif
    return songs;
}

size_t LibraryCount() { return Library().size(); }

size_t Count() { return kSongCount + Library().size(); }

const Song* At(size_t index) {
    if (index < kSongCount) return &kSongs[index];
    index -= kSongCount;
    auto& lib = Library();
    return index < lib.size() ? &lib[index] : nullptr;
}

}  // namespace CogletMusic
#endif  // ESP_PLATFORM
