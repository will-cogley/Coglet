"""Three original ~30 s dance tracks for Coglet: Mecha, Evil, Cat.

Each composer writes audio into named buses AND marks musical events
(kick, snare, section changes, hits...). The same marks drive the
choreography, so music and dance can never drift apart.
"""
import numpy as np

import synth as S
from synth import note as N


# ====================================================================== MECHA
def mecha():
    """Heavy electro, 128 BPM, F minor. Intro / build / drop / outro."""
    T = S.Track(bpm=128, seconds=31.5)
    prog = [("F2", ["F3", "Ab3", "C4"]), ("Db2", ["Db3", "F3", "Ab3"]),
            ("Ab1", ["Ab3", "C4", "Eb4"]), ("Eb2", ["Eb3", "G3", "Bb3"])]
    kicks = []

    def kick_at(t, big=False):
        T.add("drums", t, S.kick(punch=1.2 if big else 1.0, f_hi=180, f_lo=50, drive=3.0), 1.0)
        kicks.append(t)
        T.mark(t, "kick", "big" if big else "")

    # ---- intro bars 0-3: four on the floor, offbeat hats, filtered bass, servo zaps
    T.mark(T.t(0), "section", "intro")
    for bar in range(0, 4):
        root = N(prog[bar % 4][0])
        for b in range(4):
            kick_at(T.t(bar, b))
            T.add("drums", T.t(bar, b + 0.5), S.hat(), 0.8)
        for s in range(8):
            cutoff = 300 + 1200 * ((bar * 8 + s) / 32)
            T.add("bass", T.t(bar, s * 0.5 + 0.25), S.growl_bass(root + (12 if s % 4 == 3 else 0), T.beat * 0.4, cutoff=cutoff), 0.8)
        if bar % 2 == 1:
            zap = S.fm_bell(N("F5"), 0.5, ratio=1.41, index=6, tau=0.12)
            T.add("fx", T.t(bar, 3.5), zap, 0.5)
            T.mark(T.t(bar, 3.5), "zap")

    # ---- build bars 4-7: snare roll, riser, opening chords
    T.mark(T.t(4), "section", "build")
    for bar in range(4, 8):
        if bar < 7:
            for b in range(4):
                kick_at(T.t(bar, b))
        step = {4: 1.0, 5: 0.5, 6: 0.25, 7: 0.125}[bar]
        b = 0.0
        while b < 4:
            vel = 0.2 + 0.35 * ((bar - 4) * 4 + b) / 16
            T.add("drums", T.t(bar, b), S.snare(snap=0.8), vel)
            if step >= 0.5 or int(b * 8) % 2 == 0:
                T.mark(T.t(bar, b), "snare")
            b += step
        ch = [N(x) for x in prog[bar % 4][1]]
        T.add("chords", T.t(bar), S.chord(ch, T.beat * 4, cutoff=500 + 900 * (bar - 4)), 0.55)
    T.add("fx", T.t(4), S.lowpass(S.riser(T.beat * 16, 300, 6000), 5000), 0.32)
    T.mark(T.t(7, 3.5), "breath")

    # ---- drop bars 8-13
    T.mark(T.t(8), "section", "drop")
    T.add("fx", T.t(8), S.impact(2.0), 0.9)
    T.add("drums", T.t(8), S.crash(), 0.8)
    T.mark(T.t(8), "hit")
    lead_motif = [(0, "C5", 0.5), (0.75, "C5", 0.25), (1, "Eb5", 0.5), (1.5, "F5", 1.0),
                  (2.75, "Ab5", 0.25), (3, "G5", 0.5), (3.5, "Eb5", 0.5)]
    for bar in range(8, 14):
        root = N(prog[bar % 4][0])
        for b in range(4):
            kick_at(T.t(bar, b), big=(b == 0))
            T.add("drums", T.t(bar, b + 0.5), S.hat(open_=True), 0.6)
        for b in (1, 3):
            T.add("drums", T.t(bar, b), S.clap(), 0.9)
            T.mark(T.t(bar, b), "snare")
        for s in range(8):
            oct_ = 12 if s in (3, 6) else 0
            T.add("bass", T.t(bar, s * 0.5), S.growl_bass(root + oct_, T.beat * 0.45, cutoff=1400, drive=4.0), 0.9)
        ch = [N(x) + 12 for x in prog[bar % 4][1]]
        for b in (0.5, 1.5, 2.5, 3.25, 3.75):
            T.add("chords", T.t(bar, b), S.chord(ch, T.beat * 0.3, cutoff=4500, r=0.08), 0.5)
        if bar % 2 == 0:
            for off, n_, ln in lead_motif:
                T.add("lead", T.t(bar, off), S.pluck(N(n_), T.beat * ln, bright=3500, tau=0.18), 0.45)
        T.mark(T.t(bar), "bar", bar - 8)

    # ---- outro bars 14-15
    T.mark(T.t(14), "section", "outro")
    for b in range(4):
        kick_at(T.t(14, b))
    T.add("chords", T.t(14), S.chord([N(x) + 12 for x in prog[0][1]], T.beat * 3.5, cutoff=3000), 0.5)
    for i, b in enumerate((0, 0.75, 1.5)):
        T.add("drums", T.t(15, b), S.tom(110 - i * 20), 0.9)
        T.mark(T.t(15, b), "tom", i)
    T.add("fx", T.t(15, 2), S.impact(2.5), 1.0)
    T.add("chords", T.t(15, 2), S.chord([N("F3"), N("C4"), N("F4")], T.beat * 3, cutoff=2500, r=1.2), 0.6)
    T.mark(T.t(15, 2), "end")

    T.sidechain = {"bass": (kicks, 0.65), "chords": (kicks, 0.55), "lead": (kicks, 0.3)}
    T.reverb = {"chords": 0.25, "lead": 0.3, "fx": 0.35, "drums": 0.08}
    T.gains = {"drums": 1.0, "bass": 0.75, "chords": 0.7, "lead": 0.8, "fx": 0.6}
    return T


