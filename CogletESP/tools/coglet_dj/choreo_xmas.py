"""Choreography for the three Christmas tracks (xmas.py), written against the
same scores so every move lands on a real note.

Principle: hit the moments that matter (phrase starts, the melody's peaks,
cymbals and bells), flow in between, and hold still now and then. Most beats
get no move at all.

Besides the classic move vocabulary (see choreo.py), these dances use two
generic moves implemented in RP2040/music.py:
  ("to",    (servo, angle[, speed_deg_s]))   move and stay (optionally at a set speed)
  ("pulse", (servo, angle, hold_ms))         go there, come back to the resting angle

Angle conventions (RP2040/animation.py):
  PIT smaller = head up (32 proud .. 50 neutral .. 74 bowed)
  ROL / YAW / EYL / EYR 90 = centre
  EAL / EAR mirrored: ears up = EAL smaller, EAR larger
  LID 150 open, 160 wide, ~102 closed;  MOU 150 closed, smaller = open

python3 choreo_xmas.py  ->  out/xmas_<name>_choreo.json
"""
import json
import os
import sys

import xmas as X

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Same tempo / meter / length as the rendered tracks in xmas.py.
TIMING = {
    "lyrical": {"bpm": 104, "bpb": 3, "seconds": 31.5},
    "classic": {"bpm": 136, "bpb": 4, "seconds": 32.0},
    "grand": {"bpm": 84, "bpb": 2, "seconds": 32.5},
}


class Dance:
    def __init__(self, name):
        tm = TIMING[name]
        self.name = name
        self.beat = 60.0 / tm["bpm"]
        self.bpb = tm["bpb"]
        self.seconds = tm["seconds"]
        self.moves = []

    def t(self, bar, beat=0.0):
        return (bar * self.bpb + beat) * self.beat

    def add(self, t, move, arg=None):
        self.moves.append({"t_ms": int(round(t * 1000)), "move": move, "arg": arg})

    def to(self, t, servo, angle, speed=None):
        arg = [servo, int(round(angle))] + ([int(round(speed))] if speed else [])
        self.add(t, "to", arg)

    def pulse(self, t, servo, angle, hold_ms):
        self.add(t, "pulse", [servo, int(round(angle)), int(hold_ms)])

    def notes(self, bar, melody):
        """Start time of every note of one bar."""
        beat = 0.0
        out = []
        for beats, name in melody:
            if name is not None:
                out.append((self.t(bar, beat), name, beats))
            beat += beats
        return out

    def finish(self):
        # The final pose comes 1.5 s before the music ends: the RP2040 holds it
        # for 1.2 s (END_HOLD_MS) and then hands back exactly when the music
        # stops, so Coglet settles into its normal pose before the follow-up
        # session starts (as the standard dances do).
        end_ms = int(self.seconds * 1000) - 1500
        self.add(end_ms / 1000.0, "pose_end", self.name)
        moves = sorted(self.moves, key=lambda m: (m["t_ms"], m["move"] == "pose_end"))
        out, last = [], {}
        for m in moves:
            if m["move"] != "pose_end" and m["t_ms"] >= end_ms:
                continue
            key = (m["move"], m["arg"][0] if m["move"] in ("to", "pulse") else None)
            if key in last and m["t_ms"] - last[key] < 90:      # servo safety
                continue
            last[key] = m["t_ms"]
            out.append(m)
        return out


