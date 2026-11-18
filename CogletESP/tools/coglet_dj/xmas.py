"""Coglet Christmas tracks (public-domain carols, our own arrangements).

  lyrical  Silent Night (Gruber, 1818)          piano, strings, celesta
  classic  Jingle Bells (Pierpont, 1857)        sleigh bells, piano, bass, glockenspiel, "ho ho ho"
  grand    Joy to the World (Antioch, 1839)     organ, brass, choir, timpani, cymbals

python3 xmas.py [lyrical|classic|grand ...]  ->  out/xmas_<name>.ogg / _preview.mp3
"""
import os
import subprocess
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

import synth as S

N = S.note
SR = S.SR
RNG = np.random.default_rng(25)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


class Song(S.Track):
    """Track with a free meter: t(bar, beat) uses `beats_per_bar`."""

    def __init__(self, bpm, seconds, beats_per_bar):
        super().__init__(bpm, seconds)
        self.bpb = beats_per_bar
        self.reverb = {}
        self.gains = {}
        self.glue = 1.4

    def t(self, bar, beat=0.0):
        return (bar * self.bpb + beat) * self.beat



# ------------------------------------------------------------------ scores
# Shared with choreo_xmas.py, so every dance move lands on a real note.
# (bar chord, melody) after the 2-bar intro; melody: [(beats, note)]
LYRICAL_VERSE = [("C", [(1.5, "G4"), (0.5, "A4"), (1, "G4")]), ("C", [(3, "E4")]),
         ("C", [(1.5, "G4"), (0.5, "A4"), (1, "G4")]), ("C", [(3, "E4")]),
         ("G7", [(2, "D5"), (1, "D5")]), ("G7", [(3, "B4")]),
         ("C", [(2, "C5"), (1, "C5")]), ("C", [(3, "G4")]),
         ("G7", [(2, "D5"), (1, "D5")]), ("G7", [(1.5, "F5"), (0.5, "D5"), (1, "B4")]),
         ("C", [(3, "C5")]), ("C", [(3, "E5")]),
         ("C", [(1.5, "C5"), (0.5, "G4"), (1, "E4")]), ("G7", [(1.5, "G4"), (0.5, "F4"), (1, "D4")]),
         ("C", [(3, "C4")])]

CLASSIC_PLAN = ["G", "G", "G", "G", "C", "G", "A7", "D7", "G", "G", "G", "G", "C", "G", "D7", "G"]
_JINGLE = [(1, "B4"), (1, "B4"), (2, "B4")]
CLASSIC_TUNE = [_JINGLE, _JINGLE, [(1, "B4"), (1, "D5"), (1.5, "G4"), (0.5, "A4")], [(4, "B4")],
        [(1, "C5"), (1, "C5"), (1.5, "C5"), (0.5, "C5")],
        [(1, "C5"), (1, "B4"), (1, "B4"), (0.5, "B4"), (0.5, "B4")],
        [(1, "B4"), (1, "A4"), (1, "A4"), (1, "B4")], [(2, "A4"), (2, "D5")],
        _JINGLE, _JINGLE, [(1, "B4"), (1, "D5"), (1.5, "G4"), (0.5, "A4")], [(4, "B4")],
        [(1, "C5"), (1, "C5"), (1.5, "C5"), (0.5, "C5")],
        [(1, "C5"), (1, "B4"), (1, "B4"), (0.5, "B4"), (0.5, "B4")],
        [(1, "D5"), (1, "D5"), (1, "C5"), (1, "A4")], [(4, "G4")]]

