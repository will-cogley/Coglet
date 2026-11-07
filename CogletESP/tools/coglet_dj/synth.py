"""Tiny offline synth engine for Coglet dance tracks (numpy/scipy).

Everything is rendered at SR (48 kHz) mono, then mastered for Coglet's small
speaker (MAX98357A + ~1 W driver): real sub-bass is inaudible there, so kicks
and basses get mid-range harmonics, and the master is high-passed.
"""
import numpy as np
from scipy import signal

SR = 48000
RNG = np.random.default_rng(7)


def midi_hz(n):
    return 440.0 * 2.0 ** ((n - 69) / 12.0)


def note(name):
    """'A4' / 'C#3' / 'Bb2' -> MIDI number."""
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    base = names[name[0]]
    i = 1
    if name[i] in "#b":
        base += 1 if name[i] == "#" else -1
        i += 1
    octave = int(name[i:])
    return 12 * (octave + 1) + base


class Track:
    def __init__(self, bpm, seconds):
        self.bpm = bpm
        self.beat = 60.0 / bpm
        self.n = int(seconds * SR)
        self.buses = {}
        self.events = []    # (time_s, kind, value) for choreography

    def t(self, bar, beat=0.0):
        return (bar * 4 + beat) * self.beat

    def bus(self, name):
        if name not in self.buses:
            self.buses[name] = np.zeros(self.n)
        return self.buses[name]

    def add(self, name, start_s, audio, gain=1.0):
        b = self.bus(name)
        i = int(round(start_s * SR))
        if i >= self.n or i + len(audio) <= 0:
            return
        j = min(self.n, i + len(audio))
        b[max(i, 0):j] += gain * audio[max(0, -i):j - i]

    def mark(self, time_s, kind, value=None):
        self.events.append((round(time_s, 4), kind, value))


# ------------------------------------------------------------------ helpers
def env_adsr(n, a=0.005, d=0.1, s=0.7, r=0.1, length=None):
    """ADSR envelope; `length` = note-on duration (s), release added after."""
    length = length if length is not None else n / SR
    total = n
    e = np.zeros(total)
    a_n, d_n = int(a * SR), int(d * SR)
    on = int(length * SR)
    r_n = int(r * SR)
    idx = np.arange(total)
    e = np.where(idx < a_n, idx / max(a_n, 1), 1.0)
    dec = (idx >= a_n) & (idx < a_n + d_n)
    e = np.where(dec, 1.0 - (1.0 - s) * (idx - a_n) / max(d_n, 1), e)
    e = np.where((idx >= a_n + d_n) & (idx < on), s, e)
    rel = idx >= on
    level_at_off = s if on >= a_n + d_n else (on / max(a_n, 1) if on < a_n else 1 - (1 - s) * (on - a_n) / max(d_n, 1))
    e = np.where(rel, level_at_off * np.clip(1 - (idx - on) / max(r_n, 1), 0, 1), e)
    return e


def env_exp(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def saw(freq, n, phase=0.0):
    """Band-limited saw by additive synthesis (fine for short notes)."""
    t = np.arange(n) / SR
    out = np.zeros(n)
    k = 1
    while k * freq < SR * 0.45 and k < 60:
        out += ((-1) ** (k + 1)) * np.sin(2 * np.pi * k * freq * t + phase * k) / k
        k += 1
    return out * (2 / np.pi)


def square(freq, n, duty_harmonics=40):
    t = np.arange(n) / SR
    out = np.zeros(n)
    k = 1
    while k * freq < SR * 0.45 and k < duty_harmonics:
        out += np.sin(2 * np.pi * k * freq * t) / k
        k += 2
    return out * (4 / np.pi)


def lowpass(x, cutoff, order=2):
    cutoff = min(max(cutoff, 30), SR * 0.45)
    b, a = signal.butter(order, cutoff / (SR / 2), "low")
    return signal.lfilter(b, a, x)


def highpass(x, cutoff, order=2):
    b, a = signal.butter(order, cutoff / (SR / 2), "high")
    return signal.lfilter(b, a, x)


def bandpass(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), hi / (SR / 2)], "band")
    return signal.lfilter(b, a, x)


def sweep_lowpass(x, f0, f1, curve=2.0):
    """Time-varying low-pass via short overlapping blocks."""
    out = np.zeros_like(x)
    block = 1024
    hop = block // 2
    win = np.hanning(block)
    n = len(x)
    for start in range(0, n, hop):
        seg = x[start:start + block]
        if len(seg) < 16:
            break
        frac = (start / max(n - 1, 1)) ** curve
        fc = f0 + (f1 - f0) * frac
        y = lowpass(np.concatenate([np.zeros(256), seg]), fc)[256:]
        w = win[:len(seg)]
        out[start:start + len(seg)] += y * w
    return out


