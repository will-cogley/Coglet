#include "coglet_app_desc.h"

#include "coglet_edition.h"

#ifndef COGLET_BUILD_COMMIT
#define COGLET_BUILD_COMMIT "local"
#endif

namespace CogletAppDesc {

// The version itself is ESP-IDF's (esp_app_desc_t.version = PROJECT_VER).
extern "C" const Desc coglet_app_desc __attribute__((section(".rodata_custom_desc"), used)) = {
    kMagic, "COGLET", 1, COGLET_EDITION_NAME, COGLET_BUILD_COMMIT, {0, 0, 0, 0},
};

const Desc& Get() { return coglet_app_desc; }

}  // namespace CogletAppDesc
