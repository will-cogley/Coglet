# motion_servo.py  (MicroPython for RP2040)
from machine import Pin, UART
import time, random
import urandom
import servoclass
from servoclass import Servo
import sys, select, uselect
import math
import animation
from animation import servos
from vision import EyeFollower

ESP = UART(1, baudrate=115200, tx=Pin(4), rx=Pin(5))
rx_buffer = b""

# ============================================================
# CogNog / Coglet PCB V2.0 physical controls
# ============================================================
CALIBRATE_PIN = 20
FACETRACK_TOGGLE_PIN = 21
WIGGLE_PIN = 12
FRONT_LED_PIN = 25

calibrate_bool = False
last_toggle = 0


# V2 controls are active LOW.
mode = Pin(CALIBRATE_PIN, Pin.IN, Pin.PULL_UP)
facetrack_toggle = Pin(FACETRACK_TOGGLE_PIN, Pin.IN, Pin.PULL_UP)
wiggle_button = Pin(WIGGLE_PIN, Pin.IN, Pin.PULL_UP)
front_LED = Pin(25, Pin.OUT)

FACETRACK_ON_LEVEL = 0
facetrack_enabled_prev = None

# XiaoZhi device speech activity is tracked separately from emotion.
# Emotions such as "sad"/"happy" must NOT stop the mouth animation.
speech_active = False

# These device states explicitly mean the assistant is no longer speaking.
SPEECH_STOP_SIGNALS = (
    "neutral",
    "idle",
    "listening",
    "thinking",
    "state_startup",
)

# Calibration wiggle:
#   - only runs while Calibration Mode is active AND GPIO12 is held
#   - commands +/-10 degrees around pose_calibrate
#   - non-blocking; PCA updates are limited to 50 Hz
#   - release immediately commands every active servo back to home
WIGGLE_AMPLITUDE_DEG = 10.0
WIGGLE_PERIOD_MS = 1200
WIGGLE_UPDATE_MS = 20

calibration_active_prev = False
wiggle_active_prev = False
wiggle_started_at = time.ticks_ms()
last_wiggle_update = time.ticks_ms()

# Filled from animation.pose_calibrate after PCA/Servo objects exist.
calibration_home = {}


def _clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def _refresh_calibration_home():
    """
    Build the diagnostic center position from the project's existing
    pose_calibrate values.

    This deliberately does not invent a second calibration table.
    If pose_calibrate is changed later, the wiggle center follows it.
    """
    calibration_home.clear()

    for name, servo in servos.items():
        raw_home = animation.pose_calibrate.get(name, servo.target)
        safe_home = _clamp(
            float(raw_home),
            float(servo.min_angle),
            float(servo.max_angle),
        )
        calibration_home[name] = safe_home

        low_room = safe_home - float(servo.min_angle)
        high_room = float(servo.max_angle) - safe_home

        if (
            low_room < WIGGLE_AMPLITUDE_DEG
            or high_room < WIGGLE_AMPLITUDE_DEG
        ):
            print(
                "[CAL] WARN {} home={} range={}..{} "
                "cannot reach full +/-{} deg; motion will be safety-clamped".format(
                    name,
                    safe_home,
                    servo.min_angle,
                    servo.max_angle,
                    WIGGLE_AMPLITUDE_DEG,
                )
            )


def _command_calibration_home(immediate=False):
    for name, servo in servos.items():
        if not servo.enabled:
            continue

        home = calibration_home[name]

        if immediate:
            servo.set_immediate(home)
        else:
            servo.set_target(home)