# melody per 2/4 bar (beats are quarters)
GRAND_TUNE = [
    [(1, "D5"), (0.75, "C#5"), (0.25, "B4")],          # Joy to the
    [(1.5, "A4"), (0.5, "G4")],                        # world! the
    [(1, "F#4"), (1, "E4")],                           # Lord is
    [(1.5, "D4"), (0.5, "A4")],                        # come! Let
    [(1.5, "B4"), (0.5, "B4")],                        # earth re-
    [(1.5, "C#5"), (0.5, "C#5")],                      # ceive her
    [(1.5, "D5"), (0.5, "D5")],                        # King; Let
    [(0.5, "D5"), (0.5, "C#5"), (0.5, "B4"), (0.5, "A4")],   # ev-'ry heart pre-
    [(0.75, "A4"), (0.25, "G4"), (0.5, "F#4"), (0.5, "D5")],  # pare Him room, And
    [(0.5, "D5"), (0.5, "C#5"), (0.5, "B4"), (0.5, "A4")],   # heav'n and na-ture
    [(0.75, "A4"), (0.25, "G4"), (0.5, "F#4"), (0.5, "F#4")],  # sing, And
    [(0.5, "F#4"), (0.5, "F#4"), (0.5, "F#4"), (0.25, "F#4"), (0.25, "G4")],  # heav'n and na-ture
    [(1.5, "A4"), (0.25, "G4"), (0.25, "F#4")],        # sing, and
    [(0.5, "E4"), (0.5, "E4"), (0.5, "E4"), (0.25, "E4"), (0.25, "F#4")],     # heav'n and na-ture
    [(1.5, "G4"), (0.25, "F#4"), (0.25, "E4")],        # sing, And
    [(0.5, "D4"), (1.0, "D5"), (0.5, "B4")],           # heav'n, and
    [(0.75, "A4"), (0.25, "G4"), (0.5, "F#4"), (0.5, "G4")],  # heav'n, and na-
    [(1, "F#4"), (1, "E4")],                           # ture
    [(2, "D4")],                                       # sing.
]


# ------------------------------------------------------------------ instruments
def sleigh_bell(vel=1.0, length=0.22):
    """A few small metal bells shaken once: inharmonic partials + jingle noise."""
    n = int(length * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for _ in range(4):                               # several bells, slightly late
        start = int(RNG.uniform(0, 0.012) * SR)
        f = RNG.uniform(2300, 3400)
        for ratio, amp in ((1.0, 1.0), (1.47, 0.6), (2.09, 0.4), (2.76, 0.25)):
            x = np.sin(2 * np.pi * f * ratio * t + RNG.uniform(0, 6.3)) * np.exp(-t / RNG.uniform(0.03, 0.07))
            out[start:] += amp * x[:n - start]
    out += S.highpass(S.noise(n), 6000) * np.exp(-t / 0.02) * 0.8
    return out * 0.08 * vel


def glock(midi, length=0.8, vel=0.6):
    return S.fm_bell(midi, length, ratio=3.0, index=0.9, tau=0.45) * vel


def celesta(midi, length=1.2, vel=0.5):
    return S.fm_bell(midi, length, ratio=4.0, index=0.7, tau=0.6) * vel


def upright_bass(midi, length=0.5, vel=0.8):
    """Plucked double bass that still reads on a small speaker (2nd harmonic)."""
    n = int((length + 0.15) * SR)
    t = np.arange(n) / SR
    f = S.midi_hz(midi)
    x = (np.sin(2 * np.pi * f * t) + 0.55 * np.sin(4 * np.pi * f * t) + 0.25 * np.sin(6 * np.pi * f * t))
    env = np.exp(-t / 0.35) * np.minimum(1, t / 0.004)
    thump = S.lowpass(S.noise(n), 900) * np.exp(-t / 0.01) * 0.3
    return S.soft_clip((x * env + thump) * vel, 1.3) * 0.6


def strings(midis, length, vel=0.35):
    """Soft string pad: detuned saws, slow attack, dark filter."""
    n = int((length + 0.8) * SR)
    out = np.zeros(n)
    for m in midis:
        for d in (-0.07, 0.0, 0.08):
            out += S.saw(S.midi_hz(m + d), n, RNG.uniform(0, 1))
    out = S.lowpass(out, 1900)
    out /= max(len(midis) * 3, 1)
    return out * S.env_adsr(n, 0.5, 0.4, 0.85, 0.8, length) * vel


def brass(midis, length, vel=0.6):
    """Brass section: saws whose filter opens on the attack ('blat')."""
    n = int((length + 0.25) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in midis:
        f = S.midi_hz(m) * (1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.4))
        ph = np.cumsum(f) / SR
        for d in (-0.0015, 0.0015):
            out += 2 * ((ph * (1 + d)) % 1.0) - 1
    out /= max(len(midis) * 2, 1)
    # "blat": a dark start, a bright burst, then a warm sustain (crossfaded filters)
    dark, bright, warm = S.lowpass(out, 700), S.lowpass(out, 3400), S.lowpass(out, 2100)
    a = np.clip(t / 0.03, 0, 1)
    b = np.clip((t - 0.03) / 0.12, 0, 1)
    y = dark * (1 - a) + (bright * (1 - b) + warm * b) * a
    return y * S.env_adsr(n, 0.03, 0.15, 0.8, 0.2, length) * vel


def timpani(midi, length=1.2, vel=0.8):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = S.midi_hz(midi)
    x = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.5 * t) + 0.35 * np.sin(2 * np.pi * f * 1.98 * t))
    x *= np.exp(-t / 0.55)
    hit = S.bandpass(S.noise(n), 150, 1200) * np.exp(-t / 0.015) * 0.5
    return S.soft_clip((x + hit) * vel, 1.8) * 0.7


