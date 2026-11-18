// Host test: the firmware's library parser on images made by the web page.
#include <cassert>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include "coglet_music.h"
#include "coglet_settings.h"

namespace CogletMusic {
const Song* const kSongs = nullptr;
const size_t kSongCount = 0;
}

using namespace CogletMusic;

static std::vector<uint8_t> Load(const std::string& p) {
    std::ifstream f(p, std::ios::binary);
    return std::vector<uint8_t>(std::istreambuf_iterator<char>(f), {});
}

static std::vector<Song> Parse(const std::vector<uint8_t>& img, bool expect_ok, size_t* skipped = nullptr,
                               std::string* why_out = nullptr) {
    std::vector<Song> songs;
    std::string why;
    bool ok = ParseLibrary(img.data(), img.size(), songs, &why, skipped);
    if (ok != expect_ok) {
        std::printf("unexpected result: %d (%s)\n", ok, why.c_str());
        assert(false);
    }
    if (why_out) *why_out = why;
    return songs;
}

int main(int, char** argv) {
    const std::string dir = argv[1];
    size_t skipped = 0;
    std::string why;

    Parse(Load(dir + "/lib_empty.bin"), false, nullptr, &why);
    assert(why == "empty");

    auto two = Load(dir + "/lib_two.bin");
    auto s = Parse(two, true, &skipped);
    assert(s.size() == 2 && skipped == 0);
    assert(std::string(s[0].name) == "Night Rain 夜雨");
    assert(s[0].preset == Preset::Calm && s[1].preset == Preset::Energetic);
    assert(s[0].beat_count == 40 && s[1].beats[59].t_ms == 59 * 500 && s[1].beats[4].flags == 1);
    assert(s[0].bpm == 140 && std::string(s[0].Ogg().substr(0, 4)) == "OggS");

    auto three = Parse(Load(dir + "/lib_three.bin"), true, &skipped);
    assert(three.size() == 3 && skipped == 0 && std::string(three[2].name) == "Third");
    // the first two songs did not move
    assert(three[0].ogg_size == s[0].ogg_size);

    auto removed = Parse(Load(dir + "/lib_removed.bin"), true, &skipped);
    assert(removed.size() == 2 && std::string(removed[0].name) == "Drop");

    auto compact = Parse(Load(dir + "/lib_compact.bin"), true, &skipped);
    assert(compact.size() == 2 && skipped == 0 && std::string(compact[1].name) == "Third");

    auto damaged = Parse(Load(dir + "/lib_damaged.bin"), true, &skipped);
    assert(damaged.size() == 1 && skipped == 1 && std::string(damaged[0].name) == "Drop");

    // damaged song list (header CRC)
    auto bad = two;
    bad[16 + 3] ^= 1;
    Parse(bad, false, nullptr, &why);
    assert(why == "damaged song list");

    // zlib CRC check value
    const char* check = "123456789";
    assert(Crc32(reinterpret_cast<const uint8_t*>(check), 9) == 0xCBF43926u);
    // settings sector written by the page
    {
        CogletSettings::Values v;
        auto full = Load(dir + "/set_full.bin");
        assert(CogletSettings::Parse(full.data(), full.size(), v));
        assert(v.wake_word == "hey coglet" && v.threshold == 3 && v.startup == "cat" && v.reminder == "evil");
        auto rem = Load(dir + "/set_reminder.bin");
        assert(CogletSettings::Parse(rem.data(), rem.size(), v));
        assert(v.wake_word.empty() && v.threshold == 0 && v.startup.empty() && v.reminder == "cat");
        auto xm = Load(dir + "/set_christmas.bin");
        assert(CogletSettings::Parse(xm.data(), xm.size(), v));
        assert(v.startup == "christmas" && v.reminder == "christmas");
        auto el = Load(dir + "/set_elf.bin");
        assert(CogletSettings::Parse(el.data(), el.size(), v));
        assert(v.startup == "elf" && v.reminder == "elf");
        auto sn = Load(dir + "/set_snowman.bin");
        assert(CogletSettings::Parse(sn.data(), sn.size(), v));
        assert(v.startup == "snowman" && v.reminder == "snowman");
        auto ae = Load(dir + "/set_aec.bin");
        assert(CogletSettings::Parse(ae.data(), ae.size(), v));
        assert(v.aec == "on" && v.startup.empty());
        auto aeo = Load(dir + "/set_aec_off.bin");
        assert(CogletSettings::Parse(aeo.data(), aeo.size(), v));
        assert(v.aec == "off" && v.reminder == "cat");
        assert(CogletSettings::Parse(xm.data(), xm.size(), v) && v.aec.empty());
        auto dmg = Load(dir + "/set_damaged.bin");
        std::string w;
        assert(!CogletSettings::Parse(dmg.data(), dmg.size(), v, &w) && w == "damaged");
        auto blank = std::vector<uint8_t>(4096, 0xFF);
        assert(!CogletSettings::Parse(blank.data(), blank.size(), v, &w) && w == "empty");
        assert(CogletSettings::ValidWakeWord("hey coglet") && CogletSettings::ValidWakeWord("what's up"));
        assert(!CogletSettings::ValidWakeWord("Hey") && !CogletSettings::ValidWakeWord("hey  coglet") &&
               !CogletSettings::ValidWakeWord("hi") && !CogletSettings::ValidWakeWord(" hey"));
    }
    std::printf("song library parser: all checks passed\n");
    return 0;
}
