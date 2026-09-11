from servoclass import Servo
import time

current_pose = "pose_calibrate"
current_state = "state_startup"
animation_bool_a = False
animation_bool_b = False
last_toggle_a = time.ticks_ms()
last_toggle_b = time.ticks_ms()
new_state_flag = True

# ============================================================
# Speaking: neck roll left/right (ROL / Socket 9 / CH9)
#
# PCB V2 verified mapping:
#   ROL -> Socket 9 -> PCA CH9 -> Neck Roll left/right
# Center position is 90 degrees.
# ============================================================
SPEAKING_NECK_LEFT = 65
SPEAKING_NECK_RIGHT = 115
SPEAKING_NECK_INTERVAL_MS = 520
LISTENING_NECK_CENTER = 90

speaking_neck_side = False
last_speaking_neck_toggle = time.ticks_ms()

# ============================================================
# Ears: alternating motion in Speaking + slower in Listening
#
# Verified PCB V2 mapping:
#   EAR -> Socket 0 -> PCA CH0 -> Right Ear
#   EAL -> Socket 1 -> PCA CH1 -> Left Ear
#
# The ear servos are mounted as a mirror pair.
# Therefore use the SAME numeric command on both ears.
# The mirrored mechanics create the opposite/symmetric physical motion.
#
# Use only the common safe range of both original V1 servo limits:
#   EAL: 60..150
#   EAR: 30..120
# Common range: 60..120
# ============================================================

EAR_ANGLE_A = 70
EAR_ANGLE_B = 115

SPEAKING_EAR_INTERVAL_MS = 520
SPEAKING_EAR_MAX_SPEED = 300.0
SPEAKING_EAR_MAX_ACCEL = 700.0

LISTENING_EAR_INTERVAL_MS = 1350
LISTENING_EAR_MAX_SPEED = 90.0
LISTENING_EAR_MAX_ACCEL = 220.0

# ============================================================
# Expression tuning: HAPPY / SAD
#
# HAPPY:
#   - one-sided neck pose
#   - no blinking
#   - faster mirrored ear alternating
#
# SAD:
#   - neck pitch down
#   - no blinking
#   - half-closed eyelid
#   - both ears droop/back
#
# Other servo behavior starts from the existing neutral
# pose_stop_speaking baseline.
# ============================================================

HAPPY_NECK_SIDE_ANGLE = 70
HAPPY_EAR_INTERVAL_MS = 300
HAPPY_EAR_MAX_SPEED = 400.0
HAPPY_EAR_MAX_ACCEL = 900.0
HAPPY_LID_OPEN_ANGLE = 150

# Eyelid normal pose-transition tuning.
# The old 50000/50000 values made large state changes (e.g. sleep 30 ->
# listening 130) behave almost like an instantaneous jump.
# Blinks are unaffected because blink code uses set_immediate().
LID_POSE_MAX_SPEED = 180.0
LID_POSE_MAX_ACCEL = 600.0

# Reuse the already-tested mirrored ear travel.
HAPPY_EAR_ANGLE_A = EAR_ANGLE_A
HAPPY_EAR_ANGLE_B = EAR_ANGLE_B

# Current PIT range is 1..80. 75 gives a clear "head down" pose.
SAD_PITCH_ANGLE = 75
SAD_LID_ANGLE = 130

# Reuse the existing sleep-style drooped ear pose.
SAD_LEFT_EAR_ANGLE = 150
SAD_RIGHT_EAR_ANGLE = 30

happy_ear_side = False
last_happy_ear_toggle = time.ticks_ms()

speaking_ear_side = False
last_speaking_ear_toggle = time.ticks_ms()

listening_ear_side = False
last_listening_ear_toggle = time.ticks_ms()

# ============================================================
# Speaking mouth: smooth, slow random opening/closing
#
# Verified PCB V2 mapping:
#   MOU -> Socket 3 -> PCA CH3 -> Mouth
#
# The mouth alternates between a random OPEN range and a random
# CLOSED range. Alternating the two ranges guarantees visible movement,
# while the exact angle and dwell time remain random.
# ============================================================

MOUTH_OPEN_MIN = 8
MOUTH_OPEN_MAX = 55

MOUTH_CLOSED_MIN = 105
MOUTH_CLOSED_MAX = 150

# Slow random cadence: centered around the Listening-ear interval (1350 ms).
# It remains random, but is no longer machine-gun fast.
MOUTH_INTERVAL_MIN_MS = 1100
MOUTH_INTERVAL_MAX_MS = 1600

# Use the SAME motion speed/acceleration as Listening ears.
# The existing Servo.update(dt) motion planner provides smooth
# acceleration/deceleration interpolation between random mouth targets.
SPEAKING_MOUTH_MAX_SPEED = LISTENING_EAR_MAX_SPEED
SPEAKING_MOUTH_MAX_ACCEL = LISTENING_EAR_MAX_ACCEL

# MOU is speech-owned:
# its continuous motion is controlled by the independent speech flag in main.py,
# not by the current emotional/expression state.
MOUTH_REST_ANGLE = 150

mouth_open_phase = True
last_mouth_toggle = time.ticks_ms()
next_mouth_interval_ms = MOUTH_INTERVAL_MIN_MS
mouth_runtime_active = False
mouth_current_target = float(MOUTH_REST_ANGLE)

# Tiny local PRNG so this file does not depend on random/urandom modules.
_rand_state = (time.ticks_us() ^ 0xA5366B4D) & 0xFFFFFFFF
if _rand_state == 0:
    _rand_state = 0x13579BDF


