"""Coglet Elf edition tracks (public-domain carols, our own arrangements).

  workshop  Deck the Halls (Welsh, trad.)                xylophone, pizzicato, woodblock, toy hammers
  mischief  God Rest Ye Merry Gentlemen (English, trad.)  tiptoe pizzicato, bassoon, clarinet, then bold
  party     We Wish You a Merry Christmas (English, trad.) fiddle, accordion, oom-pah, tambourine

python3 elf.py [workshop|mischief|party|startup|reminder ...]  ->  out/elf_<name>.ogg / _preview.mp3
"""
import os
import subprocess
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

import synth as S
import xmas as X

N = S.note
SR = S.SR
RNG = np.random.default_rng(31)
OUT = X.OUT
Song, put, melody_line = X.Song, X.put, X.melody_line


# ------------------------------------------------------------------ scores
# Shared with the choreography, so every dance move lands on a real note.
# One list per bar: [(beats, note | None)].

# Deck the Halls, G major, 4/4: A A B A' (4 bars each)
_DECK_A = [[(1.5, "D5"), (0.5, "C5"), (1, "B4"), (1, "A4")],
           [(1, "G4"), (1, "A4"), (1, "B4"), (1, "G4")],
           [(0.5, "A4"), (0.5, "B4"), (0.5, "C5"), (0.5, "A4"), (1.5, "B4"), (0.5, "A4")],
           [(1, "G4"), (1, "F#4"), (2, "G4")]]
_DECK_B = [[(1.5, "A4"), (0.5, "B4"), (1, "C5"), (1, "A4")],
           [(1.5, "B4"), (0.5, "C5"), (1, "D5"), (1, "A4")],
           [(0.5, "B4"), (0.5, "C#5"), (1, "D5"), (0.5, "E5"), (0.5, "F#5"), (1, "G5")],
           [(1, "F#5"), (1, "E5"), (2, "D5")]]
_DECK_A2 = [_DECK_A[0], _DECK_A[1],
            [(0.5, "E5"), (0.5, "E5"), (0.5, "E5"), (0.5, "E5"), (1.5, "D5"), (0.5, "C5")],
            [(1, "B4"), (1, "A4"), (2, "G4")]]
DECK_TUNE = _DECK_A + _DECK_A + _DECK_B + _DECK_A2
# chords per bar: [(beat, chord)]
_DA = [[(0, "G")], [(0, "G"), (2, "C"), (3, "G")], [(0, "Am"), (2, "D7")], [(0, "G"), (1, "D7"), (2, "G")]]
_DB = [[(0, "D7")], [(0, "G"), (2, "D")], [(0, "A7"), (2, "D")], [(0, "D"), (1, "A7"), (2, "D")]]
_DA2 = [[(0, "G")], [(0, "G"), (2, "C"), (3, "G")], [(0, "C"), (2, "D7")], [(0, "G"), (1, "D7"), (2, "G")]]
DECK_CHORDS = _DA + _DA + _DB + _DA2
# the "fa la la" bars (toy hammers answer them)
DECK_FALALA = [2, 3, 6, 7, 10, 11, 14, 15]

# God Rest Ye Merry Gentlemen, E minor, 4/4, pickup E4 on beat 4 of the intro bar
_GR_A = [[(1, "E4"), (1, "B4"), (1, "B4"), (1, "A4")],
         [(1, "G4"), (1, "F#4"), (1, "E4"), (1, "D4")],
         [(1, "E4"), (1, "F#4"), (1, "G4"), (1, "A4")]]
GOD_REST_TUNE = (_GR_A + [[(3, "B4"), (1, "E4")]] +
                 _GR_A + [[(3, "B4"), (1, "B4")]] +
                 [[(1, "C5"), (1, "A4"), (1, "B4"), (1, "C5")],
                  [(1, "D5"), (1, "E5"), (1, "B4"), (1, "A4")],
                  [(1, "G4"), (1, "E4"), (1, "F#4"), (1, "G4")],
                  [(2, "A4"), (1, "G4"), (1, "A4")],
                  [(2, "B4"), (1, "C5"), (1, "B4")],
                  [(1, "B4"), (1, "A4"), (1, "G4"), (1, "F#4")],
                  [(2, "E4"), (1, "G4"), (1, "F#4")],
                  [(2, "E4"), (2, "A4")],
                  [(1, "G4"), (1, "A4"), (1, "B4"), (1, "C5")],
                  [(1, "B4"), (1, "A4"), (1, "G4"), (1, "F#4")],
                  [(4, "E4")]])
