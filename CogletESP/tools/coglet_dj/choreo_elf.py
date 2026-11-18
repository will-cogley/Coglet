"""Choreography for the three Elf tracks (elf.py), written against the same
scores so every move lands on a real note. Same principle and move
vocabulary as choreo_xmas.py: hit the moments that matter, flow or hold
still in between.

The elf is quick, cheeky and busy: hammering nods in the workshop, shifty
eyes while sneaking, a waltzing party.

python3 choreo_elf.py  ->  out/elf_<name>_choreo.json
"""
import json
import os
import sys

import choreo_xmas as C
import elf as E

OUT = C.OUT

# Same tempo / meter / length as the rendered tracks in elf.py.
TIMING = {
    "workshop": {"bpm": 132, "bpb": 4, "seconds": 32.5},
    "mischief": {"bpm": 156, "bpb": 4, "seconds": 32.0},
    "party": {"bpm": 160, "bpb": 3, "seconds": 31.0},
}
C.TIMING.update(TIMING)
Dance = C.Dance


# ------------------------------------------------------------------ workshop
def workshop():
    """Deck the Halls in a toy workshop: Coglet winds up with the key, pops
    up with the spring, hammers on the beat (nods on 1 and 3), its ears
    answer the toy hammers on every 'fa la la', it looks around the
    workshop in the B section and climbs with the rising run, and ends
    proud with a wink when the spring goes 'boing'."""
    D = Dance("workshop")
    # intro: winding up (little head ticks with the ratchet), woodblocks, the spring
    for k in range(5):
        D.to(k * 0.15, "ROL", 90 + (5 if k % 2 == 0 else -5), 300)
    for k in range(4):
        D.add(D.t(0, k), "eyes", "L" if k % 2 == 0 else "R")
    t = D.t(0, 3)
    D.to(t, "ROL", 90)
    D.pulse(t, "PIT", 34, 260)
    D.add(t, "ears")
    D.add(t, "eyes", "C")

    def phrase(first, big, last_phrase=False):
        amp = 1.35 if big else 1.0
        # "Deck the halls with boughs of holly": hammering nods on 1 and 3
        for k, bar in enumerate((first, first + 1)):
            D.add(D.t(bar, 0), "nod", "big" if big else "small")
            D.add(D.t(bar, 2), "nod", "small")
            D.to(D.t(bar, 0), "YAW", 90 + (10 if k == 0 else -10) * amp)
            D.add(D.t(bar, 0), "eyes", "R" if k == 0 else "L")
        # "fa la la la la, la la la la": ears answer the toy hammers, a tilt per bar
        for k, bar in enumerate((first + 2, first + 3)):
            side = 1 if k == 0 else -1
            D.to(D.t(bar, 0), "ROL", 90 + 12 * amp * side)
            D.add(D.t(bar, 0), "eyes", "R" if side > 0 else "L")
            if not (last_phrase and k == 1):
                for b in range(4):
                    D.add(D.t(bar, b + 0.5), "ear_L" if b % 2 == 0 else "ear_R")
        # the long G at the end of the phrase: settle, a pleased little lift
        t = D.t(first + 3, 2)
        D.to(t, "ROL", 90)
        D.to(t, "YAW", 90)
        D.add(t, "eyes", "C")
        D.pulse(t, "PIT", 38, 380)
        D.add(t + 0.45, "blink")

    intro = 1
    phrase(intro + 0, False)
    phrase(intro + 4, False)
    # B: "Don we now our gay apparel": the clarinet; Coglet looks around the workshop
    b0 = intro + 8
    D.to(D.t(b0, 0), "YAW", 66, 120)
    D.add(D.t(b0, 0), "eyes", "L")
    D.to(D.t(b0 + 1, 0), "YAW", 114, 120)
    D.add(D.t(b0 + 1, 0), "eyes", "R")
    D.add(D.t(b0 + 1, 2), "nod", "small")
    # the rising run B C# D E F# G: the head climbs a step per note, ears rise
    run = D.notes(b0 + 2, E.DECK_TUNE[10])
    for k, (t, _, _) in enumerate(run):
        f = (k + 1) / float(len(run))
        D.to(t, "PIT", 52 - 20 * f, 260)
        D.to(t, "YAW", 114 - 24 * f, 200)
        D.to(t, "EAL", 110 - 38 * f, 400)
        D.to(t, "EAR", 90 + 38 * f, 400)
    D.add(run[-1][0], "eyes", "C")
    D.pulse(run[-1][0], "LID", 160, 350)
    # F# E D: back down with two nods
    D.to(D.t(b0 + 3, 0), "PIT", 46, 260)
    D.add(D.t(b0 + 3, 0), "nod", "small")
    D.add(D.t(b0 + 3, 1), "nod", "small")
    D.to(D.t(b0 + 3, 2), "EAL", 110, 400)
    D.to(D.t(b0 + 3, 2), "EAR", 90, 400)
    # A': bigger hammering; "E E E E": four quick ear flicks
    phrase(intro + 12, True, last_phrase=True)
    bar = intro + 14
    for k in range(4):
        D.add(D.t(bar, k * 0.5), "ear_L" if k % 2 == 0 else "ear_R")
    D.pulse(D.t(bar, 2), "MOU", 100, 250)
    # final chord: proud pose, the spring 'boing' -> head pops, a wink
    t = D.t(intro + 16)
    D.to(t, "PIT", 36, 260)
    D.to(t, "ROL", 98)
    D.to(t, "EAL", 72)
    D.to(t, "EAR", 128)
    D.add(t, "eyes", "C")
    D.pulse(t + 0.9, "PIT", 28, 200)
    D.pulse(t + 1.2, "LID", 105, 160)
    return D.finish()