def _rand_u32():
    global _rand_state

    x = _rand_state
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= (x >> 17)
    x ^= (x << 5) & 0xFFFFFFFF

    _rand_state = x & 0xFFFFFFFF
    return _rand_state


def _randint(a, b):
    if b <= a:
        return int(a)

    return int(a + (_rand_u32() % (b - a + 1)))


def _schedule_next_mouth(now):
    global next_mouth_interval_ms
    global last_mouth_toggle

    next_mouth_interval_ms = _randint(
        MOUTH_INTERVAL_MIN_MS,
        MOUTH_INTERVAL_MAX_MS
    )
    last_mouth_toggle = now


def _set_random_mouth_target():
    global mouth_open_phase
    global mouth_current_target

    if mouth_open_phase:
        angle = _randint(
            MOUTH_OPEN_MIN,
            MOUTH_OPEN_MAX
        )
    else:
        angle = _randint(
            MOUTH_CLOSED_MIN,
            MOUTH_CLOSED_MAX
        )

    mouth_current_target = float(angle)
    servos["MOU"].set_target(mouth_current_target)
    mouth_open_phase = not mouth_open_phase


def update_speaking_mouth(now, speaking_active):
    """
    Independent mouth controller.

    This is intentionally separate from current_state / emotion.
    Once the ESP reports "speaking", MOU keeps opening/closing even if
    the current expression later becomes "sad" or "happy".

    When speaking ends, MOU returns to the normal closed/rest position once.
    """
    global mouth_runtime_active
    global mouth_open_phase
    global mouth_current_target

    speaking_active = bool(speaking_active)

    # MOU is speech-owned. A normal state transition may restore every
    # servo's declaration defaults, so while speech is active we re-assert
    # the mouth-specific motion limits on every loop.
    if speaking_active:
        servos["MOU"].max_speed = SPEAKING_MOUTH_MAX_SPEED
        servos["MOU"].max_accel = SPEAKING_MOUTH_MAX_ACCEL

    if speaking_active and not mouth_runtime_active:

        mouth_open_phase = True
        _set_random_mouth_target()
        _schedule_next_mouth(now)

        mouth_runtime_active = True
        print("[MOUTH] SPEECH ON -> independent mouth animation started")

    elif not speaking_active and mouth_runtime_active:
        mouth_runtime_active = False
        mouth_current_target = float(MOUTH_REST_ANGLE)
        servos["MOU"].set_target(mouth_current_target)
        print("[MOUTH] SPEECH OFF -> mouth returning to rest")

    if not mouth_runtime_active:
        return

    # Re-assert the current speech-owned target every loop.
    # This makes MOU win over any pose applied by an emotion on the same loop.
    servos["MOU"].set_target(mouth_current_target)

    if time.ticks_diff(now, last_mouth_toggle) >= next_mouth_interval_ms:
        _set_random_mouth_target()
        _schedule_next_mouth(now)


# ============================================================
# Random blink - simple timer version
#
# This is the old commented main.py blink idea moved into animation.py,
# but corrected for PCB V2 and the measured eyelid range.
#
# Active only in:
#   speaking / listening / thinking
#
# Verified mapping:
#   LID -> Socket 2 -> PCA CH2 -> Eyelid
#
# IMPORTANT:
# Blink commands use Servo.set_immediate(), so there is NO software
# speed/acceleration interpolation during the blink itself.
# ============================================================

BLINK_ALLOWED_STATES = (
    "speaking",
    "listening",
    "thinking",
)

BLINK_CLOSED_ANGLE = 105
BLINK_DEFAULT_OPEN_ANGLE = 150

# How long the close command is held before reopening.
BLINK_DURATION_MS = 120

# Random interval between blinks. This is independent of loop frequency.
BLINK_INTERVAL_MIN_MS = 2800
BLINK_INTERVAL_MAX_MS = 6500

blink_state = {
    "active": False,
    "start_time": 0,
    "restore_angle": float(BLINK_DEFAULT_OPEN_ANGLE),
    "next_due": time.ticks_add(
        time.ticks_ms(),
        _randint(BLINK_INTERVAL_MIN_MS, BLINK_INTERVAL_MAX_MS)
    ),
}


def _schedule_next_blink(now):
    blink_state["next_due"] = time.ticks_add(
        now,
        _randint(
            BLINK_INTERVAL_MIN_MS,
            BLINK_INTERVAL_MAX_MS
        )
    )


def trigger_blink(now):
    """
    Start one blink.

    This is the useful part of the old commented main.py trigger_blink():
    remember the current eyelid expression, close once, then let
    update_blink() restore it after BLINK_DURATION_MS.
    """
    if blink_state["active"]:
        return

    lid = servos["LID"]
    current_target = float(lid.target)

    # Do not restore legacy unsafe low LID targets.
    if current_target <= BLINK_CLOSED_ANGLE + 5:
        restore_angle = float(BLINK_DEFAULT_OPEN_ANGLE)
    else:
        restore_angle = min(
            float(BLINK_DEFAULT_OPEN_ANGLE),
            current_target
        )

    blink_state["active"] = True
    blink_state["start_time"] = now
    blink_state["restore_angle"] = restore_angle

    # Immediate close: no interpolation/speed limiter.
    lid.set_immediate(BLINK_CLOSED_ANGLE)