GOD_REST_CHORDS = ([[(0, "Em")], [(0, "Em"), (2, "Bm")], [(0, "Em"), (2, "D")], [(0, "Em")]] * 2 +
                   [[(0, "Am")], [(0, "G"), (2, "Em")], [(0, "Em"), (2, "G")], [(0, "D")],
                    [(0, "G"), (2, "C")], [(0, "Em"), (2, "B7")], [(0, "Em"), (2, "G")], [(0, "Em"), (2, "Am")],
                    [(0, "G"), (2, "Am")], [(0, "Em"), (2, "B7")], [(0, "Em")]])
GOD_REST_BOLD = 8      # from this tune bar on, the elf stops tiptoeing

# We Wish You a Merry Christmas, G major, 3/4, pickup D4 on beat 3 of the intro
_WW_VERSE = [[(1, "G4"), (0.5, "G4"), (0.5, "A4"), (0.5, "G4"), (0.5, "F#4")],
             [(1, "E4"), (1, "E4"), (1, "E4")],
             [(1, "A4"), (0.5, "A4"), (0.5, "B4"), (0.5, "A4"), (0.5, "G4")],
             [(1, "F#4"), (1, "D4"), (1, "D4")],
             [(1, "B4"), (0.5, "B4"), (0.5, "C5"), (0.5, "B4"), (0.5, "A4")],
             [(1, "G4"), (1, "E4"), (0.5, "D4"), (0.5, "D4")],
             [(1, "E4"), (1, "A4"), (1, "F#4")],
             [(2, "G4"), (1, "D4")]]
_WW_CHORUS = [[(1, "G4"), (1, "G4"), (1, "G4")],
              [(2, "F#4"), (1, "F#4")],
              [(1, "G4"), (1, "F#4"), (1, "E4")],
              [(2, "D4"), (1, "A4")],
              [(1, "B4"), (1, "A4"), (1, "G4")],
              [(1, "D5"), (1, "D4"), (0.5, "D4"), (0.5, "D4")],
              [(1, "E4"), (1, "A4"), (1, "F#4")],
              [(2, "G4"), (1, "D4")]]
_WW_VC = [[(0, "G")], [(0, "C")], [(0, "A7")], [(0, "D")], [(0, "B7")], [(0, "Em"), (2, "C")],
          [(0, "C"), (1, "D7")], [(0, "G")]]
_WW_CC = [[(0, "G")], [(0, "D")], [(0, "G"), (1, "D"), (2, "Em")], [(0, "D")],
          [(0, "G"), (1, "D"), (2, "Em")], [(0, "G"), (1, "D")], [(0, "C"), (1, "D7")], [(0, "G")]]


def _up(bars, semis):
    """A score moved up by `semis` semitones."""
    out = []
    for bar in bars:
        out.append([(b, None if n is None else _name(N(n) + semis)) for b, n in bar])
    return out


