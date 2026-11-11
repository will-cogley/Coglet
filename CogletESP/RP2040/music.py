# Coglet dance player (MicroPython / RP2040)
#
# ESP -> UART:  "dance:mecha" | "dance:evil" | "dance:cat"   start a dance
#               "dance:stop"                                    stop now (any mode)
#
# Custom songs from the Music folder (groove mode, beats streamed live):
#               "groove:<energetic|calm>:<bpm>"   start
#               "gb:<strength><energy><bar>"      one beat, e.g. "gb:751"
#               "groove:end"                      song finished
#
# The ESP starts the matching built-in track at the same moment it sends the
# command. The choreography (dance_data.py) is generated from the same score
# as the music, so every move lands on a known beat; we only need to add the
# audio output latency and start servo moves slightly early.
#
# While a dance runs it owns every servo (after Calibration, before MCP
# actions / states / blink / Facetrack). When it ends, the current XiaoZhi
# state is re-applied and the normal torque-release logic takes over again.

import time

import animation
from animation import servos
import dance_data

# ---------------------------------------------------------------- sync tuning
# ESP PlaySound() -> sound actually leaving the speaker (decode + DMA).
AUDIO_LATENCY_MS = 120
# Start servo moves this much earlier so the motion peaks on the beat
# (a 15-25 deg move takes ~100 ms to arrive).
SERVO_LEAD_MS = 100
# Pose-end hold after the last move before control is handed back.
END_HOLD_MS = 1200

# ---------------------------------------------------------------- styles
# Angle conventions (see animation.py):
#   PIT: smaller = head up (10 shocked, 50 neutral, 80 head down)
#   EAL/EAR mirrored: ears up = EAL smaller / EAR larger
#   MOU: 8..55 open, 150 closed;  LID: 150 open, 105 blink, 160 wide
STYLES = {
    "mecha": {
        "base": {"YAW": 90, "ROL": 90, "PIT": 45, "MOU": 150, "LID": 150,
                 "EYL": 90, "EYR": 90, "EAL": 110, "EAR": 90},
        "motion": {"PIT": (650, 7000), "ROL": (450, 3000), "YAW": (400, 1800),
                   "EAL": (750, 9000), "EAR": (750, 9000), "LID": (900, 9000),
                   "MOU": (2000, 10000), "EYL": (420, 5000), "EYR": (420, 5000)},
        "nod": {"small": (11, 110), "big": (19, 150)},
        "sway": 20,
        "turn": 24,
        "gaze": 20,
        "pose_end": {"YAW": 90, "ROL": 100, "PIT": 30, "MOU": 150, "LID": 150,
                     "EAL": 70, "EAR": 120},
    },
    "evil": {
        "base": {"YAW": 90, "ROL": 90, "PIT": 60, "MOU": 150, "LID": 125,
                 "EYL": 90, "EYR": 90, "EAL": 140, "EAR": 45},
        "motion": {"PIT": (400, 3000), "ROL": (160, 900), "YAW": (220, 900),
                   "EAL": (500, 5000), "EAR": (500, 5000), "LID": (600, 5000),
                   "MOU": (1000, 6000), "EYL": (280, 2500), "EYR": (280, 2500)},
        "nod": {"heavy": (15, 260), "small": (9, 160)},
        "sway": 18,
        "turn": 20,
        "gaze": 16,
        "pose_end": {"YAW": 90, "ROL": 90, "PIT": 75, "MOU": 150, "LID": 110,
                     "EAL": 150, "EAR": 30},
    },
    "cat": {
        "base": {"YAW": 90, "ROL": 90, "PIT": 45, "MOU": 150, "LID": 150,
                 "EYL": 90, "EYR": 90, "EAL": 100, "EAR": 100},
        "motion": {"PIT": (600, 6000), "ROL": (400, 2800), "YAW": (350, 1500),
                   "EAL": (750, 9000), "EAR": (750, 9000), "LID": (900, 9000),
                   "MOU": (2000, 10000), "EYL": (420, 5000), "EYR": (420, 5000)},
        "nod": {"small": (10, 110)},
        "sway": 18,
        "turn": 22,
        "gaze": 19,
        "pose_end": {"YAW": 90, "ROL": 72, "PIT": 40, "MOU": 40, "LID": 150,
                     "EAL": 75, "EAR": 115},
    },
}

