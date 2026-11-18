"""Coglet Snowman edition tracks (public-domain music, our own arrangements).

  lullaby   Brahms, Wiegenlied Op. 49/4 (1868)              music box, celesta, soft strings, wind chimes
  stomp     Good King Wenceslas (tune: Piae Cantiones 1582)  tuba, bassoon, pizzicato, snow crunch, a snowball
  blizzard  Leontovych, Shchedryk (1914; the bell ostinato)   glass bells, swirling strings, wind, a freeze

Carol of the Bells: only Leontovych's own 1914 material (the four-note
ostinato and its sequence) is used, in our own arrangement; not the later
English lyrics or choral arrangement.

python3 snow.py [lullaby|stomp|blizzard|startup|reminder ...]  ->  out/snow_<name>.ogg / _preview.mp3
"""
import os
import subprocess
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

import synth as S
import xmas as X
import elf as E

N = S.note
SR = S.SR
RNG = np.random.default_rng(47)
OUT = X.OUT
Song, put, melody_line, chord_at = X.Song, X.put, X.melody_line, E.chord_at


# ------------------------------------------------------------------ scores
# Brahms' Lullaby, C major, 3/4; the pickup (E E) is on beat 3 of the intro bar.
LULLABY_TUNE = [
    [(2, "G4"), (0.5, "E4"), (0.5, "E4")],
    [(2, "G4"), (0.5, "E4"), (0.5, "G4")],
    [(1, "C5"), (1.5, "B4"), (0.5, "A4")],
    [(1, "A4"), (1, "G4"), (0.5, "D4"), (0.5, "E4")],
    [(1, "F4"), (1, "D4"), (0.5, "D4"), (0.5, "E4")],
    [(2, "F4"), (0.5, "D4"), (0.5, "F4")],
    [(0.5, "B4"), (0.5, "A4"), (1, "G4"), (1, "B4")],
    [(2, "C5"), (0.5, "C4"), (0.5, "C4")],
    [(2, "C5"), (0.5, "A4"), (0.5, "F4")],
    [(2, "G4"), (0.5, "E4"), (0.5, "C4")],
    [(1, "F4"), (1, "G4"), (1, "A4")],
    [(2, "G4"), (0.5, "C4"), (0.5, "C4")],
    [(2, "C5"), (0.5, "A4"), (0.5, "F4")],
    [(2, "G4"), (0.5, "E4"), (0.5, "C4")],
    [(1, "F4"), (1, "E4"), (1, "D4")],
    [(3, "C4")],
]
LULLABY_CHORDS = [[(0, "C")], [(0, "C")], [(0, "F")], [(0, "F"), (1, "C"), (2, "G7")],
                  [(0, "G7")], [(0, "G7")], [(0, "G7")], [(0, "C")],
                  [(0, "F")], [(0, "C")], [(0, "G7")], [(0, "C")],
                  [(0, "F")], [(0, "C")], [(0, "G7")], [(0, "C")]]

# Good King Wenceslas, G major, 4/4 (verse without the repeat of line 1)
STOMP_TUNE = [
    [(1, "G4"), (1, "G4"), (1, "G4"), (1, "A4")],
    [(1, "G4"), (1, "G4"), (2, "D4")],
    [(1, "E4"), (1, "D4"), (1, "E4"), (1, "F#4")],
    [(2, "G4"), (2, "G4")],
    [(1, "D5"), (1, "C5"), (1, "B4"), (1, "A4")],
    [(1, "B4"), (1, "A4"), (2, "G4")],
    [(1, "E4"), (1, "D4"), (1, "E4"), (1, "F#4")],
    [(2, "G4"), (2, "G4")],
    [(1, "D4"), (1, "D4"), (1, "E4"), (1, "F#4")],
    [(1, "G4"), (1, "G4"), (2, "A4")],
    [(1, "D5"), (1, "C5"), (1, "B4"), (1, "A4")],
    [(2, "G4"), (2, "C5")],
    [(4, "G4")],
]
STOMP_CHORDS = [[(0, "G")], [(0, "G"), (2, "D")], [(0, "C"), (2, "D")], [(0, "G")],
                [(0, "G"), (2, "D7")], [(0, "G"), (1, "D"), (2, "G")], [(0, "C"), (2, "D")], [(0, "G")],
                [(0, "G"), (2, "D")], [(0, "G"), (2, "D")], [(0, "G"), (2, "D7")], [(0, "G"), (2, "C")],
                [(0, "G")]]