def santa_ho(f0=105.0, count=3, gap=0.09, each=0.30):
    """'Ho ho ho' from a glottal pulse train through /o/ formants. Deliberately
    a little robotic: this is Coglet doing Santa."""
    seg = int(each * SR)
    total = int(count * (each + gap) * SR) + int(0.4 * SR)
    out = np.zeros(total)
    formants = ((450, 70, 1.0), (800, 80, 0.55), (2830, 120, 0.12))
    for k in range(count):
        t = np.arange(seg) / SR
        pitch = f0 * (1.12 - 0.15 * t / each) * (1 - 0.06 * k)       # each "ho" falls, last is lowest
        ph = np.cumsum(pitch) / SR
        src = (2 * (ph % 1.0) - 1) + 0.25 * S.noise(seg)              # buzzy source + breath
        breath = S.noise(seg) * np.exp(-t / 0.05)                     # the /h/
        voice = np.zeros(seg)
        for fc, bw, g in formants:
            voice += g * S.bandpass(src, fc - bw, fc + bw, order=2)
            voice += 0.4 * g * S.bandpass(breath, fc - bw * 2, fc + bw * 2, order=2)
        env = np.minimum(1, t / 0.035) * np.exp(-np.maximum(0, t - each * 0.55) / 0.07)
        i = int(k * (each + gap) * SR)
        out[i:i + seg] += voice * env
    out /= np.max(np.abs(out)) + 1e-9
    return out * 0.9


# ------------------------------------------------------------------ helpers
def put(T, bus, t, audio, gain=1.0, jitter=0.008):
    T.add(bus, t + RNG.uniform(-jitter, jitter), audio, gain)


def melody_line(T, start_bar, notes):
    """notes: [(beats, name|None), ...] played back to back; yields (t, midi, beats)."""
    beat = 0.0
    for beats, name in notes:
        if name is not None:
            yield T.t(start_bar, beat), N(name), beats
        beat += beats


# ------------------------------------------------------------------ lyrical
def lyrical():
    """Silent Night, C major, 3/4, quarter = 104. Piano with a broken-chord left
    hand; strings join for 'All is calm'; celesta doubles 'Sleep in heavenly
    peace'; ends on a long C chord with a bell."""
    T = Song(bpm=104, seconds=31.5, beats_per_bar=3)
    chords = {"C": ("C3", ["G3", "E4", "G3", "C4", "G3"]), "G7": ("G2", ["D3", "F3", "B3", "F3", "D3"]),
              "F": ("F2", ["C3", "A3", "C4", "A3", "C3"])}
    intro = ["C", "F"]
    verse = LYRICAL_VERSE

    def left_hand(bar, cname, vel):
        root, tones = chords[cname]
        put(T, "keys", T.t(bar), S.grand(N(root), 3 * T.beat, vel + 0.08))
        for i, tone in enumerate(tones):
            put(T, "keys", T.t(bar, 0.5 + i * 0.5), S.grand(N(tone), 1.4 * T.beat, vel * (0.9 if i % 2 else 0.75)))

    for bar, c in enumerate(intro):
        left_hand(bar, c, 0.38)
    for i, (c, notes) in enumerate(verse):
        bar = 2 + i
        last = i == len(verse) - 1
        sleep = i >= 8
        if not last:
            left_hand(bar, c, 0.36 + (0.06 if sleep else 0))
        if 4 <= i < len(verse) - 1:
            root, tones = chords[c]
            pad = [N(root) + 12, N(tones[1]), N(tones[2])]
            T.add("pad", T.t(bar), strings(pad, 3 * T.beat, 0.32 if sleep else 0.24))
        for t, m, beats in melody_line(T, bar, notes):
            ln = beats * T.beat
            put(T, "keys", t, S.grand(m + 12 if False else m, ln * 1.1, 0.62 if sleep else 0.55), jitter=0.006)
            if sleep:
                T.add("bells", t, celesta(m + 12, max(ln, 0.6), 0.35))
        if last:
            t0 = T.t(bar)
            for k, nm in enumerate(["C2", "C3", "G3", "C4", "E4", "G4"]):
                put(T, "keys", t0 + k * 0.07, S.grand(N(nm), 6.0, 0.45 - 0.03 * k), jitter=0)
            T.add("pad", t0, strings([N("C3"), N("G3"), N("E4")], 4.0, 0.3))
            T.add("bells", t0 + 0.6, celesta(N("C6"), 3.0, 0.4))
            T.add("bells", t0 + 0.95, celesta(N("G5"), 3.0, 0.3))
    T.reverb = {"keys": 0.34, "pad": 0.45, "bells": 0.5}
    T.gains = {"keys": 1.0, "pad": 0.55, "bells": 0.5}
    T.glue = 1.15
    return T


