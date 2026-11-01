// NMRobotics Coglet - compile-time sound selection from menuconfig.
// Only the selected startup and reminder headers are included in this
// translation unit, so unused sound arrays are not linked into firmware.
#pragma once

#include <string_view>
#include "sdkconfig.h"

#if defined(CONFIG_COGLET_BOOT_SOUND_MECHA)
#  include "coglet_sounds/coglet_mecha_boot_chime.h"
#elif defined(CONFIG_COGLET_BOOT_SOUND_EVIL)
#  include "coglet_sounds/coglet_evil_boot_chime.h"
#elif defined(CONFIG_COGLET_BOOT_SOUND_CAT)
#  include "coglet_sounds/coglet_cat_boot_chime.h"
#else
#  error "Please select a Coglet Startup Sound in menuconfig"
#endif

#if defined(CONFIG_COGLET_REMINDER_SOUND_MECHA)
#  include "coglet_sounds/coglet_mecha_reminder_chime.h"
#elif defined(CONFIG_COGLET_REMINDER_SOUND_EVIL)
#  include "coglet_sounds/coglet_evil_reminder_chime.h"
#elif defined(CONFIG_COGLET_REMINDER_SOUND_CAT)
#  include "coglet_sounds/coglet_reminder_chime.h"
#else
#  error "Please select a Coglet Reminder Sound in menuconfig"
#endif

namespace CogletSounds {

inline std::string_view Boot() {
#if defined(CONFIG_COGLET_BOOT_SOUND_MECHA)
    return CogletMechaBootChime::Ogg();
#elif defined(CONFIG_COGLET_BOOT_SOUND_EVIL)
    return CogletEvilBootChime::Ogg();
#else
    return CogletCatBootChime::Ogg();
#endif
}

inline const char* BootName() {
#if defined(CONFIG_COGLET_BOOT_SOUND_MECHA)
    return "Mecha Startup";
#elif defined(CONFIG_COGLET_BOOT_SOUND_EVIL)
    return "Evil Startup";
#else
    return "Cat Startup";
#endif
}

inline std::string_view Reminder() {
#if defined(CONFIG_COGLET_REMINDER_SOUND_MECHA)
    return CogletMechaReminderChime::Ogg();
#elif defined(CONFIG_COGLET_REMINDER_SOUND_EVIL)
    return CogletEvilReminderChime::Ogg();
#else
    return CogletReminderChime::Ogg();
#endif
}

inline const char* ReminderName() {
#if defined(CONFIG_COGLET_REMINDER_SOUND_MECHA)
    return "Mecha Reminder";
#elif defined(CONFIG_COGLET_REMINDER_SOUND_EVIL)
    return "Evil Reminder";
#else
    return "Cat Reminder (Gentle Chime)";
#endif
}

}  // namespace CogletSounds