def _name(midi):
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return names[midi % 12] + str(midi // 12 - 1)


# verse, chorus (its pickup already a step up), and the verse again in A major
PARTY_TUNE = _WW_VERSE + _WW_CHORUS[:-1] + [[(2, "G4"), (1, "E4")]] + _up(_WW_VERSE[:-1], 2) + [[(3, "A4")]]

CHORDS = {   # root, fifth, triad (close voicing around middle C)
    "G": ("G2", "D3", ["G3", "B3", "D4"]), "C": ("C3", "G2", ["G3", "C4", "E4"]),
    "D": ("D3", "A2", ["F#3", "A3", "D4"]), "D7": ("D3", "A2", ["F#3", "C4", "D4"]),
    "Am": ("A2", "E3", ["A3", "C4", "E4"]), "A7": ("A2", "E3", ["G3", "C#4", "E4"]),
    "Em": ("E3", "B2", ["G3", "B3", "E4"]), "Bm": ("B2", "F#3", ["F#3", "B3", "D4"]),
    "B7": ("B2", "F#3", ["F#3", "A3", "D#4"]), "A": ("A2", "E3", ["A3", "C#4", "E4"]),
    "E7": ("E3", "B2", ["G#3", "D4", "E4"]), "F#m": ("F#2", "C#3", ["F#3", "A3", "C#4"]),
    "C#7": ("C#3", "G#2", ["G#3", "B3", "F4"]), "E": ("E3", "B2", ["G#3", "B3", "E4"]),
}
# the party's last verse is in A: G->A, C->D, A7->B7, D->E, B7->C#7, Em->F#m, D7->E7
_TO_A = {"G": "A", "C": "D", "A7": "B7", "D": "E", "B7": "C#7", "Em": "F#m", "D7": "E7"}
PARTY_CHORDS = _WW_VC + _WW_CC + [[(b, _TO_A[c]) for b, c in bar] for bar in _WW_VC[:-1]] + [[(0, "A")]]


def chord_at(chords, bar, beat):
    name = chords[bar][0][1]
    for b, c in chords[bar]:
        if b <= beat:
            name = c
    return name


# ------------------------------------------------------------------ instruments
def xylo(midi, length=0.35, vel=0.6):
    """Xylophone: hard mallet, bright 3rd/4th partials, short ring."""
    n = int((length + 0.25) * SR)
    t = np.arange(n) / SR
    f = S.midi_hz(midi)
    x = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.22) +
         0.45 * np.sin(2 * np.pi * f * 3.0 * t) * np.exp(-t / 0.08) +
         0.2 * np.sin(2 * np.pi * f * 4.1 * t) * np.exp(-t / 0.04))
    click = S.bandpass(S.noise(n), 2500, 9000) * np.exp(-t / 0.004) * 0.35
    return (x + click) * np.minimum(1, t / 0.0015) * vel * 0.6


def pizz(midi, length=0.3, vel=0.6):
    """Pizzicato string: soft pluck through a wooden body."""
    n = int((length + 0.3) * SR)
    t = np.arange(n) / SR
    f = S.midi_hz(midi)
    x = sum(np.sin(2 * np.pi * f * k * t + RNG.uniform(0, 6)) / k ** 1.3 for k in range(1, 7))
    x = S.lowpass(x, 2600) * np.exp(-t / 0.16) * np.minimum(1, t / 0.003)
    body = S.bandpass(x, 300, 900) * 0.4
    return (x + body) * vel * 0.5


def woodblock(high=True, vel=0.6):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    f = 1250 if high else 880
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.025) + 0.4 * np.sin(2 * np.pi * f * 2.7 * t) * np.exp(-t / 0.01)
    x += S.bandpass(S.noise(n), 1500, 6000) * np.exp(-t / 0.003) * 0.4
    return x * vel * 0.6


def tink(midi=N("E7"), vel=0.6):
    """A tiny toy hammer on a tiny anvil."""
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = S.midi_hz(midi)
    x = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t / d)
            for r, a, d in ((1.0, 1.0, 0.18), (2.32, 0.6, 0.09), (3.97, 0.35, 0.05), (5.4, 0.2, 0.03)))
    x += S.highpass(S.noise(n), 5000) * np.exp(-t / 0.002) * 0.5
    return x * vel * 0.35


def ratchet(clicks=8, span=0.4, vel=0.6):
    """A wind-up key turning: a run of tiny clicks."""
    n = int((span + 0.05) * SR)
    out = np.zeros(n)
    for k in range(clicks):
        i = int(k * span / clicks * SR)
        c = woodblock(True, 0.4)[:int(0.02 * SR)] * 0.5 + S.highpass(S.noise(int(0.02 * SR)), 3000) * 0.3
        out[i:i + len(c)] += c[:n - i]
    return out * vel


def boing(f0=180, f1=520, length=0.5, vel=0.5):
    """A spring: a wobbling glide."""
    n = int(length * SR)
    t = np.arange(n) / SR
    f = f0 + (f1 - f0) * (1 - np.exp(-t / 0.05)) + 40 * np.sin(2 * np.pi * 14 * t) * np.exp(-t / 0.2)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    x += 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR)
    return x * np.exp(-t / 0.18) * vel * 0.5