def update_blink(now, state_name, enabled=True):
    """
    Non-blocking blink timer.

    Call once each main loop after apply_state().
    """
    allowed = (
        enabled
        and state_name in BLINK_ALLOWED_STATES
    )

    lid = servos["LID"]

    if not allowed:
        if blink_state["active"]:
            lid.set_immediate(
                blink_state["restore_angle"]
            )
            blink_state["active"] = False

        _schedule_next_blink(now)
        return

    # Finish the current blink exactly once.
    if blink_state["active"]:
        if (
            time.ticks_diff(
                now,
                blink_state["start_time"]
            )
            >= BLINK_DURATION_MS
        ):
            lid.set_immediate(
                blink_state["restore_angle"]
            )
            blink_state["active"] = False
            _schedule_next_blink(now)

        return

    # Start one random blink when its absolute due time arrives.
    if time.ticks_diff(
        now,
        blink_state["next_due"]
    ) >= 0:
        trigger_blink(now)


servos = {
    # PCB physical servo connector semantics.
    # pin_num is the PCB-printed Socket ID, and Socket ID == PCA9685 channel.
    # This keeps the PCB silkscreen, customer servo table, and code identical.
    # Named servos currently use sockets/channels: 0,1,2,3,4,5,8,9,10.
    "YAW": Servo(pin_num=10, max_speed=400, max_accel=100, min_angle=30, max_angle=150), # Base Yaw      -> Socket 10 / CH10
    "ROL": Servo(pin_num=9,  max_speed=600, max_accel=400, min_angle=30, max_angle=120), # Neck Roll     -> Socket 9  / CH9
    "PIT": Servo(pin_num=8,  max_speed=600, max_accel=400, min_angle=1, max_angle=80),   # Neck Pitch    -> Socket 8  / CH8
    "MOU": Servo(pin_num=3,  max_speed=50000, max_accel=10000, min_angle=5, max_angle=150), # Mouth       -> Socket 3  / CH3
    "EYL": Servo(pin_num=4,  max_speed=250, max_accel=10000, min_angle=50, max_angle=140), # Left Eye     -> Socket 4  / CH4
    "EYR": Servo(pin_num=5,  max_speed=250, max_accel=10000, min_angle=50, max_angle=140), # Right Eye    -> Socket 5  / CH5
    "LID": Servo(pin_num=2,  max_speed=LID_POSE_MAX_SPEED, max_accel=LID_POSE_MAX_ACCEL, min_angle=30, max_angle=160), # Eyelid -> Socket 2 / CH2
    "EAL": Servo(pin_num=1,  max_speed=250, max_accel=200, min_angle=60, max_angle=150), # Left Ear      -> Socket 1  / CH1
    "EAR": Servo(pin_num=0,  max_speed=500, max_accel=200, min_angle=30, max_angle=120), # Right Ear     -> Socket 0  / CH0
}

# ============================================================
# Servo motion defaults
#
# The servos declaration above is the SINGLE source of truth for default
# max_speed/max_accel values. Capture those values once at startup so a
# state is free to tune motion temporarily without leaking that tuning into
# the next state. Editing the Servo(...) values above automatically changes
# the defaults used here; there is no second table to maintain.
# ============================================================
SERVO_MOTION_DEFAULTS = {
    name: (servo.max_speed, servo.max_accel)
    for name, servo in servos.items()
}


def reset_servo_motion_defaults():
    """Restore every servo to the speed/acceleration it was declared with."""
    for name, servo in servos.items():
        default_speed, default_accel = SERVO_MOTION_DEFAULTS[name]
        servo.max_speed = default_speed
        servo.max_accel = default_accel


# ============================================================
# Explicit MCP actions (ESP -> UART "action:<name>")
#
# These are NOT expression states.  They temporarily take ownership of the
# servos for a fixed 2-second window, then the latest normal state is
# re-entered.  Calibration still has absolute priority in main.py.
#
# Supported ESP action names:
#   action:shake_head  -> ROL
#   action:blink       -> LID
#   action:left_ear    -> EAL
#   action:right_ear   -> EAR
#   action:ears        -> EAL + EAR
#
# While an MCP action owns the servos, main.py pauses normal State animation,
# random blinking, Grove Vision tracking, and speaking-mouth motion.  This is
# intentional: a request such as "move your left ear" should visibly move only
# that requested part for the 2-second action window.
# ============================================================
MCP_ACTION_DURATION_MS = 2000

MCP_ACTION_NAMES = (
    "shake_head",
    "blink",
    "left_ear",
    "right_ear",
    "ears",
)

# Keep the old action geometry/cadence that was copied from Speaking.
MCP_HEAD_ANGLE_A = SPEAKING_NECK_LEFT
MCP_HEAD_ANGLE_B = SPEAKING_NECK_RIGHT
MCP_HEAD_INTERVAL_MS = SPEAKING_NECK_INTERVAL_MS

MCP_EAR_ANGLE_A = EAR_ANGLE_A
MCP_EAR_ANGLE_B = EAR_ANGLE_B
MCP_EAR_INTERVAL_MS = SPEAKING_EAR_INTERVAL_MS
MCP_EAR_MAX_SPEED = SPEAKING_EAR_MAX_SPEED
MCP_EAR_MAX_ACCEL = SPEAKING_EAR_MAX_ACCEL

# A 400 ms blink cycle gives repeated, readable blinks throughout the 2 s
# ownership window: 120 ms closed + 280 ms open.
MCP_BLINK_CYCLE_MS = 400
MCP_BLINK_CLOSED_MS = BLINK_DURATION_MS

_mcp_action = {
    "name": None,
    "started_at": 0,
    "last_toggle": 0,
    "side": False,
    "lid_restore_angle": float(BLINK_DEFAULT_OPEN_ANGLE),
}


def _freeze_all_servos_for_mcp():
    """Stop every currently-moving axis exactly where it is."""
    for servo in servos.values():
        if servo.enabled:
            # set_immediate(current pos) also clears residual velocity, so a
            # previous State cannot keep coasting while the MCP action owns
            # the robot.
            servo.set_immediate(servo.pos)


