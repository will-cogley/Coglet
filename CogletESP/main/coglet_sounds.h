// NMRobotics Coglet - sounds.
// All three startup and all three reminder sounds are linked in: menuconfig
// sets the defaults and the web flasher's Settings can change them
// (coglet_settings.h).
#pragma once

#include <string_view>
#include "sdkconfig.h"
#include "coglet_settings.h"

#include "coglet_sounds/coglet_mecha_boot_chime.h"
#include "coglet_sounds/coglet_evil_boot_chime.h"
#include "coglet_sounds/coglet_cat_boot_chime.h"
#include "coglet_sounds/coglet_mecha_reminder_chime.h"
#include "coglet_sounds/coglet_evil_reminder_chime.h"
#include "coglet_sounds/coglet_reminder_chime.h"

#if CONFIG_COGLET_DANCE
#  include "coglet_sounds/coglet_dance_mecha.h"
#  include "coglet_sounds/coglet_dance_evil.h"
#  include "coglet_sounds/coglet_dance_cat.h"
#endif

namespace CogletSounds {

#if CONFIG_COGLET_DANCE
// style: "mecha" | "evil" | "cat". Empty view for anything else.
inline std::string_view Dance(std::string_view style) {
    if (style == "mecha") return CogletDanceMecha::Ogg();
    if (style == "evil") return CogletDanceEvil::Ogg();
    if (style == "cat") return CogletDanceCat::Ogg();
    return {};
}
#endif

// "mecha" | "evil" | "cat": from Settings, else the menuconfig choice.
inline std::string_view StartupStyle() {
    const std::string& chosen = CogletSettings::Get().startup;
    if (!chosen.empty()) return chosen;
#if defined(CONFIG_COGLET_BOOT_SOUND_EVIL)
    return "evil";
#elif defined(CONFIG_COGLET_BOOT_SOUND_CAT)
    return "cat";
#else
    return "mecha";
#endif
}

inline std::string_view Boot() {
    const auto style = StartupStyle();
    if (style == "evil") return CogletEvilBootChime::Ogg();
    if (style == "cat") return CogletCatBootChime::Ogg();
    return CogletMechaBootChime::Ogg();
}

inline const char* BootName() {
    const auto style = StartupStyle();
    if (style == "evil") return "Evil Startup";
    if (style == "cat") return "Cat Startup";
    return "Mecha Startup";
}

// "mecha" | "evil" | "cat": from Settings, else the menuconfig choice.
inline std::string_view ReminderStyle() {
    const std::string& chosen = CogletSettings::Get().reminder;
    if (!chosen.empty()) return chosen;
#if defined(CONFIG_COGLET_REMINDER_SOUND_EVIL)
    return "evil";
#elif defined(CONFIG_COGLET_REMINDER_SOUND_CAT)
    return "cat";
#else
    return "mecha";
#endif
}

inline std::string_view Reminder() {
    const auto style = ReminderStyle();
    if (style == "evil") return CogletEvilReminderChime::Ogg();
    if (style == "cat") return CogletReminderChime::Ogg();
    return CogletMechaReminderChime::Ogg();
}

inline const char* ReminderName() {
    const auto style = ReminderStyle();
    if (style == "evil") return "Evil Reminder";
    if (style == "cat") return "Cat Reminder (Gentle Chime)";
    return "Mecha Reminder";
}

}  // namespace CogletSounds