STOMP_SNOWBALLS = [3, 7]      # bars whose second half gets a snowball 'poof'

# Shchedryk: the four-note bell ostinato, G minor, 3/4, one figure per bar.
def _bell(top, a, b, low):
    return [(1, top), (0.5, a), (0.5, b), (1, low)]


OSTINATO = _bell("Bb4", "A4", "Bb4", "G4")
SECOND = _bell("D5", "C5", "D5", "Bb4")
THIRD = _bell("F5", "Eb5", "F5", "D5")
HIGH = _bell("Bb5", "A5", "Bb5", "G5")
BLIZZARD_BASS = ["G2", "F2", "Eb2", "D2"]        # the descending bass under each 4 bars
# section plan: (first bar, last bar, name)
BLIZZARD_PLAN = [(0, 3, "alone"), (4, 7, "bass"), (8, 11, "second"), (12, 15, "third"),
                 (16, 19, "climax"), (20, 23, "fading"), (24, 24, "last"), (25, 25, "freeze")]
# the figure Coglet follows in each bar (the highest one sounding)
BLIZZARD_TUNE = ([OSTINATO] * 8 + [SECOND] * 4 + [THIRD] * 4 + [HIGH] * 4 +
                 [HIGH, THIRD, SECOND, OSTINATO] + [OSTINATO] + [[(3, "G4")]])

CHORDS = dict(E.CHORDS)
CHORDS.update({
    "F": ("F2", "C3", ["F3", "A3", "C4"]), "G7": ("G2", "D3", ["F3", "B3", "D4"]),
})


# ------------------------------------------------------------------ instruments
def glass(midi, length=1.2, vel=0.5):
    """Glassy bell: inharmonic partials, a bright strike, a long shimmer."""
    n = int((length + 0.6) * SR)
    t = np.arange(n) / SR
    f = S.midi_hz(midi)
    x = sum(a * np.sin(2 * np.pi * f * r * t + RNG.uniform(0, 6)) * np.exp(-t / d)
            for r, a, d in ((1.0, 1.0, 0.9), (2.76, 0.45, 0.35), (5.4, 0.25, 0.15), (8.93, 0.12, 0.06)))
    x *= 1 + 0.08 * np.sin(2 * np.pi * 4.5 * t)
    return x * np.minimum(1, t / 0.002) * vel * 0.35


def wind(length, vel=0.5, gust=0.35):
    """Wind: filtered noise with slow gusts."""
    n = int(length * SR)
    t = np.arange(n) / SR
    x = S.noise(n)
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * (0.13 * t + 0.07 * np.sin(2 * np.pi * 0.05 * t)))
    lo = S.bandpass(x, 250, 900) * lfo
    hi = S.bandpass(x, 1800, 4200) * (gust * lfo ** 3)
    env = np.minimum(1, t / 1.0) * np.minimum(1, (length - t) / 1.2)
    return (lo + hi) * env * vel * 0.5


def chimes(length, count=6, vel=0.4):
    """Wind chimes: a few random high notes of a pentatonic set."""
    n = int((length + 1.5) * SR)
    out = np.zeros(n)
    notes = [N(x) for x in ("C6", "D6", "E6", "G6", "A6", "C7")]
    for _ in range(count):
        t0 = RNG.uniform(0, length)
        c = glass(notes[RNG.integers(len(notes))], 1.0, vel * RNG.uniform(0.4, 1.0))
        i = int(t0 * SR)
        out[i:i + len(c)] += c[:n - i]
    return out


def crunch(vel=0.6):
    """A foot in deep snow: a soft thump and a packed-snow crackle."""
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * 75 * t) * np.exp(-t / 0.05) * 0.6
    grains = S.noise(n) * (RNG.random(n) < 0.08)
    crackle = S.bandpass(grains, 1500, 6000) * np.exp(-t / 0.08) * 2.5
    return (thump + crackle) * vel * 0.6


def poof(vel=0.8):
    """A snowball hitting: a soft low thud and a burst of powder."""
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    thud = np.sin(2 * np.pi * (110 - 50 * np.minimum(1, t / 0.08)) * t) * np.exp(-t / 0.06)
    powder = S.lowpass(S.noise(n), 3500) * np.exp(-t / 0.18) * np.minimum(1, t / 0.01)
    return (thud * 0.8 + powder * 0.6) * vel * 0.6


