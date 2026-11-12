// Host test: the firmware's library parser on images made by the web page.
#include <cassert>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include "coglet_music.h"

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
    std::printf("song library parser: all checks passed\n");
    return 0;
}
