"""Coglet dance choreography v2 (denser, eyes included).

Built from the same score marks as the music (tracks.py) plus a beat grid,
so every move still lands on a real beat. render.py and choreo_only.py both
call choreography(name, T).

Move vocabulary (implemented in RP2040/music.py):
  nod(small|big|heavy) bounce  ears ear_L ear_R ears_down
  sway_L/R(slow?) turn_L/R/center  head_tilt(L|R) head_roll shudder
  crouch(seconds) eyes_squint eyes_wide mouth_open blink rest pose_end
  eyes(L|R|C|cross|split)   L/R/C = both eyes same direction (held)
                            cross/split = eyes in opposite directions (pulse)
"""


def choreography(name, T):
    ev = sorted(T.events, key=lambda e: e[0])
    beat = T.beat
    moves = []

    def add(t, move, arg=None):
        moves.append({"t_ms": int(round(t * 1000)), "move": move, "arg": arg})

    # Section spans from the score.
    sections = [(t, v) for t, k, v in ev if k == "section"]
    end_t = next((t for t, k, _ in ev if k == "end"), T.n / 48000.0)

    def section_at(t):
        cur = "intro"
        for st, v in sections:
            if t + 1e-6 >= st:
                cur = v
        return cur

    # ------------------------------------------------ score-driven moves
    sway_dir = 1
    ear_dir = 1
    tilt_dir = 1
    for t, kind, value in ev:
        sec = section_at(t)
        if kind == "section":
            if value == "build":
                add(t, "crouch", round(beat * (16 if name == "mecha" else 8), 2))
            elif value == "outro":
                add(t, "rest")
            continue
        if kind == "end":
            add(t, "pose_end", name)
            continue

        if name == "mecha":
            if kind == "kick":
                if sec in ("intro", "outro"):
                    add(t, "nod", "small")
                elif sec == "drop":
                    add(t, "nod", "big" if value == "big" else "small")
            elif kind == "zap":
                add(t, "ear_L" if ear_dir > 0 else "ear_R")
                ear_dir = -ear_dir
            elif kind == "snare":
                add(t, "ears")
                if sec == "drop":
                    add(t, "blink")
            elif kind == "breath":
                add(t, "eyes_squint")
            elif kind == "hit":
                add(t, "eyes_wide")
                add(t, "ears")
                add(t, "mouth_open")
                add(t, "eyes", "split")
            elif kind == "bar" and sec == "drop":
                add(t, "sway_L" if sway_dir > 0 else "sway_R")
                add(t, "turn_L" if sway_dir > 0 else "turn_R")
                sway_dir = -sway_dir
            elif kind == "tom":
                add(t, ("turn_L", "turn_R", "turn_center")[value])
                add(t, "eyes", ("L", "R", "C")[value])

        elif name == "evil":
            if kind == "toll":
                add(t, "head_roll", "slow")
                add(t, "blink")
            elif kind == "kick" and sec in ("verse", "drop"):
                add(t, "nod", "heavy")
            elif kind == "snare":
                add(t, "ears_down")
                add(t, "eyes", "split")
                if sec == "drop":
                    add(t, "blink")
            elif kind == "bar":
                add(t, "sway_L" if sway_dir > 0 else "sway_R", "slow")
                if sec == "drop":
                    add(t, "turn_L" if sway_dir > 0 else "turn_R")
                sway_dir = -sway_dir
            elif kind == "tom":
                add(t, "shudder")
                add(t, "eyes", "cross")
            elif kind == "hit":
                add(t, "eyes_wide")
                add(t, "mouth_open")
                add(t, "eyes", "split")

        elif name == "cat":
            if kind == "kick":
                add(t, "bounce")
            elif kind == "snare":
                if sec == "build":
                    add(t, "ears")
                else:
                    add(t, "ear_L" if ear_dir > 0 else "ear_R")
                    ear_dir = -ear_dir
            elif kind == "nya":
                add(t, "head_tilt", "L" if tilt_dir > 0 else "R")
                add(t, "blink")
                add(t, "eyes", "cross")
                tilt_dir = -tilt_dir
            elif kind == "bar" and sec in ("verse", "drop"):
                if sec == "drop" or value % 2 == 0:
                    add(t, "turn_L" if value % 2 == 0 else "turn_R")
            elif kind == "hit":
                add(t, "eyes_wide")
                add(t, "ears")
                add(t, "eyes", "split")

    # ------------------------------------------------ beat-grid moves
    n_beats = int(end_t / beat + 1e-6)
    eye_dir = 1
    for i in range(n_beats):
        t = i * beat
        bar, b = divmod(i, 4)
        sec = section_at(t)
        off = t + beat / 2           # off-beat

        if name == "mecha":
            if sec == "intro":
                if b % 2 == 0:
                    add(t, "eyes", "L" if eye_dir > 0 else "R"); eye_dir = -eye_dir
                if b == 0 and bar % 2 == 1:
                    add(t, "blink")
            elif sec == "build":
                add(t, "eyes", "cross" if b % 2 == 0 else "split")
                if bar == 7:                       # rising: every half beat
                    add(off, "eyes", "split" if b % 2 == 0 else "cross")
            elif sec == "drop":
                if bar in (10, 11):                # eyes in opposite directions
                    add(t, "eyes", "cross" if b % 2 == 0 else "split")
                else:                              # both eyes on the beat
                    add(t, "eyes", "L" if eye_dir > 0 else "R"); eye_dir = -eye_dir
                add(off, "ear_L" if b % 2 == 0 else "ear_R")
            elif sec == "outro":
                if b == 0:
                    add(t, "eyes", "C")
                    add(t, "blink")

        elif name == "evil":
            if sec in ("intro", "outro"):
                if b == 0:
                    add(t, "eyes", "L" if eye_dir > 0 else "R"); eye_dir = -eye_dir
            elif sec == "verse":
                if b % 2 == 0:
                    add(t, "eyes", "L" if eye_dir > 0 else "R"); eye_dir = -eye_dir
                if b == 3:
                    add(t, "blink")
            elif sec == "build":
                add(t, "eyes", "cross" if b % 2 == 0 else "split")
            elif sec == "drop":
                add(t, "eyes", "L" if eye_dir > 0 else "R"); eye_dir = -eye_dir
                if b in (1, 3):
                    add(off, "ear_L" if b == 1 else "ear_R")

        elif name == "cat":
            if sec == "intro":
                if b % 2 == 0:
                    add(t, "eyes", "L" if eye_dir > 0 else "R"); eye_dir = -eye_dir
            elif sec == "verse":
                add(t, "eyes", "L" if eye_dir > 0 else "R"); eye_dir = -eye_dir
                if b == 3:
                    add(t, "blink")
            elif sec == "build":
                add(t, "eyes", "cross" if b % 2 == 0 else "split")
            elif sec == "drop":
                if bar % 2 == 1:
                    add(t, "eyes", "cross" if b % 2 == 0 else "split")
                else:
                    add(t, "eyes", "L" if eye_dir > 0 else "R"); eye_dir = -eye_dir
                add(off, "ear_L" if b % 2 == 0 else "ear_R")
                if b == 3:
                    add(t, "blink")
            elif sec == "outro":
                if b == 0:
                    add(t, "eyes", "C")

    # Servo safety: never the same move closer than 90 ms; nothing after the end pose.
    moves.sort(key=lambda m: m["t_ms"])
    end_ms = int(round(end_t * 1000))
    filtered = []
    last = {}
    for m in moves:
        if m["move"] != "pose_end" and m["t_ms"] > end_ms:
            continue
        key = m["move"]
        if key in last and m["t_ms"] - last[key] < 90:
            continue
        last[key] = m["t_ms"]
        filtered.append(m)
    # pose_end must stay last
    filtered.sort(key=lambda m: (m["t_ms"], m["move"] == "pose_end"))
    return filtered