def _mcp_lid_restore_angle():
    """Choose the eyelid open/restore angle using the normal blink rules."""
    lid = servos["LID"]
    current_target = float(lid.target)

    if current_target <= BLINK_CLOSED_ANGLE + 5:
        return float(BLINK_DEFAULT_OPEN_ANGLE)

    return min(
        float(BLINK_DEFAULT_OPEN_ANGLE),
        current_target,
    )


def mcp_action_active():
    return _mcp_action["name"] is not None


def start_mcp_action(action_name, now=None):
    """
    Start/restart one explicit MCP action.

    A new MCP action immediately replaces an older MCP action and receives a
    fresh 2-second ownership window.  The latest normal current_state is still
    allowed to update in main.py while this action is running; it simply is not
    applied until MCP ownership ends.
    """
    global new_state_flag

    if now is None:
        now = time.ticks_ms()

    action_name = str(action_name).strip().lower()

    # Accept a few legacy spelling variants without changing the five public
    # ESP tool names.
    aliases = {
        "ear_wiggle": "ears",
        "ears_wiggle": "ears",
        "left_ear_wiggle": "left_ear",
        "right_ear_wiggle": "right_ear",
    }
    action_name = aliases.get(action_name, action_name)

    if action_name not in MCP_ACTION_NAMES:
        print("[MCP] unknown action:", action_name)
        return False

    old_action = _mcp_action["name"]

    # If an older MCP blink is being replaced, do not leave LID closed before
    # freezing the current pose for the new action.
    if old_action == "blink":
        servos["LID"].set_immediate(
            _mcp_action["lid_restore_angle"]
        )

    # Cancel any normal random blink cleanly before MCP ownership begins.
    # This also restores LID if a random blink happened to be in progress.
    update_blink(
        now,
        current_state,
        enabled=False,
    )

    # Capture the current expression's intended eyelid-open position BEFORE
    # freezing the servos.  Freezing intentionally changes each target to the
    # current physical/interpolated position.
    lid_restore_angle = _mcp_lid_restore_angle()

    # Every explicit action starts from the declaration defaults, then applies
    # only the temporary tuning it needs.  Normal State tuning is restored by
    # re-entering current_state after the action ends.
    reset_servo_motion_defaults()
    _freeze_all_servos_for_mcp()

    _mcp_action["name"] = action_name
    _mcp_action["started_at"] = now
    _mcp_action["last_toggle"] = now
    _mcp_action["side"] = False
    _mcp_action["lid_restore_angle"] = lid_restore_angle

    if action_name == "shake_head":
        servos["ROL"].max_speed = SERVO_MOTION_DEFAULTS["ROL"][0]
        servos["ROL"].max_accel = SERVO_MOTION_DEFAULTS["ROL"][1]
        servos["ROL"].set_target(MCP_HEAD_ANGLE_A)

    elif action_name == "blink":
        servos["LID"].set_immediate(BLINK_CLOSED_ANGLE)

    elif action_name == "left_ear":
        servos["EAL"].max_speed = MCP_EAR_MAX_SPEED
        servos["EAL"].max_accel = MCP_EAR_MAX_ACCEL
        servos["EAL"].set_target(MCP_EAR_ANGLE_A)

    elif action_name == "right_ear":
        servos["EAR"].max_speed = MCP_EAR_MAX_SPEED
        servos["EAR"].max_accel = MCP_EAR_MAX_ACCEL
        servos["EAR"].set_target(MCP_EAR_ANGLE_A)

    elif action_name == "ears":
        servos["EAL"].max_speed = MCP_EAR_MAX_SPEED
        servos["EAR"].max_speed = MCP_EAR_MAX_SPEED
        servos["EAL"].max_accel = MCP_EAR_MAX_ACCEL
        servos["EAR"].max_accel = MCP_EAR_MAX_ACCEL
        # Same numeric angle is intentional: the two ear mechanisms are a
        # mirror pair, producing opposite/symmetric physical movement.
        servos["EAL"].set_target(MCP_EAR_ANGLE_A)
        servos["EAR"].set_target(MCP_EAR_ANGLE_A)

    # The normal state must re-enter cleanly after MCP ownership ends.
    new_state_flag = True

    if old_action is None:
        print("[MCP] START {} -> 2000 ms exclusive ownership".format(action_name))
    else:
        print(
            "[MCP] REPLACE {} -> {} -> fresh 2000 ms ownership".format(
                old_action,
                action_name,
            )
        )

    return True


def _finish_mcp_action(now=None, reason="timeout"):
    """Release MCP ownership and prepare the latest normal state to resume."""
    global new_state_flag

    if _mcp_action["name"] is None:
        return

    if now is None:
        now = time.ticks_ms()

    old_action = _mcp_action["name"]

    if old_action == "blink":
        servos["LID"].set_immediate(
            _mcp_action["lid_restore_angle"]
        )

    _mcp_action["name"] = None

    # Remove temporary MCP speed/acceleration tuning.  The latest State will
    # then re-apply any state-specific tuning through new_state_flag.
    reset_servo_motion_defaults()
    new_state_flag = True

    print(
        "[MCP] END {} ({}) -> resume state {}".format(
            old_action,
            reason,
            current_state,
        )
    )


