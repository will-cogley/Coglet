"""Choreography for the three Snowman tracks (snow.py), written against the
same scores so every move lands on a real note. Same principle and move
vocabulary as choreo_xmas.py: hit the moments that matter, flow or hold
still in between.

The snowman is soft, slow and a little clumsy: it dozes off to the lullaby,
waddles through deep snow (and gets hit by snowballs), and is swept around
by the blizzard until it freezes solid.

python3 choreo_snow.py  ->  out/snow_<name>_choreo.json
"""
import json
import os
import sys

import choreo_xmas as C
import snow as W

OUT = C.OUT

# Same tempo / meter / length as the rendered tracks in snow.py.
TIMING = {
    "lullaby": {"bpm": 104, "bpb": 3, "seconds": 32.5},
    "stomp": {"bpm": 108, "bpb": 4, "seconds": 32.5},
    "blizzard": {"bpm": 150, "bpb": 3, "seconds": 32.0},
}
C.TIMING.update(TIMING)
Dance = C.Dance


# ------------------------------------------------------------------ lullaby
def lullaby():
    """Brahms' Lullaby: eyes open at first, getting sleepier every line
    (lids lower, the head sinks, the sway gets slower). It startles awake
    once at the end of the first half, glances at the wind chimes, yawns
    on the rising F G A, and is asleep by the last chord."""
    D = Dance("lullaby")
    intro = 1
    bars = len(W.LULLABY_TUNE)
    D.to(0.0, "LID", 150, 60)
    D.to(0.0, "PIT", 46, 20)
    # sleepiness per line of four bars: lids, head, ears
    lines = [(148, 46, 104, 96), (136, 52, 112, 88), (126, 56, 118, 82), (114, 62, 126, 74)]
    for i in range(bars - 1):
        bar = intro + i
        t = D.t(bar)
        side = 1 if i % 2 == 0 else -1
        lid, pit, eal, ear = lines[min(3, i // 4)]
        slow = 1.0 - 0.12 * (i // 4)
        # rocking: the neck every bar, the base every two bars
        D.to(t, "ROL", 90 + 8 * side, 14 * slow)
        if i % 2 == 0:
            D.to(t, "YAW", 90 + 12 * side, 10 * slow)
            D.add(t, "eyes", "R" if side > 0 else "L")
        if i % 4 == 0:
            D.to(t, "LID", lid, 30)
            D.to(t, "PIT", pit, 10)
            D.to(t, "EAL", eal, 40)
            D.to(t, "EAR", ear, 40)
        elif i % 4 == 2:
            D.pulse(t, "PIT", pit + 4, 500)          # nodding off a little
        if i in (3, 11):                              # wind chimes: a sleepy glance up
            D.add(D.t(bar, 1), "eyes", "C")
            D.pulse(D.t(bar, 1), "PIT", pit - 6, 700)
    # end of the first half (bar 7, the long C): startled awake for a moment
    t = D.t(intro + 7, 0)
    D.pulse(t, "LID", 158, 500)
    D.pulse(t, "PIT", 38, 450)
    D.add(t, "ears")
    D.add(t + 0.7, "blink")
    # the rising F G A (bar 10): a big yawn
    t = D.t(intro + 10, 0)
    D.pulse(t, "MOU", 70, 1200)
    D.pulse(t, "PIT", 40, 1100)
    D.pulse(t + 0.2, "LID", 108, 900)
    # last chord: asleep
    t = D.t(intro + bars - 1)
    for servo, angle, speed in (("PIT", 66, 10), ("YAW", 90, 10), ("ROL", 96, 8), ("LID", 102, 14),
                                ("EAL", 136, 20), ("EAR", 64, 20), ("EYL", 90, 10), ("EYR", 90, 10)):
        D.to(t, servo, angle, speed)
    return D.finish()


# ------------------------------------------------------------------ stomp
def stomp():
    """Good King Wenceslas: a heavy waddle (the neck rocks on 1 and 3, the
    head bobs with the step), eyes on the path. Two snowballs hit in the
    gaps: Coglet recoils, blinks and shakes it off. The second half gets
    bolder; the last snowball gets a wink."""
    D = Dance("stomp")
    intro = 1
    # intro: four steps into the snow
    for k in range(4):
        D.to(D.t(0, k), "ROL", 90 + (7 if k % 2 == 0 else -7), 90)
    D.to(0.0, "PIT", 50, 60)

    def hit(t, side, wink=False):
        D.pulse(t, "PIT", 32, 260)
        D.pulse(t, "ROL", 90 + 16 * side, 300)
        D.pulse(t, "LID", 160, 300)
        D.add(t, "ears")
        D.add(t + 0.32, "blink")
        D.pulse(t + 0.5, "YAW", 78, 120)          # shake it off
        D.pulse(t + 0.65, "YAW", 102, 120)
        if wink:
            D.pulse(t + 0.85, "LID", 104, 160)

    for i in range(len(W.STOMP_TUNE) - 1):
        bar = intro + i
        bold = i >= 8
        amp = 1.3 if bold else 1.0
        for b in (0, 2):
            side = 1 if b == 0 else -1
            if i in W.STOMP_SNOWBALLS and b == 2:
                continue                              # the gap with the snowball
            D.to(D.t(bar, b), "ROL", 90 + 9 * amp * side, 110)
            D.pulse(D.t(bar, b), "PIT", 56, 140)      # the step sinks in
        if i % 2 == 0:
            D.to(D.t(bar, 0), "YAW", 90 + (10 if i % 4 == 0 else -10) * amp, 60)
            D.add(D.t(bar, 0), "eyes", "R" if i % 4 == 0 else "L")
        if i in (4, 10):                              # D C B A: the head steps down
            for j, (tn, _, _) in enumerate(D.notes(bar, W.STOMP_TUNE[i])):
                D.to(tn, "PIT", 40 + 4 * j, 200)
        if i in W.STOMP_SNOWBALLS:
            hit(D.t(bar, 2.5), 1 if i == 3 else -1)
        if i == 8:                                    # bolder: ears up, eyes open
            D.to(D.t(bar), "EAL", 84, 400)
            D.to(D.t(bar), "EAR", 116, 400)
            D.to(D.t(bar), "LID", 152, 300)
    # last bar: stand proud ... and one more snowball, with a wink
    t = D.t(intro + len(W.STOMP_TUNE) - 1)
    D.to(t, "ROL", 90, 110)
    D.to(t, "YAW", 90, 60)
    D.to(t, "PIT", 40, 120)
    D.add(t, "eyes", "C")
    hit(t + 1.4, 1, wink=True)
    return D.finish()


# ------------------------------------------------------------------ blizzard
def blizzard():
    """Shchedryk as a blizzard: the eyes follow the bells, the base drifts
    down with the bass, ears flutter on the quick notes, then the head is
    swept around in circles that grow to the climax; it calms down as the
    music thins out, and at the crack of ice it freezes in one snap."""
    D = Dance("blizzard")
    D.to(0.0, "PIT", 46, 60)
    yaw = 90
    for bar in range(25):
        t = D.t(bar)
        if bar < 4:                                   # the bells alone: eyes follow
            D.add(t, "eyes", "L")
            D.add(D.t(bar, 2), "eyes", "R")
            if bar == 3:
                D.add(D.t(bar, 2), "eyes", "C")
        elif bar < 8:                                 # the bass walks down: the base drifts
            yaw -= 4
            D.to(t, "YAW", yaw, 30)
            D.pulse(t, "PIT", 50, 300)
        elif bar < 12:                                # second voice: sway, ears flutter
            side = 1 if bar % 2 == 0 else -1
            D.to(t, "ROL", 90 + 9 * side, 120)
            D.add(D.t(bar, 1), "ear_L")
            D.add(D.t(bar, 1.5), "ear_R")
            if bar == 8:
                D.to(t, "YAW", 90, 60)
        elif bar < 16:                                # third voice: swirling circles
            k = bar - 12
            for b, (yv, rv) in enumerate(((104, 98), (90, 104), (76, 98))):
                s = 1 if k % 2 == 0 else -1
                D.to(D.t(bar, b), "YAW", 90 + (yv - 90) * s, 160)
                D.to(D.t(bar, b), "ROL", rv if b != 1 else 90 + 12 * s, 160)
            D.to(t, "PIT", 42 - k, 120)
        elif bar < 20:                                # climax: swept around, eyes wide
            side = 1 if bar % 2 == 0 else -1
            D.to(t, "YAW", 90 + 28 * side, 220)
            D.to(t, "ROL", 90 - 14 * side, 200)
            D.add(t, "eyes", "R" if side > 0 else "L")
            D.add(D.t(bar, 1), "ears")
            D.pulse(D.t(bar, 2), "PIT", 34, 300)
            if bar == 16:
                D.to(t, "LID", 158, 400)
                D.pulse(t, "MOU", 80, 700)
        elif bar < 24:                                # fading: smaller and slower
            side = 1 if bar % 2 == 0 else -1
            f = 1.0 - (bar - 19) * 0.22
            D.to(t, "YAW", 90 + 18 * f * side, 80)
            D.to(t, "ROL", 90 - 8 * f * side, 80)
            if bar == 20:
                D.to(t, "LID", 140, 200)
        else:                                         # the last bell: almost still
            D.to(t, "YAW", 90, 40)
            D.to(t, "ROL", 90, 40)
            D.add(D.t(bar, 1), "blink")
    # the crack of ice: frozen in one snap, then not a single move
    t = D.t(25)
    for servo, angle in (("PIT", 40), ("ROL", 84), ("YAW", 100), ("LID", 152), ("EAL", 76),
                         ("EAR", 124), ("MOU", 120), ("EYL", 98), ("EYR", 98)):
        D.to(t, servo, angle, 600)
    return D.finish()


DANCES = {"lullaby": lullaby, "stomp": stomp, "blizzard": blizzard}


def main(names):
    os.makedirs(OUT, exist_ok=True)
    for n in names or list(DANCES):
        moves = DANCES[n]()
        tm = TIMING[n]
        with open(os.path.join(OUT, "snow_{}_choreo.json".format(n)), "w") as f:
            json.dump({"track": n, "bpm": tm["bpm"], "duration_ms": int(tm["seconds"] * 1000),
                       "moves": moves}, f, indent=1)
        beats = tm["seconds"] / (60.0 / tm["bpm"])
        print("{:<8} {:>3} moves at {:>3} moments over ~{:.0f} beats".format(
            n, len(moves), len({m["t_ms"] for m in moves}), beats))


if __name__ == "__main__":
    main(sys.argv[1:])