def reed(midi, length, vel=0.5, octave_down=False, cutoff=2200, vib=0.0):
    """Clarinet/bassoon-like reed: odd harmonics, a little breath."""
    n = int((length + 0.12) * SR)
    t = np.arange(n) / SR
    f = S.midi_hz(midi - (12 if octave_down else 0)) * (1 + vib * np.sin(2 * np.pi * 5.0 * t) * np.minimum(1, t / 0.3))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = sum(np.sin(k * ph) / k for k in (1, 3, 5, 7, 9))
    x += 0.05 * S.bandpass(S.noise(n), 1000, 4000)
    x = S.lowpass(x, cutoff)
    return x * S.env_adsr(n, 0.02, 0.06, 0.8, 0.08, length) * vel * 0.5


def fiddle(midi, length, vel=0.5):
    """Folk fiddle: bright saw, quick vibrato, a wooden body."""
    n = int((length + 0.15) * SR)
    t = np.arange(n) / SR
    f = S.midi_hz(midi) * (1 + 0.006 * np.sin(2 * np.pi * 6.0 * t) * np.minimum(1, t / 0.15))
    ph = np.cumsum(f) / SR
    x = 2 * (ph % 1.0) - 1
    x = S.lowpass(x, 4500) + 0.5 * S.bandpass(x, 2200, 3200) + 0.3 * S.bandpass(x, 400, 700)
    return x * S.env_adsr(n, 0.025, 0.08, 0.75, 0.07, length) * vel * 0.4