def update_mcp_action(now=None):
    """
    Advance the active MCP action without blocking.

    Returns True while MCP still owns the servos.  Returns False when no MCP
    action is active, including the same loop in which the 2-second timeout is
    reached; main.py can therefore resume the normal State immediately.
    """
    if now is None:
        now = time.ticks_ms()

    action_name = _mcp_action["name"]
    if action_name is None:
        return False

    if (
        time.ticks_diff(now, _mcp_action["started_at"])
        >= MCP_ACTION_DURATION_MS
    ):
        _finish_mcp_action(now, reason="timeout")
        return False

    # Re-assert temporary motion limits in case a new normal State arrived
    # over UART while MCP ownership was active and reset declaration defaults.
    if action_name == "shake_head":
        servos["ROL"].max_speed = SERVO_MOTION_DEFAULTS["ROL"][0]
        servos["ROL"].max_accel = SERVO_MOTION_DEFAULTS["ROL"][1]

        if (
            time.ticks_diff(now, _mcp_action["last_toggle"])
            >= MCP_HEAD_INTERVAL_MS
        ):
            _mcp_action["side"] = not _mcp_action["side"]
            servos["ROL"].set_target(
                MCP_HEAD_ANGLE_B
                if _mcp_action["side"]
                else MCP_HEAD_ANGLE_A
            )
            _mcp_action["last_toggle"] = now

    elif action_name == "blink":
        cycle_pos = (
            time.ticks_diff(now, _mcp_action["started_at"])
            % MCP_BLINK_CYCLE_MS
        )

        if cycle_pos < MCP_BLINK_CLOSED_MS:
            servos["LID"].set_immediate(BLINK_CLOSED_ANGLE)
        else:
            servos["LID"].set_immediate(
                _mcp_action["lid_restore_angle"]
            )

    elif action_name == "left_ear":
        servos["EAL"].max_speed = MCP_EAR_MAX_SPEED
        servos["EAL"].max_accel = MCP_EAR_MAX_ACCEL

        if (
            time.ticks_diff(now, _mcp_action["last_toggle"])
            >= MCP_EAR_INTERVAL_MS
        ):
            _mcp_action["side"] = not _mcp_action["side"]
            servos["EAL"].set_target(
                MCP_EAR_ANGLE_B
                if _mcp_action["side"]
                else MCP_EAR_ANGLE_A
            )
            _mcp_action["last_toggle"] = now

    elif action_name == "right_ear":
        servos["EAR"].max_speed = MCP_EAR_MAX_SPEED
        servos["EAR"].max_accel = MCP_EAR_MAX_ACCEL

        if (
            time.ticks_diff(now, _mcp_action["last_toggle"])
            >= MCP_EAR_INTERVAL_MS
        ):
            _mcp_action["side"] = not _mcp_action["side"]
            servos["EAR"].set_target(
                MCP_EAR_ANGLE_B
                if _mcp_action["side"]
                else MCP_EAR_ANGLE_A
            )
            _mcp_action["last_toggle"] = now

    elif action_name == "ears":
        servos["EAL"].max_speed = MCP_EAR_MAX_SPEED
        servos["EAR"].max_speed = MCP_EAR_MAX_SPEED
        servos["EAL"].max_accel = MCP_EAR_MAX_ACCEL
        servos["EAR"].max_accel = MCP_EAR_MAX_ACCEL

        if (
            time.ticks_diff(now, _mcp_action["last_toggle"])
            >= MCP_EAR_INTERVAL_MS
        ):
            _mcp_action["side"] = not _mcp_action["side"]
            ear_angle = (
                MCP_EAR_ANGLE_B
                if _mcp_action["side"]
                else MCP_EAR_ANGLE_A
            )
            servos["EAL"].set_target(ear_angle)
            servos["EAR"].set_target(ear_angle)
            _mcp_action["last_toggle"] = now

    return True


def apply_pose(pose):
    pose = pose_map.get(pose, pose_calibrate)
    for name, angle in pose.items():
        if name in servos:
            servos[name].set_target(angle)
            
def apply_state(state_name):
    state_func = state_map.get(state_name)
    if state_func:
        state_func()  # Call the function
    else:
        print(f"Unknown state: {state_name}")
        
#_________________# Poses (static servo positions used in states) #_________________#

pose_calibrate = { # Each dictionary key = servo name, value = angle
    "YAW": 90,
    "ROL": 90,
    "PIT": 80,
    "MOU": 170,
    "LID": 110,
    "EYL": 90,
    "EYR": 90,
    "EAL": 90,
    "EAR": 90,
}
pose_sleep = { # Each dictionary key = servo name, value = angle
#     "YAW": 88,
#     "RWH": 89,
    "ROL": 90,
    "PIT": 80,
    "MOU": 170,
    "LID": 30,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 150,
    "EAR": 30,
}

pose_base = { # Each dictionary key = servo name, value = angle
#     "YAW": 88,
#     "RWH": 89,
    "ROL": 90,
#     "PIT": 20,
#     "MOU": 170,
    "LID": 150,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 130,
    "EAR": 70,
}

pose_speaking = { # Each dictionary key = servo name, value = angle
#     "YAW": 88,
#     "RWH": 89,
#     "ROL": 90,
#     "PIT": 20,
    "MOU": 10,
#     "LID": 130,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 130,
    "EAR": 70,
}

pose_stop_speaking = { # Each dictionary key = servo name, value = angle
#     "YAW": 88,
#     "RWH": 89,
#     "ROL": 90,
#     "PIT": 20,
    "MOU": 150,
#     "LID": 130,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 130,
    "EAR": 70,
}

pose_thinking_1 = { # Each dictionary key = servo name, value = angle
#     "YAW": 90,
#     "RWH": 90,
    "ROL": 130,
#     "PIT": 50,
    "MOU": 150,
    "LID": 70,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 150,
    "EAR": 120,
}

