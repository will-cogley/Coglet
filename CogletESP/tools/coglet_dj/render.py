"""Render Coglet dance tracks + choreography timelines.

python3 render.py [mecha|evil|cat ...]
Outputs in out/: <name>.ogg (device format: Opus mono 24 kHz, 60 ms packets),
<name>_preview.mp3 (decoded from the .ogg, i.e. what Coglet plays),
<name>_choreo.json, and timeline.md.
"""
import json
import os
import subprocess
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

import synth as S
from tracks import TRACKS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


from choreo import choreography  # noqa: E402  (v2: denser, eyes included)


# ----------------------------------------------------------------- render
def mixdown(T):
    mix = np.zeros(T.n)
    for name, buf in T.buses.items():
        x = buf
        if name in getattr(T, "sidechain", {}):
            kicks, depth = T.sidechain[name]
            x = S.sidechain(x, kicks, depth=depth)
        if name in getattr(T, "reverb", {}):
            x = S.reverb(x, wet=T.reverb[name])
        mix += x * T.gains.get(name, 1.0)
    return S.master(mix)


def loudness_report(x, sr):
    rms = np.sqrt(np.mean(x ** 2))
    peak = np.max(np.abs(x))
    # energy share above/below 150 Hz (tiny-speaker sanity check)
    f, p = signal.welch(x, sr, nperseg=8192)
    low = p[f < 150].sum() / p.sum()
    return "peak={:.2f} rms={:.1f} dBFS sub150Hz_energy={:.0f}%".format(peak, 20 * np.log10(rms + 1e-12), low * 100)


def render(name):
    T = TRACKS[name]()
    mix48 = mixdown(T)
    mix24 = signal.resample_poly(mix48, 1, 2)
    os.makedirs(OUT, exist_ok=True)
    wav = os.path.join(OUT, name + "_24k.wav")
    wavfile.write(wav, 24000, (np.clip(mix24, -1, 1) * 32767).astype(np.int16))
    ogg = os.path.join(OUT, name + ".ogg")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libopus",
                    "-b:a", "32k", "-ar", "24000", "-ac", "1", "-frame_duration", "60",
                    "-application", "audio", ogg], check=True)
    mp3 = os.path.join(OUT, name + "_preview.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", ogg, "-c:a", "libmp3lame",
                    "-b:a", "128k", mp3], check=True)
    moves = choreography(name, T)
    with open(os.path.join(OUT, name + "_choreo.json"), "w") as f:
        json.dump({"track": name, "bpm": T.bpm, "duration_ms": int(T.n / S.SR * 1000),
                   "moves": moves}, f, ensure_ascii=False, indent=1)
    size = os.path.getsize(ogg)
    print("{:<6} {:>4} BPM  {:.1f}s  ogg={:.0f} KB  moves={}  {}".format(
        name, T.bpm, T.n / S.SR, size / 1024, len(moves), loudness_report(mix24, 24000)))
    return T, moves


if __name__ == "__main__":
    names = sys.argv[1:] or list(TRACKS)
    for n in names:
        render(n)