# ------------------------------------------------------------------ lyrical
def lyrical():
    """Silent Night: eyes closed the whole time, as if dreaming along. A waltz
    sway in three with the base and the neck, a soft nod on each downbeat,
    ears and a quiet hum (mouth) on the long notes. The face lifts towards the
    two high points ('All is calm', 'Sleep in heavenly peace') and sinks a
    little lower with every 'sleep', ending curled up asleep."""
    D = Dance("lyrical")
    intro, verse = 2, X.LYRICAL_VERSE
    last_bar = intro + len(verse) - 1
    bar_s = D.bpb * D.beat

    # how high the face is in each verse bar (smaller PIT = higher)
    face = {0: 50, 2: 50, 4: 40, 6: 46, 8: 42, 9: 36, 10: 50, 11: 42, 12: 54, 13: 58}
    ears = {4: (98, 102), 8: (100, 100), 9: (92, 108), 11: (100, 100), 12: (124, 76), 13: (132, 68)}

    D.to(0.0, "LID", 104, 30)                               # eyes close and stay closed
    D.to(0.0, "PIT", 56, 10)                                # intro: a slow breath in ...
    D.to(D.t(1), "PIT", 50, 10)                             # ... and out
    for bar in range(0, last_bar):
        side = 1 if bar % 2 == 0 else -1
        t = D.t(bar)
        D.to(t, "YAW", 90 + 13 * side, 20)                  # waltz sway, arriving by the next bar
        D.to(t, "ROL", 90 - 8 * side, 12)                   # the neck leans the other way
        D.to(t, "EYL", 90 + 6 * side, 12)
        D.to(t, "EYR", 90 + 6 * side, 12)
        if bar >= intro:
            D.pulse(t, "PIT", _held_face(face, bar - intro) + 6, 420)   # soft nod on "one"
        i = bar - intro
        if i in face:
            D.to(t + 0.05, "PIT", face[i], 24)
        if i in ears:
            D.to(t, "EAL", ears[i][0], 30)
            D.to(t, "EAR", ears[i][1], 30)
        elif i in (1, 3, 5, 7, 10):                          # long notes: ears breathe, a hum
            k = 1 if i % 4 == 1 else -1
            D.pulse(t, "EAL" if k > 0 else "EAR", 104 if k > 0 else 96, int(bar_s * 600))
            D.pulse(t + D.beat * 0.5, "MOU", 124, int(bar_s * 550))
        if i in (6, 7):                                     # "all is bright": a tender tilt
            D.pulse(t + D.beat, "ROL", 90 + 12 * side, int(D.beat * 1500))

    # last chord: curled up asleep, a long sigh
    t = D.t(last_bar)
    for servo, angle, speed in (("PIT", 66, 10), ("YAW", 90, 10), ("ROL", 97, 8),
                                ("EAL", 138, 20), ("EAR", 62, 20), ("EYL", 90, 10), ("EYR", 90, 10),
                                ("LID", 102, 10)):
        D.to(t, servo, angle, speed)
    D.pulse(t + 0.4, "MOU", 120, 900)
    return D.finish()


def _held_face(face, i):
    """The face height in force at verse bar i."""
    keys = [k for k in face if k <= i]
    return face[max(keys)] if keys else 50