# ------------------------------------------------------------------ classic
def classic():
    """Jingle Bells chorus, G major, 4/4, 136 BPM. One-bar intro of sleigh bells
    and Coglet's 'ho ho ho', then the chorus twice: stride piano, plucked bass,
    brushed snare, sleigh bells on every 8th, glockenspiel on the tune."""
    T = Song(bpm=136, seconds=32.0, beats_per_bar=4)
    chords = {"G": ("G2", "D3", ["G3", "B3", "D4"]), "C": ("C3", "G2", ["C4", "E4", "G4"]),
              "A7": ("A2", "E3", ["G3", "C#4", "E4"]), "D7": ("D3", "A2", ["F#3", "C4", "D4"])}
    plan, tune = CLASSIC_PLAN, CLASSIC_TUNE

    # intro: a sleigh-bell shake and "ho ho ho"
    for k in range(16):
        T.add("bells", T.t(0, k * 0.25), sleigh_bell(0.5 + 0.5 * k / 16))
    T.add("voice", T.t(0, 0.4), santa_ho())

    for i, cname in enumerate(plan):
        bar = 1 + i
        root, fifth, triad = chords[cname]
        last = i == len(plan) - 1
        # stride piano: bass note on 1 & 3, chord on 2 & 4
        for beat, note_ in ((0, root), (2, fifth)):
            put(T, "keys", T.t(bar, beat), S.grand(N(note_), 0.9 * T.beat, 0.55), jitter=0.004)
            T.add("bass", T.t(bar, beat), upright_bass(N(note_) - 12 if N(note_) >= N("C3") else N(note_), 0.9 * T.beat, 0.9))
        for beat in (1, 3):
            for nm in triad:
                put(T, "keys", T.t(bar, beat), S.grand(N(nm), 0.5 * T.beat, 0.42), jitter=0.004)
        if not last:
            T.add("drums", T.t(bar, 1), S.snare(0.16, tone=210, snap=0.4), 0.22)
            T.add("drums", T.t(bar, 3), S.snare(0.16, tone=210, snap=0.4), 0.22)
            for k in range(8):
                T.add("bells", T.t(bar, k * 0.5), sleigh_bell(1.0 if k % 2 == 0 else 0.65))
        for t, m, beats in melody_line(T, bar, tune[i]):
            ln = beats * T.beat
            put(T, "keys", t, S.grand(m, ln * 0.95, 0.7), jitter=0.004)
            T.add("glock", t, glock(m + 12, max(0.5, ln), 0.42 if i < 8 else 0.55))
        if last:
            t0 = T.t(bar)
            for k, nm in enumerate(["G2", "D3", "G3", "B3", "D4", "G4"]):
                put(T, "keys", t0 + k * 0.03, S.grand(N(nm), 2.6, 0.6), jitter=0)
            for k in range(10):
                T.add("bells", t0 + k * 0.11, sleigh_bell(1.0 - k * 0.08))
            T.add("glock", t0 + 0.3, glock(N("G6"), 2.0, 0.5))
    T.reverb = {"keys": 0.18, "glock": 0.3, "bells": 0.15, "voice": 0.22}
    T.gains = {"keys": 0.95, "bass": 0.7, "bells": 0.8, "glock": 0.45, "drums": 1.0, "voice": 0.55}
    T.glue = 1.5
    return T


