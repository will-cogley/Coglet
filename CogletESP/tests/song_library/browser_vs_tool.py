"""Whole browser path (decodeAudioData + resampling + analysis) vs build_music.py."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "coglet_music"))
import build_music as bm  # noqa: E402

bad = 0
for path in sys.argv[1:]:
    out = tempfile.mkdtemp()
    subprocess.run(["node", os.path.join(HERE, "browser_encode.mjs"), path, out], check=True,
                   stdout=subprocess.DEVNULL)
    web = json.load(open(os.path.join(out, "web.json")))
    seconds = min(60.0, float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                              "-of", "csv=p=0", path], stdout=subprocess.PIPE).stdout))
    bands = bm.decode_analysis_pcm("ffmpeg", path, 61)
    n = int(seconds * bm.SR)
    pb, pi = bm.analyse([b[:n] for b in bands], seconds)
    jt = [b[0] for b in web["beats"]]
    pt = [b[0] for b in pb]
    near = sum(1 for t in jt if any(abs(t - u) <= 30 for u in pt))
    ok = abs(pi["felt_bpm"] - web["info"]["felt_bpm"]) <= 1 and pi["preset"] == web["info"]["preset"] \
        and near >= 0.9 * len(jt)
    bad += not ok
    print("{:<22} tool {:>6} {:<9} {:>3} beats | browser {:>6} {:<9} {:>3} beats | {:>3}% within 30 ms {}".format(
        os.path.basename(path)[:22], pi["felt_bpm"], pi["preset"], len(pb), web["info"]["felt_bpm"],
        web["info"]["preset"], len(jt), 100 * near // max(1, len(jt)), "ok" if ok else "DIFFERENT"))
sys.exit(1 if bad else 0)