def soft_clip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


def noise(n):
    return RNG.uniform(-1, 1, n)


# ------------------------------------------------------------------ drums
def kick(punch=1.0, length=0.35, f_hi=160, f_lo=48, click=0.6, drive=2.5):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = f_lo + (f_hi - f_lo) * np.exp(-t / 0.03)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * env_exp(n, 0.12 * punch)
    clk = highpass(noise(n), 1500) * env_exp(n, 0.004) * click
    # harmonics so the kick is audible on a tiny speaker
    return soft_clip(body * 1.2 + clk, drive) * 0.9


def snare(length=0.25, tone=190, snap=1.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * tone * t) * env_exp(n, 0.05)
    nz = bandpass(noise(n), 1200, 9000) * env_exp(n, 0.07) * snap
    return soft_clip(body * 0.6 + nz, 1.5) * 0.8


def clap(length=0.3):
    n = int(length * SR)
    e = np.zeros(n)
    for off in (0.0, 0.011, 0.022):
        i = int(off * SR)
        e[i:] += env_exp(n - i, 0.008 if off < 0.02 else 0.09)
    return bandpass(noise(n), 900, 6000) * e * 0.7


def hat(open_=False):
    length = 0.25 if open_ else 0.05
    n = int(length * SR)
    return highpass(noise(n), 7000, 4) * env_exp(n, 0.08 if open_ else 0.012) * 0.5


def shaker():
    n = int(0.08 * SR)
    return bandpass(noise(n), 5000, 11000) * env_adsr(n, 0.01, 0.03, 0.3, 0.04, 0.03) * 0.35


def tom(freq=110, length=0.4):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = freq * (1 + 0.5 * np.exp(-t / 0.05))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.15) * 0.8


def crash(length=1.8):
    n = int(length * SR)
    return highpass(noise(n), 4000, 2) * env_exp(n, 0.5) * 0.35


def riser(length, f0=300, f1=9000):
    n = int(length * SR)
    x = noise(n)
    x = sweep_lowpass(x, f0, f1, curve=1.5)
    return x * np.linspace(0.05, 1.0, n) ** 2 * 0.6


def impact(length=2.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(70 + 80 * np.exp(-t / 0.08)) / SR) * env_exp(n, 0.5)
    return soft_clip(boom * 1.3 + lowpass(noise(n), 2500) * env_exp(n, 0.3) * 0.5, 2) * 0.9


# ------------------------------------------------------------------ tonal
def supersaw(midi, length, voices=5, detune=0.18, a=0.01, r=0.15, cutoff=5000):
    n = int((length + r) * SR)
    out = np.zeros(n)
    for v in range(voices):
        d = (v - (voices - 1) / 2) * detune / max(voices - 1, 1)
        out += saw(midi_hz(midi + d), n, phase=RNG.uniform(0, 2 * np.pi))
    out /= voices
    out = lowpass(out, cutoff)
    return out * env_adsr(n, a, 0.1, 0.8, r, length)


def chord(midis, length, **kw):
    out = None
    for m in midis:
        v = supersaw(m, length, **kw)
        out = v if out is None else out + v
    return out / len(midis)


def growl_bass(midi, length, cutoff=900, drive=3.0):
    n = int((length + 0.03) * SR)
    t = np.arange(n) / SR
    x = saw(midi_hz(midi), n) + 0.5 * square(midi_hz(midi) * 0.5, n, 15)
    # wobble cutoff at 1/8 notes feels "heavy electro"
    x = lowpass(x, cutoff)
    x = soft_clip(x, drive)
    return x * env_adsr(n, 0.004, 0.05, 0.85, 0.03, length) * 0.7


def pluck(midi, length=0.3, bright=4000, tau=0.12):
    n = int((length + 0.2) * SR)
    x = saw(midi_hz(midi), n) * 0.7 + square(midi_hz(midi), n, 12) * 0.3
    x = lowpass(x, bright)
    return x * env_exp(n, tau)


def fm_bell(midi, length=1.2, ratio=3.5, index=2.5, tau=0.5):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = midi_hz(midi)
    mod = np.sin(2 * np.pi * f * ratio * t) * index * env_exp(n, tau * 0.6)
    return np.sin(2 * np.pi * f * t + mod) * env_exp(n, tau) * 0.6


def music_box(midi, length=1.0):
    return fm_bell(midi, length, ratio=4.0, index=1.2, tau=0.35) * 0.8


