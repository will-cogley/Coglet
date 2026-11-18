// NMRobotics Coglet - sounds.
// All startup and reminder sounds (Mecha, Evil, Cat, Christmas, Elf, Snowman)
// are linked in: menuconfig sets the defaults and the web flasher's Settings
// can change them (coglet_settings.h). The three dance tracks depend on the
// firmware edition (menuconfig: Firmware edition).
#pragma once

#include <string_view>
#include "sdkconfig.h"
#include "coglet_settings.h"
#include "coglet_edition.h"

#include "coglet_sounds/coglet_mecha_boot_chime.h"
#include "coglet_sounds/coglet_evil_boot_chime.h"
#include "coglet_sounds/coglet_cat_boot_chime.h"
#include "coglet_sounds/coglet_christmas_boot_chime.h"
#include "coglet_sounds/coglet_elf_boot_chime.h"
#include "coglet_sounds/coglet_snowman_boot_chime.h"
#include "coglet_sounds/coglet_mecha_reminder_chime.h"
#include "coglet_sounds/coglet_evil_reminder_chime.h"
#include "coglet_sounds/coglet_reminder_chime.h"
#include "coglet_sounds/coglet_christmas_reminder_chime.h"
#include "coglet_sounds/coglet_elf_reminder_chime.h"
#include "coglet_sounds/coglet_snowman_reminder_chime.h"

#if CONFIG_COGLET_DANCE && CONFIG_COGLET_EDITION_CHRISTMAS
#  include "coglet_sounds/coglet_dance_lyrical.h"
#  include "coglet_sounds/coglet_dance_classic.h"
#  include "coglet_sounds/coglet_dance_grand.h"
#elif CONFIG_COGLET_DANCE && CONFIG_COGLET_EDITION_ELF
#  include "coglet_sounds/coglet_dance_workshop.h"
#  include "coglet_sounds/coglet_dance_mischief.h"
#  include "coglet_sounds/coglet_dance_party.h"
#elif CONFIG_COGLET_DANCE && CONFIG_COGLET_EDITION_SNOWMAN
#  include "coglet_sounds/coglet_dance_lullaby.h"
#  include "coglet_sounds/coglet_dance_stomp.h"
#  include "coglet_sounds/coglet_dance_blizzard.h"
#elif CONFIG_COGLET_DANCE
#  include "coglet_sounds/coglet_dance_mecha.h"
#  include "coglet_sounds/coglet_dance_evil.h"
#  include "coglet_sounds/coglet_dance_cat.h"
#endif

namespace CogletSounds {

#if CONFIG_COGLET_DANCE
#if CONFIG_COGLET_EDITION_CHRISTMAS
inline std::string_view Dance(std::string_view style) {
    if (style == "lyrical") return CogletDanceLyrical::Ogg();
    if (style == "classic") return CogletDanceClassic::Ogg();
    if (style == "grand") return CogletDanceGrand::Ogg();
    return {};
}
#elif CONFIG_COGLET_EDITION_ELF
inline std::string_view Dance(std::string_view style) {
    if (style == "workshop") return CogletDanceWorkshop::Ogg();
    if (style == "mischief") return CogletDanceMischief::Ogg();
    if (style == "party") return CogletDanceParty::Ogg();
    return {};
}
#elif CONFIG_COGLET_EDITION_SNOWMAN
inline std::string_view Dance(std::string_view style) {
    if (style == "lullaby") return CogletDanceLullaby::Ogg();
    if (style == "stomp") return CogletDanceStomp::Ogg();
    if (style == "blizzard") return CogletDanceBlizzard::Ogg();
    return {};
}
#else
// style: "mecha" | "evil" | "cat". Empty view for anything else.
inline std::string_view Dance(std::string_view style) {
    if (style == "mecha") return CogletDanceMecha::Ogg();
    if (style == "evil") return CogletDanceEvil::Ogg();
    if (style == "cat") return CogletDanceCat::Ogg();
    return {};
}
#endif
#endif

// "mecha" | "evil" | "cat" | "christmas" | "elf" | "snowman": from Settings, else the menuconfig choice.
inline std::string_view StartupStyle() {
    const std::string& chosen = CogletSettings::Get().startup;
    if (!chosen.empty()) return chosen;
#if defined(CONFIG_COGLET_BOOT_SOUND_EVIL)
    return "evil";
#elif defined(CONFIG_COGLET_BOOT_SOUND_CAT)
    return "cat";
#elif defined(CONFIG_COGLET_BOOT_SOUND_CHRISTMAS)
    return "christmas";
#elif defined(CONFIG_COGLET_BOOT_SOUND_ELF)
    return "elf";
#elif defined(CONFIG_COGLET_BOOT_SOUND_SNOWMAN)
    return "snowman";
#else
    return "mecha";
#endif
}

inline std::string_view Boot() {
    const auto style = StartupStyle();
    if (style == "evil") return CogletEvilBootChime::Ogg();
    if (style == "cat") return CogletCatBootChime::Ogg();
    if (style == "christmas") return CogletChristmasBootChime::Ogg();
    if (style == "elf") return CogletElfBootChime::Ogg();
    if (style == "snowman") return CogletSnowmanBootChime::Ogg();
    return CogletMechaBootChime::Ogg();
}

inline const char* BootName() {
    const auto style = StartupStyle();
    if (style == "evil") return "Evil Startup";
    if (style == "cat") return "Cat Startup";
    if (style == "christmas") return "Christmas Startup";
    if (style == "elf") return "Elf Startup";
    if (style == "snowman") return "Snowman Startup";
    return "Mecha Startup";
}

// "mecha" | "evil" | "cat" | "christmas" | "elf" | "snowman": from Settings, else the menuconfig choice.
inline std::string_view ReminderStyle() {
    const std::string& chosen = CogletSettings::Get().reminder;
    if (!chosen.empty()) return chosen;
#if defined(CONFIG_COGLET_REMINDER_SOUND_EVIL)
    return "evil";
#elif defined(CONFIG_COGLET_REMINDER_SOUND_CAT)
    return "cat";
#elif defined(CONFIG_COGLET_REMINDER_SOUND_CHRISTMAS)
    return "christmas";
#elif defined(CONFIG_COGLET_REMINDER_SOUND_ELF)
    return "elf";
#elif defined(CONFIG_COGLET_REMINDER_SOUND_SNOWMAN)
    return "snowman";
#else
    return "mecha";
#endif
}

inline std::string_view Reminder() {
    const auto style = ReminderStyle();
    if (style == "evil") return CogletEvilReminderChime::Ogg();
    if (style == "cat") return CogletReminderChime::Ogg();
    if (style == "christmas") return CogletChristmasReminderChime::Ogg();
    if (style == "elf") return CogletElfReminderChime::Ogg();
    if (style == "snowman") return CogletSnowmanReminderChime::Ogg();
    return CogletMechaReminderChime::Ogg();
}

inline const char* ReminderName() {
    const auto style = ReminderStyle();
    if (style == "evil") return "Evil Reminder";
    if (style == "cat") return "Cat Reminder (Gentle Chime)";
    if (style == "christmas") return "Christmas Reminder (Church Bells)";
    if (style == "elf") return "Elf Reminder (Toy Clock)";
    if (style == "snowman") return "Snowman Reminder (Icicles)";
    return "Mecha Reminder";
}

}  // namespace CogletSounds
