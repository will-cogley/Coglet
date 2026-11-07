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


# ----------------------------------------------------------------- choreography
def choreography(name, T):
    ev = sorted(T.events, key=lambda e: e[0])
    moves = []
    section = "intro"
    sway_dir = 1
    ear_dir = 1

    def add(t, move, arg=None):
        moves.append({"t_ms": int(round(t * 1000)), "move": move, "arg": arg})

    beat = T.beat
    for t, kind, value in ev:
        if kind == "section":
            section = value
            if value == "build":
                add(t, "crouch", {"seconds": round(beat * (16 if name == "mecha" else 8), 2)})
            elif value == "outro":
                add(t, "rest")
            continue
        if kind == "end":
            add(t, "pose_end", name)
            continue

        if name == "mecha":
            if kind == "kick":
                if section in ("intro", "outro"):
                    add(t, "nod", "small")
                elif section == "drop":
                    add(t, "nod", "big" if value == "big" else "small")
            elif kind == "zap":
                add(t, "ear_L" if ear_dir > 0 else "ear_R")
                ear_dir = -ear_dir
            elif kind == "snare" and section == "build":
                add(t, "ears")
            elif kind == "snare" and section == "drop":
                add(t, "ear_L" if ear_dir > 0 else "ear_R")
                ear_dir = -ear_dir
            elif kind == "breath":
                add(t, "eyes_squint")
            elif kind == "hit":
                add(t, "eyes_wide")
                add(t, "ears")
                add(t, "mouth_open")
            elif kind == "bar" and section == "drop":
                add(t, "sway_L" if sway_dir > 0 else "sway_R")
                if value % 2 == 0:
                    add(t, "turn_L" if sway_dir > 0 else "turn_R")
                sway_dir = -sway_dir
            elif kind == "tom":
                add(t, ("turn_L", "turn_R", "turn_center")[value])

        elif name == "evil":
            if kind == "toll":
                add(t, "head_roll", "slow")
                add(t, "blink")
            elif kind == "kick" and section in ("verse", "drop"):
                add(t, "nod", "heavy")
            elif kind == "snare":
                add(t, "ears_down")
            elif kind == "bar":
                add(t, "sway_L" if sway_dir > 0 else "sway_R", "slow")
                sway_dir = -sway_dir
            elif kind == "tom":
                add(t, "shudder")
            elif kind == "hit":
                add(t, "eyes_wide")
                add(t, "mouth_open")

        elif name == "cat":
            if kind == "kick":
                add(t, "bounce")
            elif kind == "snare" and section != "build":
                add(t, "ear_L" if ear_dir > 0 else "ear_R")
                ear_dir = -ear_dir
            elif kind == "snare" and section == "build":
                add(t, "ears")
            elif kind == "nya":
                add(t, "head_tilt", "L" if sway_dir > 0 else "R")
                add(t, "blink")
                sway_dir = -sway_dir
            elif kind == "bar" and section == "drop":
                add(t, "turn_L" if value % 2 == 0 else "turn_R")
            elif kind == "hit":
                add(t, "eyes_wide")
                add(t, "ears")

    # Servo safety: never two moves of the same kind closer than 90 ms
    moves.sort(key=lambda m: m["t_ms"])
    filtered = []
    last = {}
    for m in moves:
        if m["move"] in last and m["t_ms"] - last[m["move"]] < 90:
            continue
        last[m["move"]] = m["t_ms"]
        filtered.append(m)
    return filtered


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