# ------------------------------------------------------------------ mischief
def mischief():
    """God Rest Ye Merry Gentlemen as an elf sneaking: low head, squinting
    lids, ears back, eyes darting and the base creeping a step at a time.
    It freezes on the long notes and checks left and right on the
    woodblock ticks. From 'remember Christ...' it stops hiding: eyes open,
    head up, big sways and nods. Ends with a sly 'ta-da' and a wink."""
    D = Dance("mischief")
    intro = 1
    # intro: tiptoe in: squint, ears back, a look around
    D.to(0.0, "LID", 126, 300)
    D.to(0.0, "PIT", 58, 120)
    D.to(0.0, "EAL", 128, 300)
    D.to(0.0, "EAR", 72, 300)
    for k in range(4):
        D.add(D.t(0, k), "eyes", "L" if k % 2 == 0 else "R")

    creep = 90
    for i in range(E.GOD_REST_BOLD):
        bar = intro + i
        long_b = i in (3, 7)
        if long_b:
            # the long B: freeze ... tick (look left), tick (look right)
            D.add(D.t(bar, 0), "eyes", "C")
            D.add(D.t(bar, 1), "eyes", "L")
            D.add(D.t(bar, 2), "eyes", "R")
            D.pulse(D.t(bar, 3), "LID", 112, 200)
            continue
        # tiptoe: the base creeps a few degrees on beats 1 and 3, eyes dart
        step = 4 if i < 4 else -4
        for b in (0, 2):
            creep += step
            D.to(D.t(bar, b), "YAW", creep, 60)
            D.pulse(D.t(bar, b), "PIT", 61, 120)
        D.add(D.t(bar, 1), "eyes", "L" if i % 2 == 0 else "R")
        D.add(D.t(bar, 3), "eyes", "C")

    # bold from here: eyes open, head up, ears up, back to the centre
    bold = intro + E.GOD_REST_BOLD
    t = D.t(bold)
    D.to(t, "LID", 152, 400)
    D.to(t, "PIT", 42, 200)
    D.to(t, "EAL", 82, 500)
    D.to(t, "EAR", 118, 500)
    D.to(t, "YAW", 90, 120)
    D.add(t, "eyes", "C")
    D.add(t, "nod", "big")
    for i in range(E.GOD_REST_BOLD, len(E.GOD_REST_TUNE) - 1):
        bar = intro + i
        side = 1 if i % 2 == 0 else -1
        k = i - E.GOD_REST_BOLD
        D.to(D.t(bar, 0), "ROL", 90 + 13 * side, 220)
        D.add(D.t(bar, 0), "eyes", "R" if side > 0 else "L")
        if k in (3, 4, 7):                 # long notes: a big look across instead of nods
            D.to(D.t(bar, 0), "YAW", 90 + 22 * side, 160)
            D.add(D.t(bar, 2), "ears")
        else:
            D.add(D.t(bar, 0), "nod", "big" if k % 2 == 0 else "small")
            D.add(D.t(bar, 2), "nod", "small")
            D.to(D.t(bar, 2), "YAW", 90, 160)
        if k == 8:                         # G A B C: the head climbs
            for j, (tn, _, _) in enumerate(D.notes(bar, E.GOD_REST_TUNE[i])):
                D.to(tn, "PIT", 44 - 4 * j, 220)
        if k == 9:                         # B A G F#: and comes down
            for j, (tn, _, _) in enumerate(D.notes(bar, E.GOD_REST_TUNE[i])):
                D.to(tn, "PIT", 34 + 4 * j, 220)

    # last bar: the low E (a crouch) ... pause ... ta-da!
    last = intro + len(E.GOD_REST_TUNE) - 1
    t0 = D.t(last)
    D.to(t0, "ROL", 90, 220)
    D.to(t0, "YAW", 90, 160)
    D.to(t0, "PIT", 58, 200)
    D.to(t0, "LID", 128, 300)
    D.add(t0, "eyes", "C")
    t1 = D.t(last, 2)
    D.to(t1, "PIT", 34, 300)
    D.to(t1, "ROL", 80, 260)
    D.to(t1, "EAL", 68, 700)
    D.to(t1, "EAR", 132, 700)
    D.pulse(t1, "LID", 160, 450)
    D.pulse(t1, "MOU", 80, 400)
    D.pulse(t1 + 0.7, "LID", 104, 170)          # wink
    return D.finish()