def ice_crack(vel=0.8):
    """Ice freezing over: a sharp crack and a glassy ring."""
    n = int(1.5 * SR)
    t = np.arange(n) / SR
    crack = S.highpass(S.noise(n), 2000) * np.exp(-t / 0.015)
    ring = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, d in ((2350, 0.5), (3870, 0.3), (5210, 0.2)))
    return (crack * 0.9 + ring * 0.25) * vel * 0.5


# ------------------------------------------------------------------ lullaby
def lullaby():
    """Brahms' Lullaby, C major, 3/4, 104 BPM: a snowman dozing off while
    the snow falls. Music box carries the tune over celesta, soft strings
    and a gentle bass; wind chimes now and then; the second half adds a
    warm string line and slows into the last chord."""
    T = Song(bpm=104, seconds=32.5, beats_per_bar=3)
    intro = 1
    T.add("air", 0.0, wind((T.n / SR), 0.22, gust=0.15))
    T.add("chimes", 0.2, chimes(1.2, 4, 0.35))
    # intro: two celesta notes of the C chord, then the pickup E E on the music box
    T.add("keys", T.t(0, 0), X.celesta(N("C5"), 1.5, 0.35))
    T.add("keys", T.t(0, 1), X.celesta(N("G5"), 1.5, 0.3))
    T.add("box", T.t(0, 2), S.music_box(N("E5"), 0.4) * 0.8)
    T.add("box", T.t(0, 2.5), S.music_box(N("E5"), 0.4) * 0.8)

    for i, bar_notes in enumerate(LULLABY_TUNE):
        bar = intro + i
        last = i == len(LULLABY_TUNE) - 1
        cname = chord_at(LULLABY_CHORDS, i, 0)
        root, fifth, triad = CHORDS[cname]
        t0 = T.t(bar)
        # bass on 1, a soft rocking celesta on 2 and 3
        T.add("bass", t0, X.upright_bass(N(root), 1.6 if not last else 3.0, 0.5))
        if not last:
            for b in (1, 2):
                cn = chord_at(LULLABY_CHORDS, i, b)
                tri = CHORDS[cn][2]
                T.add("keys", T.t(bar, b), X.celesta(N(tri[b % 3]) + 12, 0.9, 0.18))
        # strings: pad all through, warmer (an octave lower line) in the second half
        T.add("strings", t0, X.strings([N(x) for x in triad], (T.bpb * T.beat) * (1.0 if not last else 1.6), 0.22))
        for t, m, beats in melody_line(T, bar, bar_notes):
            T.add("box", t, S.music_box(m + 12, max(0.6, beats * T.beat)) * 0.9)
            if i >= 8:
                T.add("lead", t, X.strings([m], beats * T.beat * 0.95, 0.22))
        if i in (3, 7, 11):
            T.add("chimes", t0 + 0.4, chimes(1.5, 3, 0.3))
        if last:
            for k, nm in enumerate(["C5", "E5", "G5", "C6"]):
                T.add("keys", t0 + 0.25 + k * 0.18, X.celesta(N(nm), 2.0, 0.3))
            T.add("chimes", t0 + 0.8, chimes(1.8, 5, 0.3))
    T.reverb = {"box": 0.35, "keys": 0.4, "strings": 0.4, "lead": 0.4, "chimes": 0.45, "air": 0.2}
    T.gains = {"box": 1.0, "keys": 0.7, "strings": 0.5, "lead": 0.55, "bass": 0.5, "chimes": 0.45, "air": 0.5}
    T.glue = 1.3
    return T


