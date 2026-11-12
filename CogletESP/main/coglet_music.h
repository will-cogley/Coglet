// Coglet custom songs.
//
// Two sources:
//  * the Music folder: every audio file in CogletESP/Music/ is converted at
//    build time by tools/coglet_music/build_music.py into Ogg/Opus plus a beat
//    map and compiled into the firmware (build/coglet_music/coglet_music_data.cc);
//  * the song library: songs added from the web flasher, stored in flash
//    outside the firmware so they survive updates (see LibraryHeader below).
//
// While a song plays, the ESP streams each beat to the RP2040 over UART and the
// RP2040 groove engine (music.py) turns the beats into motion using the song's
// preset:
//   Energetic - every servo, big and fast moves, eyes join in;
//   Calm      - ears, head and base only, small slow moves on the felt pulse;
//               eyelid and eye servos have their torque released.
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace CogletMusic {

enum class Preset : uint8_t { Calm, Energetic };

struct Beat {   // 8 bytes, same layout in the song library
    uint32_t t_ms;      // from the start of the song
    uint8_t strength;   // accent 0..9
    uint8_t energy;     // section loudness 0..9 (quiet verse .. full chorus)
    uint8_t flags;      // bit 0: bar start
    uint8_t reserved;
};

struct Song {
    const char* name;          // file name without extension / tags (UTF-8)
    Preset preset;
    uint16_t bpm;              // felt tempo the dance follows
    uint32_t duration_ms;
    const uint8_t* ogg;
    size_t ogg_size;
    const Beat* beats;
    size_t beat_count;

    std::string_view Ogg() const {
        return std::string_view(reinterpret_cast<const char*>(ogg), ogg_size);
    }
    const char* PresetName() const { return preset == Preset::Energetic ? "energetic" : "calm"; }
};

static_assert(sizeof(Beat) == 8, "Beat layout");

// Songs compiled in from the Music folder (generated source; may be 0).
extern const Song* const kSongs;
extern const size_t kSongCount;

// ---- Song library -------------------------------------------------------
// Songs added from the web flasher ("My songs") live in their own flash area:
// the last CONFIG_COGLET_MUSIC_LIBRARY_KB of the "assets" partition, which the
// assets image never reaches. Firmware updates don't write there, so these
// songs survive every update (only "Fresh install" erases them).
//
// Layout (little endian), written by tools/web_flasher/coglet_songs.js:
//   sector 0 (4 KB): LibraryHeader + `count` LibraryEntry
//   then one block per song, each starting on a 4 KB boundary:
//   Ogg/Opus data, padding to 4 bytes, the Beat table.
// The header CRC covers the entry table; each entry has the CRC of its own
// block, so adding or removing a song only rewrites sector 0 and the new
// block, and a damaged song is skipped without losing the others.
constexpr char kLibraryMagic[4] = {'C', 'G', 'M', 'L'};
constexpr uint16_t kLibraryVersion = 1;
constexpr uint16_t kLibraryMaxSongs = 32;
constexpr uint32_t kLibrarySector = 4096;

struct LibraryHeader {
    char magic[4];
    uint16_t version;
    uint16_t count;
    uint32_t total;        // end of the last song block (bytes from the area start)
    uint32_t crc32;        // zlib CRC-32 of the `count` entries
};

struct LibraryEntry {
    char name[36];         // UTF-8, NUL padded (always NUL terminated)
    uint8_t preset;        // 0 calm, 1 energetic
    uint8_t reserved;
    uint16_t bpm;
    uint32_t duration_ms;
    uint32_t ogg_offset;   // from the start of the area
    uint32_t ogg_size;
    uint32_t beats_offset; // 4-byte aligned array of Beat (8 bytes each)
    uint32_t beat_count;
    uint32_t crc32;        // CRC-32 of the Ogg data followed by the Beat table
};
static_assert(sizeof(LibraryHeader) == 16, "LibraryHeader layout");
static_assert(sizeof(LibraryEntry) == 64, "LibraryEntry layout");
static_assert(sizeof(LibraryHeader) + kLibraryMaxSongs * sizeof(LibraryEntry) <= kLibrarySector,
              "library table must fit in its sector");

uint32_t Crc32(const uint8_t* data, size_t size, uint32_t crc = 0);

// Validates a library image and appends its songs, which point into `data`
// (names included). Damaged songs are skipped and counted in *skipped.
// Returns false with a reason when the area holds no valid library.
bool ParseLibrary(const uint8_t* data, size_t size, std::vector<Song>& songs,
                  std::string* why = nullptr, size_t* skipped = nullptr);

// ---- All songs: Music folder first, then the library ----------------------
size_t Count();
const Song* At(size_t index);
size_t LibraryCount();

// Case-insensitive (ASCII) exact match on the song name.
inline const Song* Find(std::string_view name) {
    auto lower = [](char c) { return (c >= 'A' && c <= 'Z') ? static_cast<char>(c - 'A' + 'a') : c; };
    for (size_t i = 0; i < Count(); ++i) {
        std::string_view n(At(i)->name);
        if (n.size() != name.size()) continue;
        bool same = true;
        for (size_t k = 0; k < n.size() && same; ++k) same = lower(n[k]) == lower(name[k]);
        if (same) return At(i);
    }
    return nullptr;
}

// Exact match first, then a song whose name contains `name` or is contained in
// it (the assistant may say "night rain" for "Night Rain (piano)").
inline const Song* FindLoose(std::string_view name) {
    if (const Song* s = Find(name)) return s;
    if (name.size() < 3 || name == "random") return nullptr;
    auto lower = [](std::string_view v) {
        std::string out(v);
        for (auto& c : out) if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
        return out;
    };
    const std::string want = lower(name);
    for (size_t i = 0; i < Count(); ++i) {
        const std::string have = lower(At(i)->name);
        if (have.find(want) != std::string::npos ||
            (have.size() >= 4 && want.find(have) != std::string::npos)) {
            return At(i);
        }
    }
    return nullptr;
}

}  // namespace CogletMusic
