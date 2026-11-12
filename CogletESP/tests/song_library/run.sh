#!/bin/sh
# Song library + in-browser song conversion checks. Needs: ffmpeg, node, g++,
# Python Playwright with Chromium (and PLAYWRIGHT_MODULE pointing at the Node
# playwright package if it isn't installed where Node finds it).
set -e
cd "$(dirname "$0")"
W=$(mktemp -d)
ffmpeg -v error -y -f lavfi -i "sine=frequency=220:duration=8" -ac 1 -ar 24000 -c:a libopus -b:a 32k -frame_duration 60 "$W/a.ogg"
ffmpeg -v error -y -f lavfi -i "sine=frequency=440:duration=6" -ac 1 -ar 24000 -c:a libopus -b:a 32k -frame_duration 60 "$W/b.ogg"
node make_images.mjs "$W"
g++ -std=c++17 -Wall -Wextra -I ../../main test_library.cc ../../main/coglet_music_library.cc -o "$W/t"
"$W/t" "$W"
if [ "$#" -gt 0 ]; then
  python3 compare_analysis.py "$@"       # same beats as build_music.py
  python3 browser_vs_tool.py "$@"        # whole browser path (decode, resample, analyse, encode)
fi