# ------------------------------------------------------------------ stomp
def stomp():
    """Good King Wenceslas, G major, 4/4, 108 BPM: a snowman stomping through
    deep snow. Tuba and bassoon on the tune, pizzicato off-beats, a crunch
    on every step, and a snowball 'poof' in the gap after two phrases."""
    T = Song(bpm=108, seconds=32.5, beats_per_bar=4)
    intro = 1
    T.add("air", 0.0, wind((T.n / SR), 0.12, gust=0.1))
    for k in range(4):                       # four steps into the snow
        T.add("steps", T.t(0, k), crunch(0.5 + 0.1 * k))
    for i, bar_notes in enumerate(STOMP_TUNE):
        bar = intro + i
        last = i == len(STOMP_TUNE) - 1
        for beat in range(4):
            if last and beat > 0:
                continue
            cname = chord_at(STOMP_CHORDS, i, beat)
            root, fifth, triad = CHORDS[cname]
            t = T.t(bar, beat)
            T.add("steps", t, crunch(0.55 if beat % 2 == 0 else 0.4))
            if beat % 2 == 0:
                T.add("bass", t, E.tuba(N(root if beat == 0 else fifth), 0.8 * T.beat, 0.7))
            else:
                for nm in triad:
                    put(T, "strings", t, E.pizz(N(nm), 0.2, 0.4), jitter=0.006)
        for t, m, beats in melody_line(T, bar, bar_notes):
            ln = beats * T.beat
            T.add("lead", t, E.reed(m, ln * 0.85, 0.6, octave_down=True, cutoff=1500))
            if i >= 4:
                T.add("bells", t, glass(m + 24, 0.6, 0.25))
            if i >= 8:
                T.add("lead2", t, E.reed(m + 12, ln * 0.85, 0.4, cutoff=3000, vib=0.004))
        if i in STOMP_SNOWBALLS:
            T.add("fx", T.t(bar, 2.5), poof(0.9))
            T.add("bells", T.t(bar, 3), glass(N("E6"), 0.4, 0.35))
            T.add("bells", T.t(bar, 3.25), glass(N("C6"), 0.4, 0.3))
        if last:
            t0 = T.t(bar)
            T.add("bass", t0, E.tuba(N("G2"), 2.0, 0.6))
            for k, nm in enumerate(["G5", "B5", "D6", "G6"]):
                T.add("bells", t0 + k * 0.09, glass(N(nm), 1.4, 0.4))
            T.add("fx", t0 + 1.4, poof(0.7))
    T.reverb = {"lead": 0.18, "lead2": 0.2, "strings": 0.15, "bells": 0.35, "fx": 0.15, "air": 0.2}
    T.gains = {"lead": 1.0, "lead2": 0.6, "strings": 0.65, "bass": 0.75, "steps": 0.6, "bells": 0.5,
               "fx": 0.75, "air": 0.5}
    T.glue = 1.5
    return T


# ------------------------------------------------------------------ blizzard
def blizzard():
    """Shchedryk (Carol of the Bells), G minor, 3/4, 150 BPM: a blizzard.
    The four-note bell figure alone, then the descending bass, then voices
    a third, a fifth and an octave higher with swirling strings and rising
    wind; at the peak everything thins out to a single bell, and the music
    freezes with a crack of ice."""
    T = Song(bpm=150, seconds=32.0, beats_per_bar=3)

    def section(bar):
        for a, b, name in BLIZZARD_PLAN:
            if a <= bar <= b:
                return name
        return "freeze"

    T.add("air", 0.0, wind((T.bpb * T.beat) * 24, 0.35, gust=0.5))
    for bar in range(25):
        sec = section(bar)
        t0 = T.t(bar)
        vel = {"alone": 0.45, "bass": 0.5, "second": 0.55, "third": 0.6, "climax": 0.7,
               "fading": 0.5 - 0.08 * (bar - 20), "last": 0.25}[sec]
        # the bell ostinato is always there
        for t, m, beats in melody_line(T, bar, OSTINATO):
            T.add("bells", t, glass(m + 12, 0.6, vel))
            T.add("pizz", t, E.pizz(m, 0.2, vel * 0.8))
        if sec in ("bass", "third", "climax"):
            bn = BLIZZARD_BASS[(bar - 4) % 4]
            T.add("bass", t0, X.strings([N(bn), N(bn) + 12], (T.bpb * T.beat) * 0.98, 0.35))
        if sec in ("second", "third", "climax"):
            for t, m, beats in melody_line(T, bar, SECOND):
                T.add("strings", t, X.strings([m], beats * T.beat * 0.95, 0.3))
        if sec in ("third", "climax"):
            for t, m, beats in melody_line(T, bar, THIRD):
                T.add("strings", t, X.strings([m], beats * T.beat * 0.95, 0.28))
            # swirling: a quick arpeggio run across the bar
            run = ["G5", "Bb5", "D6", "G6", "D6", "Bb5"]
            for k, nm in enumerate(run):
                T.add("swirl", t0 + k * T.beat / 2, X.celesta(N(nm), 0.4, 0.25 if sec == "third" else 0.32))
        if sec == "climax":
            for t, m, beats in melody_line(T, bar, HIGH):
                T.add("high", t, glass(m + 12, 0.8, 0.55))
                T.add("strings", t, X.strings([m], beats * T.beat * 0.95, 0.25))
            T.add("choir", t0, S.choir([N("G4"), N("Bb4"), N("D5")] if bar % 2 == 0 else
                                       [N("F4"), N("A4"), N("C5")], (T.bpb * T.beat), cutoff=2400) * 0.35)
        if sec == "fading":
            fig = BLIZZARD_TUNE[bar]
            for t, m, beats in melody_line(T, bar, fig):
                T.add("high", t, glass(m + 12, 0.8, 0.4 - 0.06 * (bar - 20)))
        if bar == 16:
            T.add("fx", t0 - (T.bpb * T.beat), S.riser((T.bpb * T.beat), 400, 6000) * 0.25)
            T.add("fx", t0, S.crash(2.0) * 0.35)
    # freeze: a G minor chord on glass, a crack of ice, then only shimmer
    t0 = T.t(25)
    for k, nm in enumerate(["G4", "Bb4", "D5", "G5", "Bb5"]):
        T.add("high", t0 + k * 0.02, glass(N(nm), 2.4, 0.5))
    T.add("bass", t0, X.strings([N("G2"), N("D3")], 1.6, 0.35))
    T.add("fx", t0, ice_crack(0.9))
    T.add("swirl", t0 + 0.6, chimes(2.0, 6, 0.3))
    T.reverb = {"bells": 0.35, "pizz": 0.2, "strings": 0.3, "swirl": 0.35, "high": 0.4, "choir": 0.4,
                "fx": 0.3, "air": 0.2, "bass": 0.25}
    T.gains = {"bells": 0.9, "pizz": 0.55, "strings": 0.55, "swirl": 0.45, "high": 0.65, "choir": 0.5,
               "bass": 0.6, "fx": 0.6, "air": 0.6}
    T.glue = 1.5
    return T