# ====================================================================== EVIL
def evil():
    """Gothic, melancholic darkwave, 96 BPM half-time, D harmonic minor."""
    T = S.Track(bpm=96, seconds=31.5)
    prog = [("D2", ["D3", "F3", "A3"]), ("Bb1", ["Bb2", "D3", "F3"]),
            ("G1", ["G2", "Bb2", "D3"]), ("A1", ["A2", "C#3", "E3"])]
    kicks = []

    def toll(t, midi=N("D3"), g=0.8):
        T.add("bell", t, S.fm_bell(midi, 3.0, ratio=1.4, index=3.0, tau=1.1), g)
        T.mark(t, "toll")

    # ---- intro bars 0-1: bell + organ + choir
    T.mark(T.t(0), "section", "intro")
    for bar in range(0, 2):
        toll(T.t(bar))
        T.add("organ", T.t(bar), S.organ([N(x) for x in prog[bar][1]], T.beat * 4), 0.6)
    T.add("choir", T.t(1), S.choir([N("D4"), N("A4")], T.beat * 4), 0.6)

    # ---- verse bars 2-5: heavy half-time groove, organ arpeggio
    T.mark(T.t(2), "section", "verse")
    for bar in range(2, 6):
        root, ch = prog[bar % 4]
        chm = [N(x) for x in ch]
        for b in (0, 2.5):
            T.add("drums", T.t(bar, b), S.kick(punch=1.5, f_hi=130, f_lo=42, drive=2.0), 1.0)
            kicks.append(T.t(bar, b))
            T.mark(T.t(bar, b), "kick")
        T.add("drums", T.t(bar, 2), S.snare(length=0.4, tone=170), 0.9)
        T.mark(T.t(bar, 2), "snare")
        for s in range(8):
            T.add("drums", T.t(bar, s * 0.5 + 0.25), S.hat(), 0.35)
        arp = [chm[0] + 12, chm[1] + 12, chm[2] + 12, chm[1] + 12]
        for s in range(8):
            T.add("organ", T.t(bar, s * 0.5), S.organ([arp[s % 4]], T.beat * 0.45,
                                                      drawbars=(1, 0.6, 0.3, 0.2, 0.1, 0.05)), 0.45)
        T.add("bass", T.t(bar), S.lowpass(S.saw(S.midi_hz(N(root) + 12), int(T.beat * 4 * S.SR)), 400)
              * S.env_adsr(int(T.beat * 4 * S.SR), 0.02, 0.3, 0.8, 0.2), 0.7)
        T.add("choir", T.t(bar), S.choir(chm, T.beat * 4), 0.45)
        T.mark(T.t(bar), "bar", bar - 2)

    # ---- build bars 6-7: tom rolls, riser, organ swell
    T.mark(T.t(6), "section", "build")
    for bar in range(6, 8):
        step = 0.5 if bar == 6 else 0.25
        b = 0.0
        i = 0
        while b < 4:
            T.add("drums", T.t(bar, b), S.tom(95 + (i % 3) * 18), 0.5 + 0.5 * ((bar - 6) * 4 + b) / 8)
            if b == int(b):
                T.mark(T.t(bar, b), "tom", i % 3)
            b += step
            i += 1
        T.add("organ", T.t(bar), S.organ([N(x) + 12 for x in prog[bar % 4][1]], T.beat * 4), 0.55)
    T.add("fx", T.t(6), S.riser(T.beat * 8, 200, 5000), 0.55)

    # ---- climax bars 8-10: full, harmonic-minor lead
    T.mark(T.t(8), "section", "drop")
    T.add("drums", T.t(8), S.crash(2.5), 0.7)
    T.add("fx", T.t(8), S.impact(2.5), 0.8)
    toll(T.t(8), N("D2"), 0.9)
    T.mark(T.t(8), "hit")
    melody = [(0, "A4", 1.0), (1, "Bb4", 0.5), (1.5, "A4", 0.5), (2, "G4", 1.0), (3, "F4", 1.0),
              (4, "E4", 1.0), (5, "F4", 0.5), (5.5, "G4", 0.5), (6, "A4", 1.5), (7.5, "C#5", 0.5),
              (8, "D5", 2.0), (10, "C#5", 1.0), (11, "A4", 1.0)]
    for bar in range(8, 11):
        root, ch = prog[bar % 4]
        chm = [N(x) for x in ch]
        for b in (0, 1.5, 2.5, 3.5):
            T.add("drums", T.t(bar, b), S.kick(punch=1.4, f_hi=140, f_lo=44, drive=2.5), 1.0)
            kicks.append(T.t(bar, b))
            T.mark(T.t(bar, b), "kick")
        T.add("drums", T.t(bar, 2), S.snare(length=0.45, tone=170, snap=1.2), 1.0)
        T.mark(T.t(bar, 2), "snare")
        T.add("choir", T.t(bar), S.choir([m + 12 for m in chm], T.beat * 4, cutoff=2500), 0.6)
        T.add("organ", T.t(bar), S.organ(chm, T.beat * 4), 0.5)
        T.add("bass", T.t(bar), S.growl_bass(N(root) + 12, T.beat * 4, cutoff=600, drive=2.0), 0.6)
        T.mark(T.t(bar), "bar", bar - 8)
    for off, n_, ln in melody:
        T.add("lead", T.t(8, off), S.supersaw(N(n_), T.beat * ln, voices=5, detune=0.12, a=0.03, r=0.3, cutoff=3200), 0.55)

    # ---- outro bar 11: last toll, choir fades
    T.mark(T.t(11), "section", "outro")
    toll(T.t(11), N("D3"), 1.0)
    T.add("choir", T.t(11), S.choir([N("D4"), N("F4"), N("A4")], T.beat * 3, cutoff=2000), 0.7)
    T.add("organ", T.t(11), S.organ([N("D3"), N("A3"), N("D4")], T.beat * 3), 0.6)
    T.mark(T.t(11), "end")

    T.sidechain = {"bass": (kicks, 0.4), "choir": (kicks, 0.2)}
    T.reverb = {"bell": 0.45, "organ": 0.35, "choir": 0.5, "lead": 0.4, "drums": 0.22, "fx": 0.4}
    T.gains = {"drums": 1.0, "bell": 0.7, "organ": 0.6, "choir": 0.7, "bass": 0.6, "lead": 0.75, "fx": 0.5}
    return T