pose_curious_2 = { # Each dictionary key = servo name, value = angle
#     "YAW": 90,
#     "RWH": 90,
    "ROL": 40,
#     "PIT": 10,
    "MOU": 160,
    "LID": 130,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 60,
    "EAR": 60,
}

pose_shock = { # Each dictionary key = servo name, value = angle
#     "YAW": 90,
#     "RWH": 90,
    "ROL": 90,
    "PIT": 10,
    "MOU": 10,
    "LID": 160,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 30,
    "EAR": 150,
}

pose_cool = { # Each dictionary key = servo name, value = angle
#     "YAW": 90,
#     "RWH": 90,
    "ROL": 90,
    "PIT": 10,
    "MOU": 160,
    "LID": 90,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 150,
    "EAR": 30,
}

pose_confident = { # Each dictionary key = servo name, value = angle
#     "YAW": 90,
#     "RWH": 90,
    "ROL": 90,
    "PIT": 10,
    "MOU": 160,
    "LID": 150,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 30,
    "EAR": 150,
}

pose_angry = { # Each dictionary key = servo name, value = angle
#     "YAW": 90,
#     "RWH": 90,
    "ROL": 90,
    "PIT": 80,
    "MOU": 160,
    "LID": 100,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 30,
    "EAR": 150,
}

pose_embarrassed = { # Each dictionary key = servo name, value = angle
#     "YAW": 90,
#     "RWH": 90,
    "ROL": 90,
    "PIT": 80,
    "MOU": 160,
    "LID": 90,
#     "EYL": 90,
#     "EYR": 90,
    "EAL": 150,
    "EAR": 30,
}

pose_map={
    "pose_calibrate": pose_calibrate,
    "pose_base": pose_base,
    "pose_thinking_1": pose_thinking_1,
    "pose_curious_2": pose_curious_2,
    "pose_sleep": pose_sleep,
    "pose_speaking": pose_speaking,
    "pose_stop_speaking": pose_stop_speaking,
    "pose_shock": pose_shock,
    "pose_cool": pose_cool,
    "pose_confident": pose_confident,
    "pose_angry": pose_angry,
    "pose_embarrassed": pose_embarrassed
}

#_________________#  #_________________#

#_________________# States (Mix of poses + animations) #_________________#



def state_startup():
    global new_state_flag
    if new_state_flag == True:
        apply_pose("pose_calibrate")
        new_state_flag = False

def state_sleep():
    global new_state_flag
    if new_state_flag == True:
        apply_pose("pose_sleep")
        new_state_flag = False
        
def state_confused():
    global new_state_flag
    if new_state_flag == True:
        apply_pose("pose_thinking_1")
        new_state_flag = False
        
def state_cool():
    global new_state_flag
    if new_state_flag == True:
        apply_pose("pose_cool")
        new_state_flag = False
        
def state_confident():
    global new_state_flag
    if new_state_flag == True:
        apply_pose("pose_confident")
        new_state_flag = False
        
def state_embarrassed():
    global new_state_flag
    if new_state_flag == True:
        apply_pose("pose_embarrassed")
        new_state_flag = False    
        
def state_angry():
    global new_state_flag
    if new_state_flag == True:
        apply_pose("pose_angry")
        new_state_flag = False 
        
def state_shock():
    global new_state_flag
    if new_state_flag == True:
        servos["EAL"].max_speed = 2000
        servos["EAR"].max_speed = 2000
        servos["MOU"].max_speed = 2000
        
        servos["EAL"].max_accel = 5000
        servos["EAR"].max_accel = 5000
        servos["MOU"].max_accel = 5000
        
        apply_pose("pose_shock")
        new_state_flag = False
        
def state_speaking():
    global new_state_flag
    global speaking_neck_side
    global last_speaking_neck_toggle
    global speaking_ear_side
    global last_speaking_ear_toggle

    now = time.ticks_ms()

    if new_state_flag == True:
        apply_pose("pose_speaking")

        # Speaking: restore faster ear motion.
        servos["EAL"].max_speed = SPEAKING_EAR_MAX_SPEED
        servos["EAR"].max_speed = SPEAKING_EAR_MAX_SPEED
        servos["EAL"].max_accel = SPEAKING_EAR_MAX_ACCEL
        servos["EAR"].max_accel = SPEAKING_EAR_MAX_ACCEL

        # Start left/right neck shake from one side.
        speaking_neck_side = False
        last_speaking_neck_toggle = now
        servos["ROL"].set_target(SPEAKING_NECK_LEFT)

        # Start alternating mirrored ears.
        speaking_ear_side = False
        last_speaking_ear_toggle = now
        servos["EAL"].set_target(EAR_ANGLE_A)
        servos["EAR"].set_target(EAR_ANGLE_A)

        # MOU is handled independently by update_speaking_mouth().
        new_state_flag = False

    # Keep shaking the neck left/right for the whole speaking state.
    if time.ticks_diff(now, last_speaking_neck_toggle) >= SPEAKING_NECK_INTERVAL_MS:
        speaking_neck_side = not speaking_neck_side

        if speaking_neck_side:
            servos["ROL"].set_target(SPEAKING_NECK_RIGHT)
        else:
            servos["ROL"].set_target(SPEAKING_NECK_LEFT)

        last_speaking_neck_toggle = now

    # Speaking: ears alternate continuously at the faster rate.
    if time.ticks_diff(now, last_speaking_ear_toggle) >= SPEAKING_EAR_INTERVAL_MS:
        speaking_ear_side = not speaking_ear_side

        if speaking_ear_side:
            servos["EAL"].set_target(EAR_ANGLE_B)
            servos["EAR"].set_target(EAR_ANGLE_B)
        else:
            servos["EAL"].set_target(EAR_ANGLE_A)
            servos["EAR"].set_target(EAR_ANGLE_A)

        last_speaking_ear_toggle = now