# ------------------------------------------------------------------ grand
def grand():
    """Joy to the World, D major, 2/4, quarter = 84. Brass fanfare and timpani
    roll, then the hymn on organ + brass with a choir underneath, cymbal at the
    top, broad ritardando into the last chord."""
    T = Song(bpm=84, seconds=32.5, beats_per_bar=2)
    tune = GRAND_TUNE
    harmony = ["D", "D", "G-A", "D", "G", "A", "D", "D", "D", "D", "D", "D", "D", "A", "A", "G", "D", "A", "D"]
    chord_notes = {"D": ["D3", "A3", "F#4"], "G": ["G2", "D3", "B3"], "A": ["A2", "E3", "C#4"]}
    bass_note = {"D": "D2", "G": "G2", "A": "A2"}
    intro = 2
    # intro fanfare: timpani roll swelling into a brass D chord
    for k in range(14):
        T.add("perc", T.t(0, k * 0.125), timpani(N("A2"), 0.5, 0.25 + 0.5 * k / 14))
    T.add("brass", T.t(1), brass([N("D4"), N("F#4"), N("A4"), N("D5")], 2 * T.beat * 0.95, 0.7))
    T.add("perc", T.t(1), timpani(N("D2"), 1.4, 1.0))
    T.add("perc", T.t(1), S.crash(2.0), 0.35)

    def chord_at(bar, beat, name, beats, last=False):
        t = T.t(bar, beat)
        ln = beats * T.beat * (1.0 if not last else 2.6)
        T.add("organ", t, S.organ([N(x) for x in chord_notes[name]] + [N(bass_note[name])], ln, (1.0, 0.9, 0.7, 0.5, 0.35, 0.25)))
        T.add("choir", t, S.choir([N(x) + 12 for x in chord_notes[name]], ln * 1.05))
        T.add("brass", t, brass([N(x) for x in chord_notes[name][1:]], ln * 0.9, 0.35))
        T.add("perc", t, timpani(N(bass_note[name]) + 12, 1.0, 0.45 if not last else 1.0))

    for i, notes in enumerate(tune):
        bar = intro + i
        last = i == len(tune) - 1
        h = harmony[i]
        if "-" in h:
            a, b = h.split("-")
            chord_at(bar, 0, a, 1)
            chord_at(bar, 1, b, 1)
        else:
            chord_at(bar, 0, h, 2, last)
        for t, m, beats in melody_line(T, bar, notes):
            ln = beats * T.beat
            if last:
                ln *= 2.6
            T.add("lead", t, brass([m], ln * 0.92, 0.75))
            T.add("lead", t, S.organ([m + 12], ln * 0.95, (0.6, 0.5, 0.3, 0.2, 0.1, 0.05)), 0.5)
        if i in (0, 15) or last:
            T.add("perc", T.t(bar), S.crash(2.2), 0.3)
        if last:
            T.add("bells", T.t(bar), S.fm_bell(N("D5"), 4.0, ratio=2.76, index=2.0, tau=1.6), 0.4)
            T.add("bells", T.t(bar), S.fm_bell(N("A4"), 4.0, ratio=2.76, index=2.0, tau=1.6), 0.3)
    T.reverb = {"organ": 0.45, "choir": 0.5, "brass": 0.35, "lead": 0.3, "perc": 0.3, "bells": 0.5}
    T.gains = {"organ": 0.55, "choir": 0.35, "brass": 0.5, "lead": 0.9, "perc": 0.6, "bells": 0.5}
    T.glue = 0.9
    return T


TRACKS = {"lyrical": lyrical, "classic": classic, "grand": grand}


