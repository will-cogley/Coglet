"""Check that the web page's beat analysis (coglet_songs.js) matches the
Music-folder tool (build_music.py) on the same audio."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "coglet_music"))
import build_music as bm  # noqa: E402


def python_result(path, seconds, preset=None, bpm=None):
    bands = bm.decode_analysis_pcm("ffmpeg", path, seconds + 1)
    n = int(seconds * bm.SR)
    return bm.analyse([b[:n] for b in bands], seconds, preset, bpm)


def js_result(path, seconds, preset=None, bpm=None):
    with tempfile.NamedTemporaryFile(suffix=".f32", delete=False) as t:
        raw = t.name
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-t", str(seconds + 1), "-ac", "1",
                    "-ar", str(bm.SR), "-f", "f32le", raw], check=True)
    out = subprocess.run(["node", os.path.join(HERE, "analyse_node.mjs"), raw, str(seconds),
                          preset or "-"] + ([str(bpm)] if bpm else []),
                         check=True, stdout=subprocess.PIPE).stdout
    os.remove(raw)
    return json.loads(out)


def compare(path, seconds, preset=None, bpm=None):
    pb, pi = python_result(path, seconds, preset, bpm)
    j = js_result(path, seconds, preset, bpm)
    jb, ji = j["beats"], j["info"]
    pt = [b[0] for b in pb]
    jt = [b[0] for b in jb]
    near = sum(1 for t in jt if any(abs(t - u) <= 25 for u in pt))
    same_vals = sum(1 for a, b in zip(pb, jb) if tuple(a) == tuple(b))
    print("{:<32} py {:>6} BPM {:<9} {:>3} beats | js {:>6} BPM {:<9} {:>3} beats | {:>3}% beats within 25 ms,"
          " {:>3}% identical".format(os.path.basename(path)[:32], pi["felt_bpm"], pi["preset"], len(pb),
                                    ji["felt_bpm"], ji["preset"], len(jb),
                                    100 * near // max(1, len(jt)), 100 * same_vals // max(1, len(pb))))
    ok = (abs(pi["felt_bpm"] - ji["felt_bpm"]) <= 1.0 and pi["preset"] == ji["preset"]
          and near >= 0.9 * len(jt) and abs(len(pb) - len(jb)) <= 2)
    return ok


if __name__ == "__main__":
    files = sys.argv[1:]
    bad = [f for f in files if not compare(f, 30.0)]
    print("FAIL: " + ", ".join(bad) if bad else "all match")
    sys.exit(1 if bad else 0)