def _update_calibration_wiggle(now):
    """
    Return True while calibration owns all servo commands.

    The diagnostic uses a smooth sine command instead of a blocking
    sleep()/while wiggle loop.  This keeps UART, Vision AI servicing,
    and the main loop alive while the button is held.
    """
    global calibration_active_prev
    global wiggle_active_prev
    global wiggle_started_at
    global last_wiggle_update

    calibration_active = (mode.value() == 0)
    wiggle_pressed = (wiggle_button.value() == 0)

    # Enter Calibration Mode: calibration owns the servos.
    if calibration_active and not calibration_active_prev:
        _refresh_calibration_home()
        _command_calibration_home(immediate=False)
        wiggle_active_prev = False
        print("[CAL] ENTER: GPIO20=LOW -> calibration owns servos")

    if calibration_active:
        if wiggle_pressed:
            if not wiggle_active_prev:
                wiggle_started_at = now
                last_wiggle_update = time.ticks_add(
                    now,
                    -WIGGLE_UPDATE_MS,
                )
                print(
                    "[CAL] WIGGLE START: GPIO12=LOW, amplitude=+/-{} deg".format(
                        WIGGLE_AMPLITUDE_DEG
                    )
                )

            if (
                time.ticks_diff(now, last_wiggle_update)
                >= WIGGLE_UPDATE_MS
            ):
                elapsed = time.ticks_diff(now, wiggle_started_at)
                phase = (
                    (elapsed % WIGGLE_PERIOD_MS)
                    * (2.0 * math.pi)
                    / WIGGLE_PERIOD_MS
                )
                offset = WIGGLE_AMPLITUDE_DEG * math.sin(phase)

                for name, servo in servos.items():
                    if not servo.enabled:
                        continue
                    servo.set_immediate(
                        calibration_home[name] + offset
                    )

                last_wiggle_update = now

        else:
            # Exact release path: command the calibrated home immediately.
            if wiggle_active_prev:
                _command_calibration_home(immediate=True)
                print(
                    "[CAL] WIGGLE STOP: GPIO12 released -> "
                    "all active servos HOME"
                )

            # Keep the home target asserted while calibration is active.
            # set_target() does not create extra I2C writes by itself.
            for name, servo in servos.items():
                if servo.enabled:
                    servo.set_target(calibration_home[name])

        wiggle_active_prev = wiggle_pressed

    # Leaving Calibration Mode also terminates any wiggle immediately.
    elif calibration_active_prev:
        if wiggle_active_prev:
            _command_calibration_home(immediate=True)
            print("[CAL] WIGGLE STOP: left Calibration Mode")

        wiggle_active_prev = False

        # The latest XiaoZhi state may have changed while calibration owned
        # the servos. Re-enter it cleanly on this same loop.
        animation.new_state_flag = True
        print("[CAL] EXIT: normal animation/vision control restored")

    calibration_active_prev = calibration_active
    return calibration_active


# Grove Vision AI V2 visual following.
eye_follower = EyeFollower(servos)


def _update_facetrack_toggle():
    """
    GP21 controls ONLY Grove Vision / visual-follow behavior.

    OFF does not suppress XiaoZhi animations and does not move unrelated
    servos.  On the OFF edge, only EYL/EYR/PIT are released to neutral once;
    the normal animation state is then allowed to own any shared axis.
    """
    global facetrack_enabled_prev

    enabled = (facetrack_toggle.value() == FACETRACK_ON_LEVEL)

    if facetrack_enabled_prev is None:
        facetrack_enabled_prev = enabled

        if enabled:
            print("[FACE] GP21 startup: ON -> Grove Vision tracking enabled")
        else:
            eye_follower.release_to_home()
            animation.new_state_flag = True
            print(
                "[FACE] GP21 startup: OFF -> Vision paused; "
                "EYL/EYR/PIT released to neutral"
            )

        return enabled

    if enabled != facetrack_enabled_prev:
        facetrack_enabled_prev = enabled

        if enabled:
            animation.new_state_flag = True
            print(
                "[FACE] SWITCH ON: Grove Vision startup/inference + "
                "visual tracking ENABLED"
            )
        else:
            # Only the three tracking-owned axes are touched.
            eye_follower.release_to_home()

            # Re-enter the current XiaoZhi state once so any legitimate
            # animation ownership (for example PIT in an emotion) can resume.
            animation.new_state_flag = True

            print(
                "[FACE] SWITCH OFF: Grove Vision PAUSED; "
                "EYL/EYR/PIT released; other servos/animations unchanged"
            )

    return enabled


# track direction for each servo (1 = going to max, -1 = going to min)
directions = {name: 1 for name in servos.keys()}

last_time = time.ticks_ms()
last_switch = last_time

# servos["YAW"].set_target(88)
# # servos["RWH"].set_target(89)


print("")
print("==============================================")
print(" Coglet V1 baseline on PCB V2.0")
print(" ESP bridge: UART1 TX=GPIO4 RX=GPIO5 115200")
print(" PCA: SDA=GPIO6 SCL=GPIO7 nOE=GPIO8")
print(" Calibrate: GPIO20 active LOW")
print(" Facetrack: GPIO21 active LOW; controls Grove Vision only")
print(" Wiggle: GPIO12 active LOW, calibration-only +/-10 deg")
print(" Vision: UART0 TX=GPIO0 RX=GPIO1 @ 921600")
print(" Vision control: EYL + EYR only")
print("==============================================")

if not servoclass.is_ready():
    print("[FATAL] PCA9685 0x40 was not detected.")
    print("[FATAL] Servo outputs stay disabled.")
    while True:
        time.sleep_ms(1000)

