// Coglet custom songs ("Music" folder).
//
// Every audio file dropped into CogletESP/Music/ is converted at build time by
// tools/coglet_music/build_music.py into Ogg/Opus plus a beat map, and compiled
// into the firmware (generated file: build/coglet_music/coglet_music_data.cc).
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

namespace CogletMusic {

enum class Preset : uint8_t { Calm, Energetic };

struct Beat {
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

// Defined in the generated source (kSongCount may be 0).
extern const Song* const kSongs;
extern const size_t kSongCount;

// Case-insensitive (ASCII) exact match on the song name.
inline const Song* Find(std::string_view name) {
    auto lower = [](char c) { return (c >= 'A' && c <= 'Z') ? static_cast<char>(c - 'A' + 'a') : c; };
    for (size_t i = 0; i < kSongCount; ++i) {
        std::string_view n(kSongs[i].name);
        if (n.size() != name.size()) continue;
        bool same = true;
        for (size_t k = 0; k < n.size() && same; ++k) same = lower(n[k]) == lower(name[k]);
        if (same) return &kSongs[i];
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
    for (size_t i = 0; i < kSongCount; ++i) {
        const std::string have = lower(kSongs[i].name);
        if (have.find(want) != std::string::npos ||
            (have.size() >= 4 && want.find(have) != std::string::npos)) {
            return &kSongs[i];
        }
    }
    return nullptr;
}

}  // namespace CogletMusic