EAR_FLICK_DEG = 45
EAR_FLICK_MS = 160
BLINK_MS = 120
EYE_CROSS_MS = 260
MOUTH_OPEN_ANGLE = 30
MOUTH_OPEN_MS = 450
EYES_WIDE_MS = 700
CROUCH_PIT_DEG = 16
CROUCH_LID_DEG = 20

_dance = {
    "name": None,
    "mode": "track",   # "track" (built-in choreography) | "groove" (streamed beats)
    "start_ms": 0,
    "index": 0,
    "moves": (),
    "duration_ms": 0,
    "style": None,
    "held": {},        # servo -> resting angle (moves return here)
    "returns": {},     # servo -> (due_ms, angle): one pending return per servo
    "sequence": [],    # [(due_ms, servo, angle)] for multi-step moves
    "end_at": None,
}


def active():
    return _dance["name"] is not None


def keeps_released(name):
    """True if the running groove wants this servo relaxed (no torque)."""
    return (active() and _dance["mode"] == "groove"
            and name in _dance["style"].get("release", ()))


# Fast dance moves can overshoot a target by ~1-2 deg while braking, so keep
# dance targets a little inside each servo's soft limits.
LIMIT_MARGIN_DEG = 3


def _clamp(name, angle):
    servo = servos[name]
    return max(servo.min_angle + LIMIT_MARGIN_DEG, min(servo.max_angle - LIMIT_MARGIN_DEG, angle))


def _set(name, angle):
    servos[name].set_target(_clamp(name, angle))


def _hold(name, angle):
    """Change the resting angle and move there."""
    _dance["held"][name] = _clamp(name, angle)
    _dance["returns"].pop(name, None)
    _set(name, angle)


def _pulse(name, angle, hold_ms, now):
    """Go to `angle`, come back to the resting angle after hold_ms."""
    _set(name, angle)
    _dance["returns"][name] = (time.ticks_add(now, hold_ms), None)


def _apply_motion(style):
    for name, (speed, accel) in style["motion"].items():
        servos[name].max_speed = speed
        servos[name].max_accel = accel


def start(name, now):
    track = dance_data.TRACKS.get(name)
    style = STYLES.get(name)
    if track is None or style is None:
        print("[DANCE] unknown track:", name)
        return False
    if active():
        stop(now, "restart")
    _dance["name"] = name
    _dance["start_ms"] = now
    _dance["index"] = 0
    _dance["moves"] = track["moves"]
    _dance["duration_ms"] = track["duration_ms"]
    _dance["style"] = style
    _dance["held"] = {}
    _dance["returns"] = {}
    _dance["sequence"] = []
    _dance["end_at"] = None
    _apply_motion(style)
    for servo_name, angle in style["base"].items():
        _hold(servo_name, angle)
    print("[DANCE] START {} ({} BPM, {} moves, {} ms)".format(
        name, track["bpm"], len(track["moves"]), track["duration_ms"]))
    return True


def stop(now, reason="stop"):
    if not active():
        return
    print("[DANCE] STOP {} ({})".format(_dance["name"], reason))
    _dance["name"] = None
    _dance["returns"] = {}
    _dance["sequence"] = []
    _dance["mode"] = "track"
    # Servos released by the calm groove get their torque back.
    for servo in servos.values():
        servo.hold()
    # Hand control back: restore declared motion limits and make the current
    # XiaoZhi state re-apply its pose on the next loop.
    animation.reset_servo_motion_defaults()
    animation.new_state_flag = True


def _music_time(now):
    """Milliseconds into the music, compensated for audio latency and servo lag."""
    return time.ticks_diff(now, _dance["start_ms"]) - AUDIO_LATENCY_MS + SERVO_LEAD_MS


