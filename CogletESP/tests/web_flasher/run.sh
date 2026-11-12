#!/bin/sh
# End-to-end page test against a simulated Coglet.
# usage: run.sh <four audio files>
set -e
cd "$(dirname "$0")"
W=$(mktemp -d)
g++ -std=c++17 -O1 -I ../../main dump_library.cc ../../main/coglet_music_library.cc -o "$W/dump_library"
python3 test_page.py "$W" "$W/dump_library" "$@"
echo "screenshots: $W"
