// Coglet settings changed from the web flasher (Settings card).
//
// Stored in one 4 KB flash sector of the "assets" partition, right before the
// song library (see coglet_music.h), so firmware updates never touch it. Any
// value that is missing falls back to the firmware's menuconfig default.
//
// Sector layout (little endian):
//   "CGST", u16 version (1), u16 text length, u32 CRC-32 (zlib) of the text,
//   then the text: one "key=value" per line, UTF-8.
// Keys (unknown keys are ignored, so newer pages stay compatible):
//   wake_word  English wake phrase, e.g. "hey coglet" (lowercase a-z, ' and spaces)
//   threshold  wake word threshold in percent, 1..99 (lower wakes more easily)
//   startup    startup sound: mecha | evil | cat | christmas | elf | snowman
//   reminder   reminder sound: mecha | evil | cat | christmas | elf | snowman
//   aec        device-side echo cancellation (talk over Coglet): on | off;
//              only used when the firmware has it (CONFIG_USE_DEVICE_AEC)
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace CogletSettings {

constexpr uint32_t kSectorSize = 4096;

struct Values {
    std::string wake_word;   // empty: menuconfig default
    int threshold = 0;       // 0: menuconfig default
    std::string startup;     // empty: menuconfig default
    std::string reminder;    // empty: menuconfig default
    std::string aec;         // "on" | "off", empty: menuconfig default
};

// Parses a settings sector. Returns false (and leaves `out` empty) when the
// sector is blank or damaged; invalid single values are dropped.
bool Parse(const uint8_t* data, size_t size, Values& out, std::string* why = nullptr);

bool ValidWakeWord(const std::string& phrase);

// Settings of this Coglet, read from flash once (ESP only).
const Values& Get();

// Device-side AEC wanted on this boot: the "aec" setting, else the menuconfig
// default (on, unless COGLET_AEC_DEFAULT_OFF). Always false without
// CONFIG_USE_DEVICE_AEC. Decided once per boot (ESP only).
bool DeviceAec();

}  // namespace CogletSettings