def _do_move(move, arg, now):
    style = _dance["style"]
    held = _dance["held"]
    base = style["base"]

    if move in ("nod", "bounce"):
        depth, hold_ms = style["nod"].get(arg or "small", style["nod"].get("small", (7, 110)))
        if move == "bounce":
            depth, hold_ms = style["nod"]["small"]
        _pulse("PIT", held["PIT"] + depth, hold_ms, now)
    elif move == "ears":
        _pulse("EAL", held["EAL"] - EAR_FLICK_DEG, EAR_FLICK_MS, now)
        _pulse("EAR", held["EAR"] + EAR_FLICK_DEG, EAR_FLICK_MS, now)
    elif move == "ear_L":
        _pulse("EAL", held["EAL"] - EAR_FLICK_DEG, EAR_FLICK_MS, now)
    elif move == "ear_R":
        _pulse("EAR", held["EAR"] + EAR_FLICK_DEG, EAR_FLICK_MS, now)
    elif move == "ears_down":
        _pulse("EAL", 150, 450, now)
        _pulse("EAR", 30, 450, now)
    elif move in ("sway_L", "sway_R"):
        side = -1 if move == "sway_L" else 1
        _hold("ROL", base["ROL"] + side * style["sway"])
    elif move in ("turn_L", "turn_R", "turn_center"):
        side = {"turn_L": -1, "turn_R": 1, "turn_center": 0}[move]
        _hold("YAW", base["YAW"] + side * style["turn"])
    elif move == "eyes":
        gaze = style["gaze"]
        if arg in ("L", "R", "C"):
            # Both eyes together, held until the next eye move.
            side = {"L": -1, "R": 1, "C": 0}[arg]
            _hold("EYL", base["EYL"] + side * gaze)
            _hold("EYR", base["EYR"] + side * gaze)
        else:
            # Opposite directions for a moment, then back.
            side = 1 if arg == "cross" else -1
            _pulse("EYL", base["EYL"] + side * gaze, EYE_CROSS_MS, now)
            _pulse("EYR", base["EYR"] - side * gaze, EYE_CROSS_MS, now)
    elif move == "head_tilt":
        side = -1 if arg == "L" else 1
        _pulse("ROL", held["ROL"] + side * 22, 600, now)
    elif move == "head_roll":
        _set("ROL", base["ROL"] - 16)
        _dance["sequence"].append((time.ticks_add(now, 600), "ROL", base["ROL"] + 16))
        _dance["sequence"].append((time.ticks_add(now, 1200), "ROL", None))
    elif move == "shudder":
        _set("ROL", held["ROL"] + 7)
        _dance["sequence"].append((time.ticks_add(now, 60), "ROL", held["ROL"] - 7))
        _dance["sequence"].append((time.ticks_add(now, 120), "ROL", None))
    elif move == "crouch":
        seconds = float(arg or 4.0)
        # Slowly lower the head and narrow the eyes over the whole build-up.
        servos["PIT"].max_speed = max(1.5, CROUCH_PIT_DEG / seconds)
        servos["LID"].max_speed = max(1.5, CROUCH_LID_DEG / seconds)
        _hold("PIT", base["PIT"] + CROUCH_PIT_DEG)
        _hold("LID", base["LID"] - CROUCH_LID_DEG)
    elif move == "eyes_squint":
        _hold("LID", 118)
    elif move == "eyes_wide":
        _apply_motion(style)          # end of crouch: fast again
        _hold("LID", base["LID"])
        _hold("PIT", base["PIT"])
        _pulse("LID", 160, EYES_WIDE_MS, now)
        _pulse("PIT", base["PIT"] - 10, 300, now)
    elif move == "mouth_open":
        _pulse("MOU", MOUTH_OPEN_ANGLE, MOUTH_OPEN_MS, now)
    elif move == "blink":
        _pulse("LID", 105, BLINK_MS, now)
    elif move == "rest":
        _apply_motion(style)
        for servo_name, angle in base.items():
            _hold(servo_name, angle)
    elif move == "pose_end":
        _apply_motion(style)
        for servo_name, angle in style["pose_end"].items():
            _hold(servo_name, angle)
        if arg == "cat":
            _pulse("LID", 105, BLINK_MS, now)   # a wink-ish blink to finish
    else:
        print("[DANCE] unknown move:", move)