def organ(midis, length, drawbars=(1.0, 0.8, 0.5, 0.35, 0.2, 0.12), vib=5.5):
    n = int((length + 0.3) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    harmonics = (1, 2, 3, 4, 6, 8)
    for m in midis:
        f = midi_hz(m) * (1 + 0.003 * np.sin(2 * np.pi * vib * t))
        ph = 2 * np.pi * np.cumsum(f) / SR
        for h, level in zip(harmonics, drawbars):
            if f[0] * h < SR * 0.45:
                out += level * np.sin(ph * h)
    out /= max(len(midis), 1) * sum(drawbars)
    return out * env_adsr(n, 0.04, 0.2, 0.9, 0.3, length)


def choir(midis, length, cutoff=1800):
    n = int((length + 0.6) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in midis:
        for d in (-0.08, 0.0, 0.09):
            f = midi_hz(m + d) * (1 + 0.004 * np.sin(2 * np.pi * 4.7 * t + d * 9))
            ph = 2 * np.pi * np.cumsum(f) / SR
            out += 0.5 * np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)
    out = bandpass(out, 250, cutoff)
    out /= max(len(midis) * 3, 1)
    return out * env_adsr(n, 0.35, 0.3, 0.85, 0.6, length) * 1.4


def nya(midi, length=0.35):
    """Cute 'meow'-like chirp: formant-ish pitch bend up then down."""
    n = int(length * SR)
    t = np.arange(n) / SR
    bend = np.sin(np.pi * t / length) * 4.0
    f = midi_hz(midi) * 2 ** (bend / 12)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)
    x = bandpass(x, 500, 4000)
    return x * env_adsr(n, 0.02, 0.1, 0.7, 0.1, length * 0.7) * 0.7


# ------------------------------------------------------------------ sad / lo-fi
def piano(midi, length=1.5, bright=1.0, tau=0.9):
    """Soft felt-ish piano: inharmonic partials with faster decay up high."""
    n = int((length + 0.4) * SR)
    t = np.arange(n) / SR
    f = midi_hz(midi)
    out = np.zeros(n)
    B = 0.0004                                   # string stiffness (inharmonicity)
    for k in range(1, 12):
        fk = f * k * np.sqrt(1 + B * k * k)
        if fk > 9000:
            break
        amp = (1.0 / k ** 1.25) * (bright if k > 3 else 1.0)
        out += amp * np.sin(2 * np.pi * fk * t + RNG.uniform(0, 6.28)) * np.exp(-t * (1 + 0.6 * k) / (tau * 2))
    hammer = bandpass(noise(n), 1500, 5000) * env_exp(n, 0.006) * 0.08
    rel = np.ones(n)
    off = int(length * SR)
    rel[off:] = np.linspace(1, 0, n - off) ** 2
    att = np.minimum(1, t / 0.004)
    return (out * 0.35 + hammer) * rel * att


def bass808(midi, length, glide_from=None, glide_time=0.09, drive=2.2):
    """Long 808 with optional pitch glide; saturated so it reads on small speakers."""
    n = int((length + 0.05) * SR)
    t = np.arange(n) / SR
    f1 = midi_hz(midi)
    if glide_from is not None:
        f0 = midi_hz(glide_from)
        f = f1 + (f0 - f1) * np.exp(-t / (glide_time / 3))
    else:
        f = f1 * (1 + 0.6 * np.exp(-t / 0.012))     # small pitch punch
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    x = soft_clip(x * 1.0, drive)
    env = np.exp(-t / max(length * 0.9, 0.2))
    off = int(length * SR)
    env[off:] *= np.linspace(1, 0, n - off)
    return x * env * np.minimum(1, t / 0.003) * 0.9


def vinyl(length, density=9.0):
    """Quiet tape hiss + random crackles."""
    n = int(length * SR)
    x = lowpass(noise(n), 6000) * 0.04
    k = int(length * density)
    for i in RNG.integers(0, n - 200, k):
        x[i:i + 60] += RNG.uniform(-1, 1) * env_exp(60, 0.0004) * RNG.uniform(0.2, 0.6)
    return x


def swell(x):
    """Reverse-envelope a sound (piano swell into a section)."""
    return x[::-1] * np.linspace(0, 1, len(x)) ** 2