# ------------------------------------------------------------------ classic
def classic():
    """Jingle Bells: the bells shake the ears, Coglet mouths its 'ho ho ho',
    ears ring on 'jingle bells', the base swings on 'jingle all the way',
    the head rocks like a sleigh, and everything freezes on 'hey!'. The second
    chorus is bigger."""
    D = Dance("classic")
    b = D.beat

    # intro: bell shake + ho ho ho (xmas.santa_ho at bar 0, beat 0.4)
    for k in range(8):
        D.add(D.t(0, k * 0.5), "ear_L" if k % 2 == 0 else "ear_R")
    ho0 = D.t(0, 0.4)
    for k in range(3):
        t = ho0 + k * 0.39
        D.pulse(t, "MOU", 95, 230)
        D.pulse(t, "PIT", 52, 140)

    for chorus in range(2):
        amp = 1.0 if chorus == 0 else 1.35
        first = 1 + 8 * chorus
        # "Jin-gle bells, jin-gle bells": ears ring left, right, then both + a nod
        for k, bar in enumerate((first, first + 1)):
            D.add(D.t(bar, 0), "ear_L")
            D.add(D.t(bar, 1), "ear_R")
            D.add(D.t(bar, 2), "ears")
            D.add(D.t(bar, 2), "nod", "small" if chorus == 0 else "big")
            D.add(D.t(bar, 0), "eyes", "L" if k == 0 else "R")
        # "jin-gle all the way": a big swing of the base, eyes leading
        bar = first + 2
        D.to(D.t(bar, 0), "YAW", 90 - 20 * amp)
        D.add(D.t(bar, 0), "eyes", "L")
        D.to(D.t(bar, 2), "YAW", 90 + 20 * amp)
        D.add(D.t(bar, 2), "eyes", "R")
        D.add(D.t(bar, 3.5), "blink")
        # "...way": settle with a tilt
        bar = first + 3
        D.to(D.t(bar, 0), "YAW", 90)
        D.add(D.t(bar, 0), "eyes", "C")
        D.pulse(D.t(bar, 0), "ROL", 90 - 16 * amp, 700)
        # "Oh what fun it is to ride...": rocking like a sleigh, nods on 1 and 3
        rock_bars = range(first + 4, first + 7) if chorus == 0 else range(first + 4, first + 6)
        for k, bar in enumerate(rock_bars):
            for half in (0, 2):
                side = 1 if (k * 2 + half // 2) % 2 == 0 else -1
                D.to(D.t(bar, half), "ROL", 90 + 13 * amp * side)
                D.add(D.t(bar, half), "eyes", "R" if side > 0 else "L")
                D.add(D.t(bar, half), "nod", "small")
            if k == 1:                                     # the quick B-B: ears flick
                D.add(D.t(bar, 3), "ear_L")
                D.add(D.t(bar, 3.5), "ear_R")
        if chorus == 0:
            # bar 8: "...o-pen sleigh, HEY!" -> freeze on the high D
            bar = first + 7
            D.to(D.t(bar, 0), "ROL", 90)
            D.add(D.t(bar, 0), "eyes", "C")
            t = D.t(bar, 2)
            D.to(t, "EAL", 68)
            D.to(t, "EAR", 132)
            D.to(t, "PIT", 32)
            D.pulse(t, "LID", 160, 600)
            D.pulse(t, "MOU", 70, 450)
            t = D.t(bar + 1)                               # and back for the second chorus
            D.to(t, "EAL", 110)
            D.to(t, "EAR", 90)
            D.to(t, "PIT", 45)
    # bar 15 "o-pen sleigh" (D-D-C-A): head straight, two big nods, ears answer
    D.to(D.t(15, 0), "ROL", 90)
    D.add(D.t(15, 0), "nod", "big")
    D.add(D.t(15, 1), "nod", "big")
    D.add(D.t(15, 2), "ear_L")
    D.add(D.t(15, 3), "ear_R")
    D.add(D.t(15, 0), "eyes", "C")
    # bar 16: final G chord + bells: proud pose, a wink, bells shake the ears
    t = D.t(16)
    D.to(t, "PIT", 32)
    D.to(t, "ROL", 100)
    D.to(t, "EAL", 72)
    D.to(t, "EAR", 128)
    for k in range(4):
        D.pulse(t + 0.25 + k * 0.22, "EAL" if k % 2 == 0 else "EAR", 52 if k % 2 == 0 else 148, 110)
    D.pulse(t + 1.3, "LID", 105, 160)                      # wink
    return D.finish()


# ------------------------------------------------------------------ grand
def grand():
    """Joy to the World, big and on the beat: rises from a bow with the timpani,
    ears snap up with the brass. The head walks down the descending scale one
    note at a time while the base sweeps across the room, and climbs back up on
    'Let earth receive her King'. The running bars swing and lean on every
    beat, the repeated notes ring the ears, the cymbal throws the head up
    singing, and the final chord is held proud before a bow."""
    D = Dance("grand")
    tune = X.GRAND_TUNE
    intro = 2

    # timpani roll: rise from the bow
    D.to(0.0, "PIT", 42, 30)
    D.to(0.0, "LID", 145, 40)
    D.to(0.0, "EAL", 118, 40)
    D.to(0.0, "EAR", 82, 40)
    # brass + cymbal: ears snap up, eyes flash, a proud tilt and a nod
    t = D.t(1)
    D.to(t, "EAL", 78, 500)
    D.to(t, "EAR", 124, 500)
    D.pulse(t, "LID", 160, 600)
    D.pulse(t, "ROL", 104, 520)
    D.add(D.t(1, 1), "nod", "big")

    # "Joy to the world, the Lord is come": one step down per note, the base
    # sweeping from one side of the room to the other
    descent = []
    for i in range(4):
        descent += D.notes(intro + i, tune[i])
    descent = descent[:8]                                  # D5 C#5 B4 A4 G4 F#4 E4 D4
    for k, (t, _, _) in enumerate(descent):
        D.to(t, "PIT", 26 + 6 * k, 160)
        D.to(t, "YAW", 64 + 52 * k / 7.0, 130)
        D.to(t, "EYL", 84 + 12 * k / 7.0, 200)
        D.to(t, "EYR", 84 + 12 * k / 7.0, 200)
        D.to(t, "EAL", 80 + 7 * k, 250)
        D.to(t, "EAR", 122 - 7 * k, 250)
    # "Let earth receive her King": climb back up to the centre
    ascent = D.notes(intro + 3, tune[3])[1:] + D.notes(intro + 4, tune[4]) + \
        D.notes(intro + 5, tune[5]) + D.notes(intro + 6, tune[6])[:1]
    n = len(ascent)
    for k, (t, _, _) in enumerate(ascent):
        f = (k + 1) / float(n)
        D.to(t, "PIT", 68 - 40 * f, 160)
        D.to(t, "YAW", 116 - 26 * f, 130)
        D.to(t, "EAL", 128 - 48 * f, 250)
        D.to(t, "EAR", 72 + 50 * f, 250)
        D.to(t, "EYL", 96 - 6 * f, 200)
        D.to(t, "EYR", 96 - 6 * f, 200)
    t_king = ascent[-1][0]
    D.add(t_king, "ears")
    D.pulse(t_king, "LID", 160, 600)
    D.pulse(t_king, "MOU", 80, 600)

    # "Let every heart prepare him room" (running notes): swing and lean on
    # every beat, alternating sides each bar
    for k, bar in enumerate(range(intro + 7, intro + 11)):
        side = 1 if k % 2 == 0 else -1
        D.to(D.t(bar, 0), "YAW", 90 + 28 * side, 150)
        D.add(D.t(bar, 0), "eyes", "R" if side > 0 else "L")
        D.add(D.t(bar, 0), "nod", "big")
        D.to(D.t(bar, 1), "ROL", 90 - 14 * side, 120)
        D.add(D.t(bar, 1), "ear_R" if side > 0 else "ear_L")
        D.add(D.t(bar, 1), "nod", "small")

    # "And heaven and nature sing" x2: repeated notes ring the ears, the long
    # notes lean far out, first one way then the other
    for k, (ring, lean) in enumerate(((intro + 11, intro + 12), (intro + 13, intro + 14))):
        side = 1 if k == 0 else -1
        D.to(D.t(ring, 0), "YAW", 90, 150)
        D.to(D.t(ring, 0), "ROL", 90, 120)
        D.add(D.t(ring, 0), "eyes", "C")
        for e in range(4):
            D.add(D.t(ring, e * 0.5), "ear_L" if e % 2 == 0 else "ear_R")
        D.add(D.t(ring, 0), "nod", "small")
        D.add(D.t(ring, 1), "nod", "small")
        t = D.t(lean, 0)
        D.to(t, "ROL", 90 + 15 * side, 120)
        D.to(t, "YAW", 90 + 22 * side, 130)
        D.to(t, "PIT", 36, 160)
        D.add(t, "eyes", "R" if side > 0 else "L")
        D.pulse(t, "MOU", 90, 700)
        D.add(D.t(lean, 1), "nod", "small")

    # cymbal + the high D: head thrown up, singing
    bar = intro + 15
    D.to(D.t(bar, 0), "YAW", 90, 150)
    D.to(D.t(bar, 0), "ROL", 90, 120)
    D.add(D.t(bar, 0), "eyes", "C")
    t = D.t(bar, 0.5)
    D.to(t, "PIT", 26, 200)
    D.to(t, "EAL", 74, 500)
    D.to(t, "EAR", 128, 500)
    D.pulse(t, "LID", 160, 800)
    D.pulse(t, "MOU", 60, 700)
    D.add(D.t(bar, 1.5), "nod", "small")
    # "and heaven, and nature sing": nods with a tilt to each side, then the cadence
    bar = intro + 16
    D.to(D.t(bar, 0), "PIT", 38, 160)
    D.add(D.t(bar, 0), "nod", "big")
    D.pulse(D.t(bar, 0), "ROL", 76, 500)
    D.add(D.t(bar, 1), "nod", "big")
    D.pulse(D.t(bar, 1), "ROL", 104, 500)
    bar = intro + 17
    D.to(D.t(bar, 0), "PIT", 42, 160)
    D.add(D.t(bar, 0), "ears")
    D.to(D.t(bar, 1), "PIT", 46, 160)
    D.add(D.t(bar, 1), "nod", "small")

    # final chord: proud and still, singing the last note ... then a bow
    t = D.t(intro + len(tune) - 1)
    D.to(t, "PIT", 28, 200)
    D.to(t, "EAL", 74, 300)
    D.to(t, "EAR", 126, 300)
    D.to(t, "LID", 150, 200)
    D.pulse(t, "MOU", 70, 1000)
    bow = t + 1.2
    D.to(bow, "PIT", 74, 45)
    D.to(bow, "LID", 116, 40)
    D.to(bow, "EAL", 138, 60)
    D.to(bow, "EAR", 62, 60)
    return D.finish()


DANCES = {"lyrical": lyrical, "classic": classic, "grand": grand}


def main(names):
    os.makedirs(OUT, exist_ok=True)
    for n in names or list(DANCES):
        moves = DANCES[n]()
        tm = TIMING[n]
        with open(os.path.join(OUT, "xmas_{}_choreo.json".format(n)), "w") as f:
            json.dump({"track": n, "bpm": tm["bpm"], "duration_ms": int(tm["seconds"] * 1000),
                       "moves": moves}, f, indent=1)
        beats = tm["seconds"] / (60.0 / tm["bpm"])
        on_beat = len({m["t_ms"] for m in moves})
        print("{:<8} {:>3} moves at {:>3} moments over ~{:.0f} beats".format(n, len(moves), on_beat, beats))


if __name__ == "__main__":
    main(sys.argv[1:])
