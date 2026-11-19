// Coglet firmware edition (menuconfig: NMRobotics Coglet Dance -> Firmware edition).
// The three built-in dances differ per edition; the RP2040 knows the
// choreographies of every edition, so "dance:<style>" works with any.
#pragma once

#include "sdkconfig.h"

namespace CogletEdition {

#if CONFIG_COGLET_EDITION_CHRISTMAS
#define COGLET_EDITION_NAME "christmas"
inline constexpr const char* kName = COGLET_EDITION_NAME;
inline constexpr const char* kDanceStyles[] = {"lyrical", "classic", "grand"};
inline constexpr const char* kDanceStylesHelp =
    "lyrical = Silent Night, gentle and dreamy; classic = Jingle Bells, playful; "
    "grand = Joy to the World, majestic";
#elif CONFIG_COGLET_EDITION_ELF
#define COGLET_EDITION_NAME "elf"
inline constexpr const char* kName = COGLET_EDITION_NAME;
inline constexpr const char* kDanceStyles[] = {"workshop", "mischief", "party"};
inline constexpr const char* kDanceStylesHelp =
    "workshop = Deck the Halls, a busy toy workshop; mischief = God Rest Ye Merry Gentlemen, "
    "sneaky then bold; party = We Wish You a Merry Christmas, a merry waltz";
#elif CONFIG_COGLET_EDITION_SNOWMAN
#define COGLET_EDITION_NAME "snowman"
inline constexpr const char* kName = COGLET_EDITION_NAME;
inline constexpr const char* kDanceStyles[] = {"lullaby", "stomp", "blizzard"};
inline constexpr const char* kDanceStylesHelp =
    "lullaby = Brahms' Lullaby, dozing off in the snow; stomp = Good King Wenceslas, "
    "waddling through deep snow; blizzard = Carol of the Bells (Shchedryk), a swirling blizzard";
#else
#define COGLET_EDITION_NAME "standard"
inline constexpr const char* kName = COGLET_EDITION_NAME;
inline constexpr const char* kDanceStyles[] = {"mecha", "evil", "cat"};
inline constexpr const char* kDanceStylesHelp =
    "mecha = heavy mecha electro, evil = gloomy gothic, cat = gentle anime cat pop";
#endif

}  // namespace CogletEdition