def grand(midi, length=2.0, vel=0.7, pedal=True):
    """Acoustic-ish grand piano note.

    3 slightly detuned strings per note (beating / chorus), stretched
    inharmonic partials, two-stage decay (prompt + aftersound), velocity-
    dependent brightness, felt-hammer thump and a short soundboard body.
    """
    f0 = midi_hz(midi)
    ring = 6.0 if pedal else 0.6
    n = int((length + (1.5 if pedal else 0.25)) * SR)
    t = np.arange(n) / SR
    B = 0.00012 * 2 ** ((midi - 60) / 12)              # more stiffness up high
    # base decay: low notes ring longer
    tau0 = np.clip(ring * 2 ** (-(midi - 48) / 24), 0.6, 9.0)
    out = np.zeros(n)
    detune = ((0.0, 1.0), (+0.00045, 0.8), (-0.0005, 0.75)) if midi > 40 else ((0.0, 1.0), (+0.0004, 0.8))
    bright = 0.35 + 0.65 * vel
    for k in range(1, 20):
        fk = f0 * k * np.sqrt(1 + B * k * k)
        if fk > 7000:
            break
        # hammer striking ~1/8 of the string: soft notch near k=8
        amp = (1.0 / k ** (2.2 - 1.2 * bright)) * (0.4 + 0.6 * abs(np.sin(np.pi * k / 8.3)))
        tau_fast = tau0 * 0.18 / (1 + 0.25 * k)
        tau_slow = tau0 / (1 + 0.12 * k * k / bright)
        env = 0.65 * np.exp(-t / tau_fast) + 0.35 * np.exp(-t / tau_slow)
        for d, w in detune:
            out += w * amp * env * np.sin(2 * np.pi * fk * (1 + d) * t + RNG.uniform(0, 6.28))
    out /= sum(w for _, w in detune)
    thump = bandpass(noise(n), 120, 500 + 700 * vel) * env_exp(n, 0.008) * 0.06 * vel
    knock = bandpass(noise(n), 2000, 6000) * env_exp(n, 0.002) * 0.05 * vel
    x = out * 0.5 + thump + knock
    # soundboard body: two gentle resonances
    x = x + 0.25 * bandpass(x, 180, 450) + 0.12 * bandpass(x, 900, 2200)
    # damper: release after note-off (or after pedal lift)
    off = int(length * SR)
    if off < n:
        rel = np.ones(n)
        rel[off:] = np.exp(-np.arange(n - off) / SR / (0.35 if pedal else 0.08))
        x *= rel
    x *= np.minimum(1, t / 0.0015)
    return x * (0.25 + 0.75 * vel)


# ------------------------------------------------------------------ fx / mix
def reverb(x, wet=0.25, room=0.82, damp=3500, predelay=0.012):
    """Schroeder/Freeverb-style reverb with lfilter combs + allpasses."""
    combs = (1557, 1617, 1491, 1422, 1277, 1356)
    allpasses = (225, 556, 441)
    scale = SR / 44100
    pd = int(predelay * SR)
    src = np.concatenate([np.zeros(pd), x])[:len(x)]
    src = lowpass(src, damp)
    acc = np.zeros(len(x))
    for c in combs:
        d = int(c * scale)
        a = np.zeros(d + 1)
        a[0] = 1
        a[d] = -room
        acc += signal.lfilter([1.0], a, src)
    acc /= len(combs)
    for p in allpasses:
        d = int(p * scale)
        g = 0.5
        b = np.zeros(d + 1)
        a = np.zeros(d + 1)
        b[0], b[d] = -g, 1
        a[0], a[d] = 1, -g
        acc = signal.lfilter(b, a, acc)
    return x * (1 - wet) + acc * wet * 1.6


def delay(x, time_s, feedback=0.35, mix=0.25):
    d = int(time_s * SR)
    a = np.zeros(d + 1)
    a[0] = 1
    a[d] = -feedback
    wet = signal.lfilter([1.0], a, np.concatenate([np.zeros(d), x])[:len(x)])
    return x + wet * mix


def sidechain(x, kick_times, depth=0.6, release=0.18):
    g = np.ones(len(x))
    rel = int(release * SR)
    curve = 1 - depth * (1 - np.linspace(0, 1, rel) ** 1.5)
    for kt in kick_times:
        i = int(kt * SR)
        if i >= len(x):
            continue
        j = min(len(x), i + rel)
        g[i:j] = np.minimum(g[i:j], curve[:j - i])
    return x * g


def master(mix, target_peak=0.85, hp=140, glue=1.6):
    """Mastering for a small speaker: high-pass, glue, soft limit, normalise.

    The Coglet speaker cannot reproduce much below ~150 Hz; energy there only
    costs headroom and excursion, so it is removed steeply. Kicks and basses
    carry enough mid-range harmonics (soft clipping) to stay audible.
    """
    x = highpass(mix, hp, 4)
    # gentle presence boost (speaker sounds thin below ~400 Hz anyway)
    x = x + 0.25 * bandpass(x, 1500, 4500)
    x = x / (np.max(np.abs(x)) + 1e-9)
    x = soft_clip(x * glue, 1.4)         # glue / loudness
    x = x / (np.max(np.abs(x)) + 1e-9) * target_peak
    fade = int(0.02 * SR)
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade * 10:] *= np.linspace(1, 0, fade * 10)
    return x