# ====================================================================== groove
# Presets for custom songs. The ESP sends each beat already compensated for
# speaker latency (menuconfig: COGLET_MUSIC_BEAT_OFFSET_MS), so moves start
# the moment a beat arrives.
GROOVES = {
    "energetic": {
        "base": {"YAW": 90, "ROL": 90, "PIT": 45, "MOU": 150, "LID": 150,
                 "EYL": 90, "EYR": 90, "EAL": 110, "EAR": 90},
        "motion": {"PIT": (650, 7000), "ROL": (450, 3000), "YAW": (400, 1800),
                   "EAL": (750, 9000), "EAR": (750, 9000), "LID": (900, 9000),
                   "MOU": (2000, 10000), "EYL": (420, 5000), "EYR": (420, 5000)},
        "nod": {"small": (10, 110)},
        "sway": 18,
        "turn": 22,
        "gaze": 19,
        "release": (),
        "pose_end": {"YAW": 90, "ROL": 100, "PIT": 32, "MOU": 150, "LID": 150,
                     "EAL": 72, "EAR": 118},
    },
    "calm": {
        # Ears, head and base only; small, slow moves on the felt pulse.
        "base": {"YAW": 90, "ROL": 90, "PIT": 55, "MOU": 150,
                 "EAL": 125, "EAR": 75},
        "motion": {"PIT": (110, 500), "ROL": (45, 220), "YAW": (35, 160),
                   "EAL": (160, 1200), "EAR": (160, 1200), "MOU": (300, 2000)},
        "nod": {"small": (5, 300)},
        "sway": 7,
        "turn": 6,
        "gaze": 0,
        # Eyelid and both eye servos go limp for the whole song.
        "release": ("LID", "EYL", "EYR"),
        "pose_end": {"YAW": 90, "ROL": 97, "PIT": 64, "MOU": 150,
                     "EAL": 140, "EAR": 55},
    },
}
GROOVE_SILENCE_MS = 4000      # no beat for this long -> finish on our own


def start_groove(preset, bpm, now):
    style = GROOVES.get(preset)
    if style is None:
        print("[DANCE] unknown groove preset:", preset)
        style = GROOVES["calm"]
        preset = "calm"
    if active():
        stop(now, "restart")
    _dance["name"] = "groove-" + preset
    _dance["mode"] = "groove"
    _dance["start_ms"] = now
    _dance["index"] = 0
    _dance["moves"] = ()
    _dance["duration_ms"] = 0
    _dance["style"] = style
    _dance["held"] = {}
    _dance["returns"] = {}
    _dance["sequence"] = []
    _dance["end_at"] = None
    _dance["beat"] = 0
    _dance["bars"] = 0
    _dance["last_beat_ms"] = now
    _dance["dirs"] = {"sway": 1, "turn": 1, "ear": 1, "eye": 1}
    _apply_motion(style)
    for servo_name in style["release"]:
        servos[servo_name].release()
    for servo_name, angle in style["base"].items():
        _hold(servo_name, angle)
    print("[DANCE] GROOVE START {} ({} BPM){}".format(
        preset, bpm, " released: " + ",".join(style["release"]) if style["release"] else ""))
    return True


def groove_beat(code, now):
    """code: 3 digits from the ESP: accent strength, section energy, bar start."""
    if not active() or _dance["mode"] != "groove" or _dance["end_at"] is not None:
        return
    try:
        strength = int(code[0])
        energy = int(code[1])
        bar = code[2] == "1"
    except (IndexError, ValueError):
        return
    _dance["last_beat_ms"] = now
    _dance["beat"] += 1
    if _dance["name"] == "groove-energetic":
        _groove_energetic(strength, energy, bar, now)
    else:
        _groove_calm(strength, energy, bar, now)


def _flip(key):
    d = _dance["dirs"]
    d[key] = -d[key]
    return d[key]