# Servo objects are created while PCA9685 nOE is HIGH.
# Most channels keep the legacy 90-degree preload, but the eyelid's actual
# startup/calibration position is 110 degrees. Preload that value BEFORE
# enabling nOE so LID does not receive a 90 -> 110 double command at boot.
servos["LID"].set_immediate(animation.pose_calibrate["LID"])
print(
    "[LID] boot preload: {} deg while PWM_nOE is disabled".format(
        animation.pose_calibrate["LID"]
    )
)

servoclass.enable_outputs()

# Build the initial home table once; it is refreshed every time
# Calibration Mode is entered.
_refresh_calibration_home()


while True:
    now = time.ticks_ms()
    dt = time.ticks_diff(now, last_time) / 1000.0
    last_time = now

    if ESP.any():
        rx_buffer += ESP.read()   # bytes + bytes = OK
        while b"\n" in rx_buffer:
            line, rx_buffer = rx_buffer.split(b"\n", 1)
            rcvstate = line.decode().strip()
            print("RX:", rcvstate)

            # Explicit MCP one-shot/temporary actions are a separate UART
            # namespace from normal XiaoZhi expression states.  The RP2040
            # owns the requested action for exactly 2 seconds.
            if rcvstate.startswith("action:"):
                action_name = rcvstate[7:].strip()
                animation.start_mcp_action(action_name, now)
                continue

            # Speech activity and expression are two separate dimensions.
            # "speaking" starts the mouth animation.
            # happy/sad only change expression and leave speech_active untouched.
            # Device states such as neutral/listening/thinking stop speech.
            if rcvstate == "speaking":
                if not speech_active:
                    print("[MOUTH] speech flag: OFF -> ON")
                speech_active = True
            elif rcvstate in SPEECH_STOP_SIGNALS:
                if speech_active:
                    print("[MOUTH] speech flag: ON -> OFF ({})".format(rcvstate))
                speech_active = False

            if rcvstate in animation.state_map:
                # XiaoZhi may report the same state repeatedly during one
                # long TTS response. Do not re-enter the same state, because
                # that would reset the Speaking timers again and again.
                if rcvstate != animation.current_state:
                    print(
                        "state change:",
                        animation.current_state,
                        "->",
                        rcvstate,
                    )
                    # Restore the motion limits declared in animation.servos
                    # before entering a different normal state. This prevents
                    # temporary tuning from excited/silly/shock/etc. leaking
                    # into the next expression.
                    animation.reset_servo_motion_defaults()

                    animation.current_state = rcvstate
                    animation.new_state_flag = True
                else:
                    print("same state ignored:", rcvstate)

    # Calibration retains absolute priority over every servo command.
    # --- START TEMPORARY ANIMATION TEST OVERRIDE ---
    calibration_owns_servos = _update_calibration_wiggle(now)


    if calibration_owns_servos:
        if time.ticks_diff(now, last_toggle) >= 500:
            calibrate_bool = not calibrate_bool   # flip the boolean
            last_toggle = now
        
        # Calibration also pauses new Grove Vision work.
        animation.update_blink(
            now,
            animation.current_state,
            enabled=False,
        )
        eye_follower.update(
            now,
            animation.current_state,
            enabled=False,
        )

    else:
        calibrate_bool = False

        # MCP actions have priority over normal State / Speaking / random Blink
        # / Vision for a fixed 2-second window.  update_mcp_action() returns
        # False on the exact loop where that window expires, so the newest
        # normal state resumes immediately without an extra dead frame.
        mcp_owns_servos = animation.update_mcp_action(now)

        if mcp_owns_servos:
            # Keep background systems alive logically but prevent any of them
            # from issuing competing servo commands during MCP ownership.
            animation.update_blink(
                now,
                animation.current_state,
                enabled=False,
            )
            eye_follower.update(
                now,
                animation.current_state,
                enabled=False,
            )

        else:
            # GP21 affects ONLY Grove Vision / face tracking.
            facetrack_enabled = _update_facetrack_toggle()

            # XiaoZhi animations keep running whether Facetrack is ON or OFF.
            animation.apply_state(animation.current_state)

            animation.update_blink(
                now,
                animation.current_state,
                enabled=True,
            )

            # When GP21 is OFF, vision.py pauses new Vision AI requests and
            # performs no visual-follow servo writes.
            eye_follower.update(
                now,
                animation.current_state,
                enabled=facetrack_enabled,
            )

            # MOU is independent from current emotion.  Run this after all
            # expression/vision updates so speech has final ownership of the mouth.
            animation.update_speaking_mouth(now, speech_active)
        
    front_LED.value(calibrate_bool)

    # During wiggle, set_immediate() writes the PCA command directly.
    # Servo.update() remains safe because pos/target/vel are synchronized
    # by set_immediate(). During non-wiggle calibration it moves toward home.
    for s in servos.values():
        s.update(dt)

    time.sleep_ms(1)