# ====================================================================== CAT
def cat():
    """Soft, cute anime future-bass, 120 BPM, C major (IV-V-iii-vi)."""
    T = S.Track(bpm=120, seconds=31.0)
    prog = [("F2", ["F4", "A4", "C5", "E5"]), ("G2", ["G4", "B4", "D5", "F5"]),
            ("E2", ["E4", "G4", "B4", "D5"]), ("A2", ["A4", "C5", "E5", "G5"])]
    kicks = []
    bells = [(0, "E6"), (0.5, "G6"), (1, "A6"), (1.5, "G6"), (2, "E6"), (3, "D6"),
             (4, "C6"), (4.5, "D6"), (5, "E6"), (6, "G6"), (6.5, "A6"), (7, "C7")]

    def nya(t, midi=N("A5")):
        T.add("fx", t, S.nya(midi), 0.55)
        T.mark(t, "nya")

    # ---- intro bars 0-1: music box + soft pad
    T.mark(T.t(0), "section", "intro")
    for off, n_ in bells:
        T.add("bell", T.t(0, off), S.music_box(N(n_) - 12, 1.2), 0.6)
    for bar in range(0, 2):
        T.add("chords", T.t(bar), S.chord([N(x) for x in prog[bar][1]], T.beat * 4, a=0.3, r=0.5, cutoff=1800), 0.35)
    nya(T.t(1, 3), N("E5"))

    # ---- groove bars 2-5
    T.mark(T.t(2), "section", "verse")
    for bar in range(2, 6):
        root, ch = prog[bar % 4]
        for b in (0, 2, 2.75):
            T.add("drums", T.t(bar, b), S.kick(punch=0.8, f_hi=150, f_lo=55, click=0.3, drive=1.8), 0.8)
            kicks.append(T.t(bar, b))
            T.mark(T.t(bar, b), "kick")
        for b in (1, 3):
            T.add("drums", T.t(bar, b), S.clap(), 0.7)
            T.mark(T.t(bar, b), "snare")
        for s in range(16):
            T.add("drums", T.t(bar, s * 0.25), S.shaker(), 0.5 if s % 2 else 0.3)
        for s in range(8):
            midi = N(root) + 12 + (12 if s % 2 else 0)
            T.add("bass", T.t(bar, s * 0.5), S.pluck(midi, T.beat * 0.4, bright=1800, tau=0.1), 0.7)
        T.add("chords", T.t(bar), S.chord([N(x) for x in ch], T.beat * 4, a=0.05, r=0.3, cutoff=2200), 0.3)
        for off, n_ in bells:
            if off < 4:
                T.add("bell", T.t(bar, off), S.music_box(N(n_) - 12 + (2 if bar % 2 else 0), 0.8), 0.35)
        T.mark(T.t(bar), "bar", bar - 2)
    nya(T.t(5, 3.5), N("G5"))

    # ---- build bars 6-7: rising stabs + gentle roll
    T.mark(T.t(6), "section", "build")
    for bar in range(6, 8):
        ch = [N(x) for x in prog[bar % 4][1]]
        for s in range(8):
            T.add("chords", T.t(bar, s * 0.5), S.chord([m + (s // 2) for m in ch], T.beat * 0.35, cutoff=1500 + 400 * s), 0.35)
        step = 0.5 if bar == 6 else 0.25
        b = 0.0
        while b < 4:
            T.add("drums", T.t(bar, b), S.snare(length=0.15, tone=260, snap=0.6), 0.25 + 0.4 * ((bar - 6) * 4 + b) / 8)
            if b == int(b):
                T.mark(T.t(bar, b), "snare")
            b += step
    T.add("fx", T.t(6), S.riser(T.beat * 8, 500, 8000), 0.4)
    for i, b in enumerate((0, 1, 2, 3)):
        nya(T.t(7, b), N("C5") + i * 3)

    # ---- chorus bars 8-13: future-bass chords, bells up an octave
    T.mark(T.t(8), "section", "drop")
    T.add("drums", T.t(8), S.crash(1.5), 0.5)
    T.mark(T.t(8), "hit")
    syncopation = (0, 0.75, 1.5, 2.25, 3.0, 3.5)
    for bar in range(8, 14):
        root, ch = prog[bar % 4]
        chm = [N(x) for x in ch]
        for b in (0, 1.5, 2, 3.5):
            T.add("drums", T.t(bar, b), S.kick(punch=0.9, f_hi=160, f_lo=55, click=0.35, drive=2.0), 0.85)
            kicks.append(T.t(bar, b))
            T.mark(T.t(bar, b), "kick")
        for b in (1, 3):
            T.add("drums", T.t(bar, b), S.clap(), 0.8)
            T.mark(T.t(bar, b), "snare")
        for s in range(8):
            T.add("drums", T.t(bar, s * 0.5 + 0.5 * 0), S.hat(), 0.3)
        for b in syncopation:
            stab = S.chord(chm, T.beat * 0.4, voices=7, detune=0.25, cutoff=5000, r=0.12)
            # future-bass "wobble": quick volume LFO inside the stab
            lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 12 * np.arange(len(stab)) / S.SR)
            T.add("chords", T.t(bar, b), stab * lfo, 0.55)
        T.add("bass", T.t(bar), S.growl_bass(N(root) + 12, T.beat * 4, cutoff=700, drive=1.5), 0.5)
        for off, n_ in bells:
            if off < 4:
                T.add("bell", T.t(bar, off), S.music_box(N(n_), 0.7), 0.4)
        if bar in (9, 11, 13):
            nya(T.t(bar, 3.5), N("A5") if bar != 13 else N("C6"))
        T.mark(T.t(bar), "bar", bar - 8)

    # ---- outro bar 14: sparkle arpeggio + final chord
    T.mark(T.t(14), "section", "outro")
    for i, n_ in enumerate(("C6", "E6", "G6", "C7", "E7")):
        T.add("bell", T.t(14, i * 0.25), S.music_box(N(n_), 1.5), 0.5)
    T.add("chords", T.t(14, 1.5), S.chord([N("C5"), N("E5"), N("G5"), N("B5")], T.beat * 2, a=0.02, r=1.0, cutoff=4000), 0.5)
    nya(T.t(14, 1.5), N("E6"))
    T.mark(T.t(14, 1.5), "end")

    T.sidechain = {"chords": (kicks, 0.6), "bass": (kicks, 0.5), "bell": (kicks, 0.15)}
    T.reverb = {"bell": 0.4, "chords": 0.3, "fx": 0.3, "drums": 0.1}
    T.gains = {"drums": 0.9, "bass": 0.6, "chords": 0.75, "bell": 0.8, "fx": 0.7}
    return T


# ======================================================================= SAD
def sad():
    """Solo piano, melancholic, 68 BPM, F minor.

    i-VI-III-VII (Fm Db Ab Eb), then iv -> V (Bbm -> C) and home to Fm.
    Left hand: low root + flowing 8th-note broken chords with the pedal down.
    Right hand: an original singing melody. No drums, no synths.
    """
    T = S.Track(bpm=68, seconds=33.8)
    rng = np.random.default_rng(11)
    chords = {  # root (low octave), chord tones for the broken-chord pattern
        "Fm": ("F2", ["F3", "C4", "Ab4"]), "Db": ("Db2", ["Db3", "Ab3", "F4"]),
        "Ab": ("Ab2", ["Ab3", "Eb4", "C5"]), "Eb": ("Eb2", ["Eb3", "Bb3", "G4"]),
        "Bbm": ("Bb1", ["Bb2", "F3", "Db4"]), "C": ("C2", ["C3", "G3", "E4"]),
    }
    plan = ["Fm", "Db", "Fm", "Db", "Ab", "Eb", "Bbm", "C", "Fm"]
    melody = {   # bar -> [(beat, note, beats, velocity)]
        2: [(0, "Ab4", 0.5, .55), (0.5, "C5", 0.5, .58), (1, "F5", 2, .66), (3, "Eb5", 0.5, .55), (3.5, "C5", 0.5, .52)],
        3: [(0, "Db5", 1.5, .6), (1.5, "C5", 0.5, .52), (2, "Ab4", 2, .5)],
        4: [(0, "C5", 0.5, .58), (0.5, "Eb5", 0.5, .62), (1, "Ab5", 1.5, .72), (2.5, "G5", 0.5, .6), (3, "F5", 0.5, .58), (3.5, "Eb5", 0.5, .55)],
        5: [(0, "Eb5", 1, .62), (1, "Db5", 0.5, .55), (1.5, "C5", 0.5, .52), (2, "Bb4", 2, .5)],
        6: [(0, "Db5", 0.5, .7), (0.5, "F5", 0.5, .74), (1, "Bb5", 1.5, .85), (2.5, "Ab5", 0.5, .72), (3, "F5", 1, .7)],
        7: [(0, "E5", 1, .78), (1, "G5", 0.5, .8), (1.5, "F5", 0.5, .7), (2, "E5", 1, .68), (3, "C5", 1, .6)],
    }
    pattern = (0, 1, 2, 1, 2, 1, 0, 1)        # indices into chord tones, 8ths

    def hum(t, amount=0.012):                  # tiny human timing
        return t + rng.uniform(-amount, amount)

    def play(t, name, beats, vel, bus="keys"):
        T.add(bus, hum(t), S.grand(N(name) if isinstance(name, str) else name, beats * T.beat, vel), 1.0)

    for bar, cname in enumerate(plan):
        if bar == 0:
            T.mark(T.t(0), "section", "intro")
        elif bar == 2:
            T.mark(T.t(2), "section", "verse")
        elif bar == 6:
            T.mark(T.t(6), "section", "climax")
        elif bar == 8:
            T.mark(T.t(8), "section", "outro")
        root, tones = chords[cname]
        T.mark(T.t(bar), "bar", bar)
        T.mark(T.t(bar), "chord", cname)
        climax = bar in (6, 7)
        lh = 0.42 + (0.15 if climax else 0.0) - (0.08 if bar < 2 else 0.0)

        if bar == 8:
            # final: rolled Fm chord, slight ritardando, let it ring
            roll = ["F1", "F2", "C3", "F3", "Ab3", "C4", "F4"]
            t0 = T.t(8) + 0.12
            for i, n_ in enumerate(roll):
                play(t0 + i * 0.06, n_, 6, 0.5 - 0.02 * i)
            play(t0 + 0.5, "F5", 6, 0.55)
            play(t0 + 0.5, "C5", 6, 0.4)
            T.mark(t0, "end")
            break

        play(T.t(bar), N(root), 4, lh + 0.1)
        if climax:
            play(T.t(bar), N(root) + 12, 4, lh)       # octave bass
        for i, idx in enumerate(pattern):
            v = lh * (1.0 if i % 2 == 0 else 0.82)
            play(T.t(bar, i * 0.5), N(tones[idx]), 1.2, v)
        for b in range(4):
            T.mark(T.t(bar, b), "beat", b)

        for beat, n_, ln, v in melody.get(bar, ()):
            play(T.t(bar, beat), n_, ln, v)
            if climax:                              # octave below, softer
                play(T.t(bar, beat), N(n_) - 12, ln, v * 0.55)
            T.mark(T.t(bar, beat), "note", N(n_))

    T.reverb = {"keys": 0.32}
    T.glue = 1.2           # keep the piano dynamics (less limiting)
    T.gains = {"keys": 0.9}
    return T

TRACKS = {"mecha": mecha, "evil": evil, "cat": cat, "sad": sad}
