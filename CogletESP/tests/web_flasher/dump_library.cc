// Prints the songs the firmware would load from a song area image (JSON).
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include "coglet_music.h"
namespace CogletMusic { const Song* const kSongs = nullptr; const size_t kSongCount = 0; }
int main(int, char** argv) {
    std::ifstream f(argv[1], std::ios::binary);
    std::vector<uint8_t> img((std::istreambuf_iterator<char>(f)), {});
    std::vector<CogletMusic::Song> songs;
    std::string why;
    size_t skipped = 0;
    bool ok = CogletMusic::ParseLibrary(img.data(), img.size(), songs, &why, &skipped);
    std::printf("{\"ok\":%s,\"why\":\"%s\",\"skipped\":%zu,\"songs\":[", ok ? "true" : "false", why.c_str(), skipped);
    for (size_t i = 0; i < songs.size(); ++i) {
        const auto& s = songs[i];
        std::printf("%s{\"name\":\"%s\",\"preset\":\"%s\",\"bpm\":%u,\"beats\":%zu,\"ogg\":%zu,\"first_beat\":%u}",
                    i ? "," : "", s.name, s.PresetName(), s.bpm, s.beat_count, s.ogg_size,
                    s.beat_count ? s.beats[0].t_ms : 0);
    }
    std::printf("]}\n");
    return 0;
}