# ------------------------------------------------------------------ short sounds
def startup():
    """~3 s: a sleigh-bell shake, the first two 'jingle bells' figures on
    glockenspiel + piano, then a bright G chord with a celesta sparkle."""
    T = Song(bpm=200, seconds=3.3, beats_per_bar=4)
    for k in range(8):                                   # shake, getting louder
        T.add("bells", k * 0.045, sleigh_bell(0.35 + 0.65 * k / 8, 0.18))
    t0 = 0.36
    figure = [(0, "B5"), (1, "B5"), (2, "B5"), (4, "B5"), (5, "B5"), (6, "B5")]
    for beat, nm in figure:
        t = t0 + beat * T.beat
        long_ = beat in (2, 6)
        T.add("glock", t, glock(N(nm), 0.9 if long_ else 0.4, 0.55 if long_ else 0.45))
        put(T, "keys", t, S.grand(N(nm) - 12, (2 if long_ else 1) * T.beat, 0.55), jitter=0.003)
        T.add("bells", t, sleigh_bell(0.6, 0.15))
    t1 = t0 + 8 * T.beat
    for k, nm in enumerate(["G3", "D4", "G4", "B4", "D5", "G5"]):
        put(T, "keys", t1 + k * 0.025, S.grand(N(nm), 1.6, 0.55), jitter=0)
    for k, nm in enumerate(["G6", "B6", "D7"]):
        T.add("glock", t1 + 0.08 + k * 0.07, celesta(N(nm), 1.2, 0.3))
    for k in range(6):
        T.add("bells", t1 + k * 0.08, sleigh_bell(0.7 - k * 0.1, 0.2))
    T.reverb = {"keys": 0.25, "glock": 0.35, "bells": 0.2}
    T.gains = {"keys": 0.9, "glock": 0.6, "bells": 0.8}
    T.glue = 1.3
    T.level_db = -1.5      # same loudness as the other startup sounds
    return T


def reminder():
    """~2.6 s: two 'ding-dong' church-bell pairs over sleigh bells, so a
    reminder is noticed without being harsh."""
    T = Song(bpm=120, seconds=2.7, beats_per_bar=4)

    def church(midi, vel):
        body = S.fm_bell(midi, 2.0, ratio=2.76, index=1.8, tau=0.9) * 0.8
        top = glock(midi + 12, 1.0, 0.35)
        body[:len(top)] += top
        return body * vel

    for i, (t, nm) in enumerate(((0.05, "G5"), (0.45, "D5"), (1.05, "G5"), (1.45, "D5"))):
        T.add("bells", t, church(N(nm), 0.9 if i % 2 == 0 else 0.75))
    for k in range(18):
        T.add("jingle", 0.05 + k * 0.105, sleigh_bell(0.75 if k % 2 == 0 else 0.45, 0.16))
    T.add("bells", 1.9, celesta(N("G6"), 0.8, 0.25))
    T.reverb = {"bells": 0.3, "jingle": 0.15}
    T.gains = {"bells": 1.0, "jingle": 0.55}
    T.glue = 1.1
    T.level_db = -4.5      # same loudness as the other reminder sounds
    return T


TRACKS.update({"startup": startup, "reminder": reminder})


def render(name):
    # Same random stream for every track, whatever else ran before, so a
    # track always renders the same (the approved files are in out/approved).
    global RNG
    RNG = np.random.default_rng(25)
    T = TRACKS[name]()
    mix = np.zeros(T.n)
    for bus, buf in T.buses.items():
        x = S.reverb(buf, wet=T.reverb[bus]) if bus in T.reverb else buf
        mix += x * T.gains.get(bus, 1.0)
    mix = S.master(mix, glue=T.glue) * 10 ** (getattr(T, "level_db", 0.0) / 20)
    mix24 = signal.resample_poly(mix, 1, 2)
    os.makedirs(OUT, exist_ok=True)
    base = os.path.join(OUT, "xmas_" + name)
    wavfile.write(base + "_24k.wav", 24000, (np.clip(mix24, -1, 1) * 32767).astype(np.int16))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", base + "_24k.wav", "-c:a", "libopus", "-b:a", "32k",
                    "-ar", "24000", "-ac", "1", "-frame_duration", "60", "-application", "audio", base + ".ogg"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", base + ".ogg", "-c:a", "libmp3lame", "-b:a", "128k",
                    base + "_preview.mp3"], check=True)
    rms = 20 * np.log10(np.sqrt(np.mean(mix24 ** 2)) + 1e-12)
    print("{:<8} {:>4} BPM {:.1f}s ogg={:.0f} KB rms={:.1f} dBFS".format(
        name, T.bpm, T.n / SR, os.path.getsize(base + ".ogg") / 1024, rms))


if __name__ == "__main__":
    for n in sys.argv[1:] or list(TRACKS):
        render(n)
