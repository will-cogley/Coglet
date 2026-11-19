// Coglet's own app description, stored in the firmware image right after
// ESP-IDF's esp_app_desc_t (section .rodata_custom_desc). The web flasher
// reads the start of the installed app from flash to show which version and
// edition a Coglet runs; see docs/coglet-web-flasher.md.
#pragma once

#include <cstdint>

namespace CogletAppDesc {

inline constexpr uint32_t kMagic = 0x434F474Cu;  // "LGOC" in memory: 4C 47 4F 43

struct Desc {
    uint32_t magic;       // kMagic
    char tag[8];          // "COGLET" (found by the web page by text)
    uint32_t layout;      // 1
    char edition[16];     // standard / christmas / elf / snowman
    char commit[16];      // short commit of a CI build, or "local"
    uint32_t reserved[4];
};
static_assert(sizeof(Desc) == 64, "the web flasher reads 64 bytes");

// Also keeps the description in the image (it is otherwise never read).
const Desc& Get();

}  // namespace CogletAppDesc