def _groove_energetic(strength, energy, bar, now):
    style = _dance["style"]
    base = style["base"]
    held = _dance["held"]
    n = _dance["beat"]
    loud = 0.55 + 0.05 * energy                     # 0.55 (quiet) .. 1.0 (chorus)

    # Head bob on every beat, deeper on accents.
    depth = (6 + 1.4 * strength) * loud
    _pulse("PIT", held["PIT"] + depth, 110, now)

    # Ears: both on strong accents, alternating otherwise.
    if strength >= 7:
        _pulse("EAL", held["EAL"] - EAR_FLICK_DEG, EAR_FLICK_MS, now)
        _pulse("EAR", held["EAR"] + EAR_FLICK_DEG, EAR_FLICK_MS, now)
    elif energy >= 3:
        if _flip("ear") > 0:
            _pulse("EAL", held["EAL"] - EAR_FLICK_DEG, EAR_FLICK_MS, now)
        else:
            _pulse("EAR", held["EAR"] + EAR_FLICK_DEG, EAR_FLICK_MS, now)

    # Body: sway every bar, turn as well once the song is up.
    if bar:
        side = _flip("sway")
        _hold("ROL", base["ROL"] + side * style["sway"] * loud)
        if energy >= 5:
            _hold("YAW", base["YAW"] + _flip("turn") * style["turn"] * loud)
        elif energy <= 2:
            _hold("YAW", base["YAW"])

    # Eyes: on every beat in loud parts, every bar in quiet ones.
    if energy >= 8 and strength >= 8 and n % 4 == 0:
        side = 1 if (n // 4) % 2 else -1
        _pulse("EYL", base["EYL"] + side * style["gaze"], EYE_CROSS_MS, now)
        _pulse("EYR", base["EYR"] - side * style["gaze"], EYE_CROSS_MS, now)
    elif energy >= 5 or bar:
        side = _flip("eye")
        _hold("EYL", base["EYL"] + side * style["gaze"] * loud)
        _hold("EYR", base["EYR"] + side * style["gaze"] * loud)

    # Blink now and then; open the mouth on the biggest hits.
    if n % 8 == 5:
        _pulse("LID", 105, BLINK_MS, now)
    if strength == 9 and energy >= 8 and n % 8 == 0:
        _pulse("MOU", MOUTH_OPEN_ANGLE, 300, now)


def _groove_calm(strength, energy, bar, now):
    style = _dance["style"]
    base = style["base"]
    held = _dance["held"]
    n = _dance["beat"]
    soft = 0.7 + 0.03 * energy                      # 0.7 .. ~1.0

    # A gentle nod on every felt beat; it sinks slowly and comes back up.
    depth, hold_ms = style["nod"]["small"]
    _pulse("PIT", held["PIT"] + (depth + 0.3 * strength) * soft, hold_ms, now)

    # Ears drift a little every other beat.
    if n % 2 == 0:
        if _flip("ear") > 0:
            _pulse("EAL", held["EAL"] - 14, 380, now)
        else:
            _pulse("EAR", held["EAR"] + 14, 380, now)

    # Lean side to side once a bar; turn the base every other bar.
    if bar:
        _dance["bars"] = _dance.get("bars", 0) + 1
        _hold("ROL", base["ROL"] + _flip("sway") * style["sway"] * soft)
        if _dance["bars"] % 2 == 1:
            _hold("YAW", base["YAW"] + _flip("turn") * style["turn"] * soft)


def groove_end(now):
    """The song finished: strike the end pose, hold it, then hand back."""
    if not active() or _dance["mode"] != "groove" or _dance["end_at"] is not None:
        return
    style = _dance["style"]
    _apply_motion(style)
    for servo_name, angle in style["pose_end"].items():
        _hold(servo_name, angle)
    _dance["end_at"] = time.ticks_add(now, END_HOLD_MS)
    print("[DANCE] GROOVE END")


def _update_returns(now):
    held = _dance["held"]
    for name in list(_dance["returns"].keys()):
        due, _ = _dance["returns"][name]
        if time.ticks_diff(now, due) >= 0:
            del _dance["returns"][name]
            _set(name, held[name])
    if _dance["sequence"]:
        remaining = []
        for due, name, angle in _dance["sequence"]:
            if time.ticks_diff(now, due) >= 0:
                _set(name, held[name] if angle is None else angle)
            else:
                remaining.append((due, name, angle))
        _dance["sequence"] = remaining


def _update_groove(now):
    _update_returns(now)
    if _dance["end_at"] is not None:
        if time.ticks_diff(now, _dance["end_at"]) >= 0:
            stop(now, "song finished")
            return False
    elif time.ticks_diff(now, _dance["last_beat_ms"]) > GROOVE_SILENCE_MS:
        groove_end(now)                 # ESP went quiet: finish gracefully
    return True


def update(now):
    """Run the dance. Returns True while the dance owns the servos."""
    if not active():
        return False
    if _dance["mode"] == "groove":
        return _update_groove(now)

    t = _music_time(now)
    moves = _dance["moves"]
    while _dance["index"] < len(moves) and moves[_dance["index"]][0] <= t:
        _, move, arg = moves[_dance["index"]]
        _dance["index"] += 1
        _do_move(move, arg, now)

    # Returns from short pulses and multi-step moves.
    _update_returns(now)

    # Finish once all moves are done and the final pose was held.
    if _dance["index"] >= len(moves):
        if _dance["end_at"] is None:
            _dance["end_at"] = time.ticks_add(now, END_HOLD_MS)
        elif time.ticks_diff(now, _dance["end_at"]) >= 0 and t >= _dance["duration_ms"]:
            stop(now, "finished")
            return False
    elif t > _dance["duration_ms"] + 3000:
        stop(now, "timeout")
        return False
    return True
