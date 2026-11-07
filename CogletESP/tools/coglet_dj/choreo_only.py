"""Regenerate only the choreography JSONs (music untouched).
python3 choreo_only.py [mecha|evil|cat ...]
"""
import json, os, sys
import synth as S
from tracks import TRACKS
from choreo import choreography
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
for n in sys.argv[1:] or list(TRACKS):
    T = TRACKS[n]()
    moves = choreography(n, T)
    with open(os.path.join(OUT, n + "_choreo.json"), "w") as f:
        json.dump({"track": n, "bpm": T.bpm, "duration_ms": int(T.n / S.SR * 1000),
                   "moves": moves}, f, ensure_ascii=False, indent=1)
    kinds = {}
    for m in moves: kinds[m["move"]] = kinds.get(m["move"], 0) + 1
    print(n, len(moves), "moves", dict(sorted(kinds.items())))