def accordion(midis, length, vel=0.4):
    """Musette accordion: two reeds slightly apart, so it shimmers."""
    n = int((length + 0.1) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in midis:
        for d in (-0.004, 0.004):
            ph = np.cumsum(np.full(n, S.midi_hz(m) * (1 + d))) / SR
            out += 0.6 * (2 * (ph % 1.0) - 1) + 0.4 * np.sign(np.sin(2 * np.pi * ph))
    out = S.lowpass(out / max(1, 2 * len(midis)), 3000)
    return out * S.env_adsr(n, 0.03, 0.05, 0.85, 0.06, length) * vel * 0.45


def tambourine(vel=0.6, shake=False):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    jingles = X.sleigh_bell(1.0, 0.25) * 0.8
    skin = 0 if shake else S.bandpass(S.noise(n), 200, 900) * np.exp(-t / 0.02) * 0.6
    out = jingles[:n] + skin
    return out * vel


def tuba(midi, length, vel=0.6):
    return X.brass([midi], length, vel) * 1.3


# ------------------------------------------------------------------ workshop
def workshop():
    """Deck the Halls, G major, 4/4, 132 BPM: a busy toy workshop.
    One bar of wind-up ratchet and woodblock, then the carol on xylophone
    over pizzicato strings and a walking pizzicato bass; little toy hammers
    answer every 'fa la la', and the B section adds a clarinet."""
    T = Song(bpm=132, seconds=32.5, beats_per_bar=4)
    intro = 1
    # intro: a key winding up, woodblocks ticking, a spring
    T.add("fx", 0.0, ratchet(10, 0.75, 0.7))
    for k in range(4):
        T.add("perc", T.t(0, k), woodblock(k % 2 == 0, 0.7))
    T.add("fx", T.t(0, 3), boing(220, 600, 0.45, 0.5))

    for i, bar_notes in enumerate(DECK_TUNE):
        bar = intro + i
        last = i == len(DECK_TUNE) - 1
        # accompaniment: bass on 1 & 3 (pizz, octave down), chord stabs on 2 & 4
        for beat in range(4):
            cname = chord_at(DECK_CHORDS, i, beat)
            root, fifth, triad = CHORDS[cname]
            t = T.t(bar, beat)
            if last and beat > 0:
                continue
            if beat % 2 == 0:
                bn = root if beat == 0 else fifth
                T.add("bass", t, pizz(N(bn), 0.5, 0.95))
            else:
                for nm in triad:
                    put(T, "strings", t, pizz(N(nm), 0.25, 0.4), jitter=0.006)
            T.add("perc", t, woodblock(beat % 2 == 0, 0.35 if beat % 2 else 0.5))
        # melody: xylophone (doubled an octave up from bar 8), clarinet in B
        for t, m, beats in melody_line(T, bar, bar_notes):
            ln = beats * T.beat
            T.add("xylo", t, xylo(m + 12, min(0.6, ln), 0.75))
            if i >= 8:
                T.add("xylo", t, xylo(m + 24, 0.3, 0.25))
            if 8 <= i < 12:
                T.add("reed", t, reed(m, ln * 0.92, 0.55, vib=0.004))
        # fa la la: toy hammers on the off-beats
        if i in DECK_FALALA and not last:
            for k in range(4):
                T.add("perc", T.t(bar, k + 0.5), tink(N("E7") + (k % 2) * 5, 0.55))
        if last:
            t0 = T.t(bar)
            for k, nm in enumerate(["G2", "D3", "G3", "B3", "D4", "G4"]):
                T.add("strings", t0 + k * 0.02, pizz(N(nm), 1.0, 0.6))
            for k, nm in enumerate(["G5", "B5", "D6", "G6"]):
                T.add("xylo", t0 + k * 0.07, xylo(N(nm), 0.8, 0.7))
            T.add("perc", t0 + 0.4, tink(N("G7"), 0.8))
            for k in range(6):
                T.add("bells", t0 + 0.35 + k * 0.07, X.sleigh_bell(0.8 - k * 0.1, 0.18))
            T.add("fx", t0 + 0.9, boing(300, 750, 0.5, 0.35))
    T.reverb = {"xylo": 0.2, "strings": 0.18, "reed": 0.22, "perc": 0.1, "bells": 0.15}
    T.gains = {"xylo": 1.0, "strings": 0.7, "bass": 0.85, "perc": 0.6, "reed": 0.55, "fx": 0.6, "bells": 0.6}
    T.glue = 1.45
    return T


# ------------------------------------------------------------------ mischief
def mischief():
    """God Rest Ye Merry Gentlemen, E minor, 4/4, 156 BPM: an elf sneaking.
    Tiptoe pizzicato and a bassoon carry the tune for the first two lines;
    from 'remember Christ...' the clarinet takes over, the band gets bold
    (tambourine, accordion), and the ending is a sly 'ta-da'."""
    T = Song(bpm=156, seconds=32.0, beats_per_bar=4)
    intro = 1
    # intro: tiptoes (staccato pizz on E and B) and the pickup
    for k, nm in enumerate(["E3", "B3", "E3", "B3"]):
        T.add("bass", T.t(0, k), pizz(N(nm), 0.18, 0.8))
    T.add("reed", T.t(0, 3), reed(N("E4"), 0.9 * T.beat, 0.6, octave_down=True, cutoff=1400))

    for i, bar_notes in enumerate(GOD_REST_TUNE):
        bar = intro + i
        bold = i >= GOD_REST_BOLD
        last = i == len(GOD_REST_TUNE) - 1
        for beat in range(4):
            if last and beat > 0:
                continue
            cname = chord_at(GOD_REST_CHORDS, i, beat)
            root, fifth, triad = CHORDS[cname]
            t = T.t(bar, beat)
            T.add("bass", t, pizz(N(root if beat % 2 == 0 else fifth), 0.2 if not bold else 0.4, 0.9))
            if beat % 2 == 1:
                if bold:
                    T.add("acc", t, accordion([N(x) for x in triad], 0.4 * T.beat, 0.5))
                    T.add("perc", t, tambourine(0.55))
                else:
                    for nm in triad:
                        put(T, "strings", t, pizz(N(nm) + 12, 0.12, 0.3), jitter=0.004)
            if bold and beat % 2 == 0:
                T.add("perc", t, tambourine(0.3, shake=True))
        for t, m, beats in melody_line(T, bar, bar_notes):
            ln = beats * T.beat
            if not bold:
                # sneaking: bassoon (an octave down) and staccato pizz doubling
                T.add("reed", t, reed(m, min(ln, T.beat) * 0.6, 0.6, octave_down=True, cutoff=1400))
                T.add("strings", t, pizz(m + 12, 0.15, 0.55))
            else:
                T.add("lead", t, reed(m + 12, ln * 0.9, 0.55, cutoff=3200, vib=0.005))
                T.add("strings", t, pizz(m + 12, 0.15, 0.35))
            if i == 3 or i == 7:          # the long B: a sneaky woodblock "tick tick"
                for k in (1, 2):
                    T.add("perc", T.t(bar, k), woodblock(k == 1, 0.5))
        if last:
            t0 = T.t(bar)
            # sly 'ta-da': a low E, a pause, then a bright E major chord (Picardy)
            T.add("bass", t0, pizz(N("E2"), 0.6, 1.0))
            T.add("reed", t0, reed(N("E4"), 0.4, 0.6, octave_down=True, cutoff=1400))
            t1 = t0 + 2 * T.beat
            T.add("acc", t1, accordion([N("E4"), N("G#4"), N("B4"), N("E5")], 1.2, 0.6))
            for k, nm in enumerate(["E5", "G#5", "B5", "E6"]):
                T.add("lead", t1 + k * 0.05, xylo(N(nm), 0.8, 0.6))
            T.add("perc", t1, tambourine(0.8))
            T.add("perc", t1 + 0.25, tink(N("E7"), 0.7))
    T.reverb = {"reed": 0.18, "lead": 0.22, "strings": 0.15, "acc": 0.2, "perc": 0.1}
    T.gains = {"reed": 0.9, "lead": 0.8, "strings": 0.75, "bass": 0.85, "acc": 0.55, "perc": 0.55}
    T.glue = 1.45
    return T


# ------------------------------------------------------------------ party
def party():
    """We Wish You a Merry Christmas, G major, 3/4, 160 BPM: an elves' party.
    Fiddle on the tune, accordion and oom-pah tuba, tambourine; the chorus
    adds xylophone, and the last verse jumps up a step to A major."""
    T = Song(bpm=160, seconds=31.0, beats_per_bar=3)
    intro = 2
    # intro: two bars of oom-pah-pah and a tambourine roll, fiddle pickup D4
    for bar in range(intro):
        root, fifth, triad = CHORDS["G"] if bar == 0 else CHORDS["D7"]
        T.add("bass", T.t(bar, 0), tuba(N(root), 0.9 * T.beat, 0.7))
        for b in (1, 2):
            T.add("acc", T.t(bar, b), accordion([N(x) for x in triad], 0.45 * T.beat, 0.45))
        T.add("perc", T.t(bar, 0), tambourine(0.5))
    T.add("lead", T.t(1, 2), fiddle(N("D4"), 0.9 * T.beat, 0.6))

    for i, bar_notes in enumerate(PARTY_TUNE):
        bar = intro + i
        last = i == len(PARTY_TUNE) - 1
        chorus = 8 <= i < 16
        for beat in range(3):
            if last and beat > 0:
                continue
            cname = chord_at(PARTY_CHORDS, i, beat)
            root, fifth, triad = CHORDS[cname]
            t = T.t(bar, beat)
            if beat == 0:
                T.add("bass", t, tuba(N(root), 0.9 * T.beat, 0.75))
                T.add("perc", t, tambourine(0.6))
            else:
                T.add("acc", t, accordion([N(x) for x in triad], 0.45 * T.beat, 0.45))
                T.add("perc", t, tambourine(0.3, shake=True))
        for t, m, beats in melody_line(T, bar, bar_notes):
            ln = beats * T.beat
            T.add("lead", t, fiddle(m + 12, ln * 0.93, 0.6))
            if chorus or i >= 16:
                T.add("xylo", t, xylo(m + 24, 0.35, 0.35))
        if last:
            t0 = T.t(bar)
            T.add("bass", t0, tuba(N("A2"), 1.6, 0.5))
            T.add("acc", t0, accordion([N("A3"), N("C#4"), N("E4"), N("A4")], 1.6, 0.4))
            for k, nm in enumerate(["A5", "C#6", "E6", "A6"]):
                T.add("xylo", t0 + k * 0.06, xylo(N(nm), 0.8, 0.6))
            for k in range(8):
                T.add("perc", t0 + k * 0.06, tambourine(0.5 - k * 0.05, shake=True))
            T.add("fx", t0 + 0.6, boing(260, 700, 0.5, 0.35))
    T.reverb = {"lead": 0.2, "acc": 0.15, "xylo": 0.2, "perc": 0.1}
    T.gains = {"lead": 1.25, "acc": 0.6, "bass": 0.7, "perc": 0.5, "xylo": 0.5, "fx": 0.5}
    T.glue = 1.8
    return T


TRACKS = {"workshop": workshop, "mischief": mischief, "party": party}


# ------------------------------------------------------------------ short sounds
def startup():
    """~3 s: a wind-up key, a spring, a xylophone run up the G major scale,
    and a toy chord with jingles and a little hammer 'tink'."""
    T = Song(bpm=200, seconds=3.2, beats_per_bar=4)
    T.add("fx", 0.0, ratchet(8, 0.55, 0.8))
    T.add("fx", 0.6, boing(200, 640, 0.45, 0.6))
    run = ["G5", "A5", "B5", "C6", "D6", "E6", "F#6", "G6"]
    for k, nm in enumerate(run):
        T.add("xylo", 0.95 + k * 0.065, xylo(N(nm), 0.3, 0.5 + 0.03 * k))
    t1 = 1.55
    for k, nm in enumerate(["G3", "D4", "G4", "B4", "D5"]):
        T.add("keys", t1 + k * 0.02, pizz(N(nm), 1.0, 0.55))
    for k, nm in enumerate(["G6", "B6", "D7"]):
        T.add("xylo", t1 + 0.05 + k * 0.06, X.celesta(N(nm), 1.2, 0.35))
    T.add("perc", t1 + 0.3, tink(N("G7"), 0.8))
    for k in range(6):
        T.add("bells", t1 + k * 0.07, X.sleigh_bell(0.7 - k * 0.1, 0.18))
    T.reverb = {"xylo": 0.25, "keys": 0.2, "bells": 0.2, "perc": 0.15}
    T.gains = {"xylo": 1.0, "keys": 0.8, "fx": 0.7, "perc": 0.7, "bells": 0.6}
    T.glue = 1.3
    T.level_db = -1.5
    return T


def reminder():
    """~2.7 s: a toy clock ticking (woodblocks), then two bright xylophone
    'ta-da!' calls with a jingle, friendly enough to hear twice a day."""
    T = Song(bpm=120, seconds=2.7, beats_per_bar=4)
    for k in range(4):
        T.add("perc", 0.05 + k * 0.16, woodblock(k % 2 == 0, 0.7))
    for rep, t0 in enumerate((0.75, 1.55)):
        for k, nm in enumerate(["G5", "B5", "D6"]):
            T.add("xylo", t0 + k * 0.08, xylo(N(nm), 0.25, 0.65))
        T.add("xylo", t0 + 0.26, xylo(N("G6"), 0.6, 0.8))
        T.add("xylo", t0 + 0.26, X.glock(N("G6"), 0.8, 0.35))
        T.add("perc", t0 + 0.26, tink(N("D7") + rep * 5, 0.6))
        for k in range(4):
            T.add("bells", t0 + 0.26 + k * 0.06, X.sleigh_bell(0.6 - k * 0.1, 0.16))
    T.reverb = {"xylo": 0.25, "perc": 0.12, "bells": 0.15}
    T.gains = {"xylo": 1.0, "perc": 0.7, "bells": 0.55}
    T.glue = 1.1
    T.level_db = -2.7      # as loud as the other reminder sounds
    return T


TRACKS.update({"startup": startup, "reminder": reminder})


def render(name):
    # Same random streams every time, whatever ran before.
    global RNG
    RNG = np.random.default_rng(31)
    X.RNG = np.random.default_rng(31)
    T = TRACKS[name]()
    mix = np.zeros(T.n)
    for bus, buf in T.buses.items():
        x = S.reverb(buf, wet=T.reverb[bus]) if bus in T.reverb else buf
        mix += x * T.gains.get(bus, 1.0)
    mix = S.master(mix, glue=T.glue) * 10 ** (getattr(T, "level_db", 0.0) / 20)
    mix24 = signal.resample_poly(mix, 1, 2)
    os.makedirs(OUT, exist_ok=True)
    base = os.path.join(OUT, "elf_" + name)
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