TRACKS = {"lullaby": lullaby, "stomp": stomp, "blizzard": blizzard}


# ------------------------------------------------------------------ short sounds
def startup():
    """~3 s: a gust of wind, ice chimes rising, a soft 'poof' of snow and a
    warm low chord, as if the snowman wakes up."""
    T = Song(bpm=120, seconds=3.2, beats_per_bar=4)
    T.add("air", 0.0, wind(1.6, 0.6, gust=0.6))
    for k, nm in enumerate(["G5", "B5", "D6", "F#6", "A6", "D7"]):
        T.add("bells", 0.35 + k * 0.12, glass(N(nm), 0.8, 0.35 + 0.04 * k))
    T.add("fx", 1.15, poof(0.9))
    t1 = 1.25
    T.add("warm", t1, X.strings([N("D3"), N("A3"), N("D4"), N("F#4")], 1.6, 0.4))
    for k, nm in enumerate(["D5", "F#5", "A5"]):
        T.add("bells", t1 + 0.05 + k * 0.08, X.celesta(N(nm), 1.4, 0.3))
    T.reverb = {"bells": 0.4, "warm": 0.35, "air": 0.2, "fx": 0.15}
    T.gains = {"bells": 1.0, "warm": 0.8, "air": 0.6, "fx": 0.8}
    T.glue = 1.3
    T.level_db = -1.5
    return T


def reminder():
    """~2.7 s: icicles: a falling run of glass bells, then two clear calls."""
    T = Song(bpm=120, seconds=2.7, beats_per_bar=4)
    for k, nm in enumerate(["E7", "C7", "A6", "E6"]):
        T.add("bells", 0.05 + k * 0.09, glass(N(nm), 0.5, 0.3))
    for rep, t0 in enumerate((0.75, 1.5)):
        T.add("bells", t0, glass(N("E6"), 0.6, 0.55))
        T.add("bells", t0 + 0.16, glass(N("A6"), 0.9, 0.65))
        T.add("keys", t0 + 0.16, X.celesta(N("A5"), 0.9, 0.3))
    T.reverb = {"bells": 0.4, "keys": 0.35}
    T.gains = {"bells": 1.0, "keys": 0.7}
    T.glue = 1.1
    T.level_db = -2.7
    return T


TRACKS.update({"startup": startup, "reminder": reminder})


def render(name):
    global RNG
    RNG = np.random.default_rng(47)
    E.RNG = np.random.default_rng(47)
    X.RNG = np.random.default_rng(47)
    T = TRACKS[name]()
    mix = np.zeros(T.n)
    for bus, buf in T.buses.items():
        x = S.reverb(buf, wet=T.reverb[bus]) if bus in T.reverb else buf
        mix += x * T.gains.get(bus, 1.0)
    mix = S.master(mix, glue=T.glue) * 10 ** (getattr(T, "level_db", 0.0) / 20)
    mix24 = signal.resample_poly(mix, 1, 2)
    os.makedirs(OUT, exist_ok=True)
    base = os.path.join(OUT, "snow_" + name)
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