# ------------------------------------------------------------------ party
def party():
    """We Wish You a Merry Christmas as an elves' party: a waltz sway (the
    neck on 'oom', the base every two bars), mouthing 'Christmas', three
    nods on 'good tidings we', ears ringing in the chorus. The key change
    throws the ears up and everything gets bigger; the last chord is a
    proud pose with wiggling ears and a wink."""
    D = Dance("party")
    intro = 2
    # intro oom-pah-pah: sway in, ears perk on the fiddle pickup
    D.to(D.t(0, 0), "ROL", 98, 160)
    D.to(D.t(1, 0), "ROL", 82, 160)
    D.add(D.t(1, 2), "ears")

    for i in range(len(E.PARTY_TUNE) - 1):
        bar = intro + i
        chorus = 8 <= i < 16
        last_verse = i >= 16
        amp = 1.35 if last_verse else 1.0
        side = 1 if i % 2 == 0 else -1
        k = i - 8
        if not chorus:
            v = i % 8
            # waltz: the neck sways on 'oom', the base every two bars
            D.to(D.t(bar, 0), "ROL", 90 + 11 * amp * side, 200)
            if v % 2 == 0:
                D.to(D.t(bar, 0), "YAW", 90 + 14 * amp * side, 140)
                D.add(D.t(bar, 0), "eyes", "R" if side > 0 else "L")
            if v in (1, 3):                      # "Christ-mas": mouth it
                D.pulse(D.t(bar, 0), "MOU", 105, 220)
                D.pulse(D.t(bar, 1), "MOU", 112, 180)
            if v in (0, 2, 4):
                D.add(D.t(bar, 0), "nod", "small")
            if v == 5:                           # "and a" (D D eighths): ear flicks
                D.add(D.t(bar, 2), "ear_L")
                D.add(D.t(bar, 2.5), "ear_R")
            if v == 6:                           # "hap-py new": head lifts
                D.pulse(D.t(bar, 1), "PIT", 36, 300)
            if v == 7:                           # "year": settle
                D.to(D.t(bar, 0), "ROL", 90, 200)
                D.to(D.t(bar, 0), "YAW", 90, 140)
                D.add(D.t(bar, 0), "eyes", "C")
        else:
            if k == 0:                           # "good tid-ings we": three nods
                for b in range(3):
                    D.add(D.t(bar, b), "nod", "big" if b == 0 else "small")
            elif k == 1:                         # "bring": lean
                D.to(D.t(bar, 0), "ROL", 102, 200)
            elif k == 2:                         # "to you and your": ears L, R, both
                D.add(D.t(bar, 0), "ear_L")
                D.add(D.t(bar, 1), "ear_R")
                D.add(D.t(bar, 2), "ears")
                D.to(D.t(bar, 0), "ROL", 90, 200)
            elif k == 3:                         # "kin": a swing of the base
                D.to(D.t(bar, 0), "YAW", 70, 160)
                D.add(D.t(bar, 0), "eyes", "L")
            elif k == 4:                         # "tid-ings for": step down
                D.to(D.t(bar, 0), "YAW", 90, 160)
                D.add(D.t(bar, 0), "eyes", "C")
                for j in range(3):
                    D.to(D.t(bar, j), "PIT", 42 + 4 * j, 260)
            elif k == 5:                         # "Christ-mas" on the high D: pop up
                D.to(D.t(bar, 0), "PIT", 32, 300)
                D.pulse(D.t(bar, 0), "LID", 160, 300)
                D.pulse(D.t(bar, 0), "MOU", 95, 250)
                D.to(D.t(bar, 1), "PIT", 48, 260)
                D.add(D.t(bar, 2), "ear_L")
                D.add(D.t(bar, 2.5), "ear_R")
            elif k == 6:                         # "hap-py new"
                D.to(D.t(bar, 0), "YAW", 110, 160)
                D.add(D.t(bar, 0), "eyes", "R")
                D.add(D.t(bar, 1), "nod", "small")
            elif k == 7:                         # "year" + the key change pickup
                D.to(D.t(bar, 0), "YAW", 90, 160)
                D.to(D.t(bar, 0), "PIT", 44, 260)
                D.add(D.t(bar, 0), "eyes", "C")
        if i == 16:                              # the key change: ears up, eyes wide
            t = D.t(bar)
            D.to(t, "EAL", 74, 600)
            D.to(t, "EAR", 126, 600)
            D.pulse(t, "LID", 160, 400)
            D.pulse(t, "PIT", 34, 260)

    # final chord: proud, ears wiggle with the tambourine, the spring, a wink
    t = D.t(intro + len(E.PARTY_TUNE) - 1)
    D.to(t, "PIT", 34, 260)
    D.to(t, "ROL", 90, 200)
    D.to(t, "YAW", 90, 160)
    D.to(t, "EAL", 70)
    D.to(t, "EAR", 130)
    D.add(t, "eyes", "C")
    for k in range(4):
        D.pulse(t + 0.1 + k * 0.12, "EAL" if k % 2 == 0 else "EAR", 52 if k % 2 == 0 else 148, 90)
    D.pulse(t + 0.6, "PIT", 28, 200)
    D.pulse(t + 1.0, "LID", 104, 160)
    return D.finish()


DANCES = {"workshop": workshop, "mischief": mischief, "party": party}


def main(names):
    os.makedirs(OUT, exist_ok=True)
    for n in names or list(DANCES):
        moves = DANCES[n]()
        tm = TIMING[n]
        with open(os.path.join(OUT, "elf_{}_choreo.json".format(n)), "w") as f:
            json.dump({"track": n, "bpm": tm["bpm"], "duration_ms": int(tm["seconds"] * 1000),
                       "moves": moves}, f, indent=1)
        beats = tm["seconds"] / (60.0 / tm["bpm"])
        print("{:<8} {:>3} moves at {:>3} moments over ~{:.0f} beats".format(
            n, len(moves), len({m["t_ms"] for m in moves}), beats))


if __name__ == "__main__":
    main(sys.argv[1:])