def state_thinking():
    now=time.ticks_ms()
    global animation_bool_a, last_toggle_a, animation_bool_b, last_toggle_b, new_state_flag
    if new_state_flag == True:
        apply_pose("pose_base")
        new_state_flag = False
    if animation_bool_a == False:
        servos["PIT"].set_target(50)
    if animation_bool_a == True:
        servos["PIT"].set_target(120)
    if time.ticks_diff(now, last_toggle_a) >= 700:
        animation_bool_a = not animation_bool_a   # flip the boolean
        last_toggle_a = now
        
        
def state_listen():
    global new_state_flag
    global listening_ear_side
    global last_listening_ear_toggle

    now = time.ticks_ms()

    if new_state_flag == True:
        apply_pose("pose_curious_2")

        # Listening: left/right neck returns to center.
        servos["ROL"].set_target(LISTENING_NECK_CENTER)

        # Listening: same alternating ear gesture, but physically slower.
        servos["EAL"].max_speed = LISTENING_EAR_MAX_SPEED
        servos["EAR"].max_speed = LISTENING_EAR_MAX_SPEED
        servos["EAL"].max_accel = LISTENING_EAR_MAX_ACCEL
        servos["EAR"].max_accel = LISTENING_EAR_MAX_ACCEL

        listening_ear_side = False
        last_listening_ear_toggle = now
        servos["EAL"].set_target(EAR_ANGLE_A)
        servos["EAR"].set_target(EAR_ANGLE_A)

        new_state_flag = False

    # Listening: ears keep alternating, but much more slowly.
    if time.ticks_diff(now, last_listening_ear_toggle) >= LISTENING_EAR_INTERVAL_MS:
        listening_ear_side = not listening_ear_side

        if listening_ear_side:
            servos["EAL"].set_target(EAR_ANGLE_B)
            servos["EAR"].set_target(EAR_ANGLE_B)
        else:
            servos["EAL"].set_target(EAR_ANGLE_A)
            servos["EAR"].set_target(EAR_ANGLE_A)

        last_listening_ear_toggle = now

def state_neutral():
    global new_state_flag
    if new_state_flag == True:
        apply_pose("pose_stop_speaking")
        new_state_flag = False
        
def state_happy():
    """
    HAPPY expression overlay based on the current neutral baseline.

    Differences from neutral:
      - neck stays tilted/turned to one side
      - blinking is disabled because "happy" is not in BLINK_ALLOWED_STATES
      - mirrored ears alternate faster

    Unmentioned servos are left at the neutral pose_stop_speaking behavior.
    """
    global new_state_flag
    global happy_ear_side
    global last_happy_ear_toggle

    now = time.ticks_ms()

    if new_state_flag == True:
        # Start from the same baseline used by neutral.
        apply_pose("pose_stop_speaking")

        # One-sided neck pose: no left/right oscillation.
        servos["ROL"].set_target(HAPPY_NECK_SIDE_ANGLE)

        # Happy does not blink; keep eyelid fully open.
        servos["LID"].set_target(HAPPY_LID_OPEN_ANGLE)

        # Faster ear motion than speaking/listening.
        servos["EAL"].max_speed = HAPPY_EAR_MAX_SPEED
        servos["EAR"].max_speed = HAPPY_EAR_MAX_SPEED
        servos["EAL"].max_accel = HAPPY_EAR_MAX_ACCEL
        servos["EAR"].max_accel = HAPPY_EAR_MAX_ACCEL

        happy_ear_side = False
        last_happy_ear_toggle = now

        # Same numeric command on both mirrored ear servos.
        servos["EAL"].set_target(HAPPY_EAR_ANGLE_A)
        servos["EAR"].set_target(HAPPY_EAR_ANGLE_A)

        new_state_flag = False

    if time.ticks_diff(now, last_happy_ear_toggle) >= HAPPY_EAR_INTERVAL_MS:
        happy_ear_side = not happy_ear_side

        if happy_ear_side:
            ear_angle = HAPPY_EAR_ANGLE_B
        else:
            ear_angle = HAPPY_EAR_ANGLE_A

        servos["EAL"].set_target(ear_angle)
        servos["EAR"].set_target(ear_angle)

        last_happy_ear_toggle = now


def state_sad():
    """
    SAD expression overlay based on the current neutral baseline.

    Differences from neutral:
      - PIT holds a head-down angle
      - blinking is disabled because "sad" is not in BLINK_ALLOWED_STATES
      - eyelid stays half closed
      - ears stay drooped/back
      - MOU is deliberately NOT owned by SAD; speech controls it independently

    X visual tracking may still move the eyeballs/base; vision.py R17
    deliberately disables only Y->PIT tracking while SAD is active.
    """
    global new_state_flag

    if new_state_flag == True:
        # Start from the same baseline used by neutral.
        apply_pose("pose_stop_speaking")
        new_state_flag = False

    # Re-assert these expression-owned axes continuously.
    # This also guarantees SAD wins immediately after a state transition
    # that happened during a blink.
    servos["PIT"].set_target(SAD_PITCH_ANGLE)
    servos["LID"].set_target(SAD_LID_ANGLE)
    servos["EAL"].set_target(SAD_LEFT_EAR_ANGLE)
    servos["EAR"].set_target(SAD_RIGHT_EAR_ANGLE)
    
def state_silly():
    global new_state_flag, animation_bool_a, last_toggle_a, animation_bool_b, last_toggle_b

    now = time.ticks_ms()

    if new_state_flag == True:
        # Start from the same baseline used by neutral.
        apply_pose("pose_stop_speaking")
        new_state_flag = False
        servos["EAL"].max_speed = 2000
        servos["EAR"].max_speed = 2000
        servos["ROL"].max_speed = 500
        
        servos["EAL"].max_accel = 5000
        servos["EAR"].max_accel = 5000
        servos["ROL"].max_accel = 400

    if animation_bool_a == False:
        servos["EAL"].set_target(60)
        servos["EAR"].set_target(60)
    if animation_bool_a == True:
        servos["EAL"].set_target(120)
        servos["EAR"].set_target(120)
    if time.ticks_diff(now, last_toggle_a) >= 500:
        animation_bool_a = not animation_bool_a   # flip the boolean
        last_toggle_a = now
        
    if animation_bool_b == False:
        servos["ROL"].set_target(70)
    if animation_bool_b == True:
        servos["ROL"].set_target(110)
    if time.ticks_diff(now, last_toggle_b) >= 750:
        animation_bool_b = not animation_bool_b   # flip the boolean
        last_toggle_b = now
        


def state_excited():
    global new_state_flag, animation_bool_a, last_toggle_a, animation_bool_b, last_toggle_b

    now = time.ticks_ms()

    if new_state_flag == True:
        # Start from the same baseline used by neutral.
        apply_pose("pose_stop_speaking")
        new_state_flag = False
        servos["EAL"].max_speed = 2000
        servos["EAR"].max_speed = 2000
        servos["PIT"].max_speed = 500
        
        servos["EAL"].max_accel = 5000
        servos["EAR"].max_accel = 5000
        servos["PIT"].max_accel = 400

    if animation_bool_a == False:
        servos["EAL"].set_target(60)
        servos["EAR"].set_target(60)
    if animation_bool_a == True:
        servos["EAL"].set_target(120)
        servos["EAR"].set_target(120)
    if time.ticks_diff(now, last_toggle_a) >= 250:
        animation_bool_a = not animation_bool_a   # flip the boolean
        last_toggle_a = now
        
    if animation_bool_b == False:
        servos["PIT"].set_target(55)
    if animation_bool_b == True:
        servos["PIT"].set_target(30)
    if time.ticks_diff(now, last_toggle_b) >= 500:
        animation_bool_b = not animation_bool_b   # flip the boolean
        last_toggle_b = now

def state_sleepy():
    global new_state_flag, animation_bool_a, last_toggle_a, animation_bool_b, last_toggle_b

    now = time.ticks_ms()

    if new_state_flag == True:
        # Start from the same baseline used by neutral.
        apply_pose("pose_cool")
        new_state_flag = False
        servos["ROL"].max_speed = 250
        servos["ROL"].max_accel = 100

    if animation_bool_a == False:
        servos["ROL"].set_target(70)
    if animation_bool_a == True:
        servos["ROL"].set_target(110)
    if time.ticks_diff(now, last_toggle_a) >= 1500:
        animation_bool_a = not animation_bool_a   # flip the boolean
        last_toggle_a = now

def state_limber_up():
    now=time.ticks_ms()
    global animation_bool_a, last_toggle_a, animation_bool_b, last_toggle_b, new_state_flag
    if new_state_flag == True:
        apply_pose("pose_base")
        new_state_flag = False
#     print("idle")
    if animation_bool_a == False:
#         servos["YAW"].set_target(50)
        servos["ROL"].set_target(70)
        servos["PIT"].set_target(70)
        servos["EAL"].set_target(100)
        servos["EYL"].set_target(60)
        servos["MOU"].set_target(20)
        servos["LID"].set_target(20)
        servos["EYR"].set_target(60)
        servos["EAL"].set_target(60)
        servos["EAR"].set_target(60)
    if animation_bool_a == True:
#         servos["YAW"].set_target(130)
        servos["ROL"].set_target(110)
        servos["PIT"].set_target(5)
        servos["EAL"].set_target(160)
        servos["EYL"].set_target(120)
        servos["MOU"].set_target(160)
        servos["LID"].set_target(160)
        servos["EYR"].set_target(120)
        servos["EAL"].set_target(120)
        servos["EAR"].set_target(120)
    if time.ticks_diff(now, last_toggle_a) >= 1000:
        animation_bool_a = not animation_bool_a   # flip the boolean
        last_toggle_a = now
        
# Note: system states:
#   - idle: sleeping, wakeword not initiated listening mode
#   - neutral: between finished speaking and begun listening. potentially use as marker for end of speech
#   - listening
#   - speaking
        
state_map={  #These emotion states mostly correspond to default "emojis" which XiaoZhi AI sends with its responses
    "neutral": state_neutral,
    "idle": state_sleep,
    "listening": state_listen,
    "state_startup": state_startup,
    "thinking": state_thinking,
    "speaking": state_speaking,
    "state_limber_up": state_limber_up,
    "happy": state_happy,
    "sad": state_sad,
    "excited": state_excited,
#     "winking": Coglet's eyelids are mechanically linked!
    "cool": state_cool,
    "relaxed": state_cool,
#     "delicious": Not sure how this would look
#     "kissy": Coglet is not your gf
    "confident": state_confident,
    "sleepy": state_sleepy,
    "silly": state_silly,
    "confused": state_confused,
    "angry": state_angry,
    "crying":state_sad,
    "loving": state_happy,
    "embarrassed": state_embarrassed,
    "surprised":state_shock,
    "shocked":state_shock
}

#_________________#  #_________________#            



