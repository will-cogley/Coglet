# Grove Vision AI V2 -> visual follower (camera inside the eye)
# MicroPython / RP2040 / Coglet PCB V2.0+
#
# PCB wiring:
#   RP2040 GPIO0 / UART0 TX -> Grove Vision AI V2 RX
#   RP2040 GPIO1 / UART0 RX <- Grove Vision AI V2 TX
#   921600 baud, 8N1
#
# Axes owned by Facetrack:
#   X -> EYL + EYR (eyeballs), with base YAW taking over when the eyes reach
#        their soft limit (printed parts limit eye travel)
#   Y -> PIT (neck pitch)
#
# ---------------------------------------------------------------------------
# Why this version is different (R18)
#
# The camera sits INSIDE the eye. The image therefore only tells us where the
# face is relative to where the eye is pointing *at the moment the frame was
# captured*. Mapping "pixel error -> absolute eye angle" (R14..R17) fights
# itself: as soon as the eye turns toward the face, the error shrinks and the
# eye is pulled back to centre. That caused the slow, never-quite-centred,
# shaky behaviour; heavy filtering then made it even slower.
#
# R18 does what the geometry says:
#   face_direction = eye_angle_at_capture + pixel_error * DEG_PER_PX
# That is the face direction in the head/body frame. It does not depend on
# where the eye is now, so the loop no longer fights itself. Then:
#   1. a One-Euro filter on that direction (smooth when still, fast when moving)
#   2. velocity prediction between frames (no 30 Hz stair-steps)
#   3. command the eyes directly; Servo.update() keeps motion smooth
#   4. if the wanted direction is beyond the eye soft limit, the base turns
#      (speed proportional to the overflow) so the eyes never sit hard-over
# Capture time = arrival time - SSCMA perf (pre+infer+post) - exposure.
# Continuous inference (AT+INVOKE=-1,0,1) removes the per-frame round trip;
# falls back to single-shot automatically if the module refuses it.
# ---------------------------------------------------------------------------
#
# SSCMA detection box format: [x, y, w, h, score, target], x/y = box centre in
# the 240x240 image.

from machine import Pin, UART
import math
import time

try:
    import ujson as json
except ImportError:
    import json


# ======================================================================
# Easy tuning section
# ======================================================================

VISION_UART_ID = 0
VISION_TX_PIN = 0
VISION_RX_PIN = 1
VISION_BAUDRATE = 921600

FRAME_WIDTH = 240
FRAME_HEIGHT = 240
FRAME_CENTER_X = FRAME_WIDTH / 2.0
FRAME_CENTER_Y = FRAME_HEIGHT / 2.0

# ---------------------------------------------------------------- geometry
# Servo degrees the camera has to turn to move the face by ONE pixel in the
# image (depends on the lens field of view and the eye/neck linkage).
#
# How to tune (only thing that really needs tuning):
#   - look at Coglet, then step sideways quickly
#   - eyes overshoot and swing back        -> value too HIGH, lower it
#   - eyes need 2-3 visible steps to land  -> value too LOW, raise it
# The tracker stays stable from about half to double the correct value.
X_SERVO_DEG_PER_PX = 0.22
Y_SERVO_DEG_PER_PX = 0.22

# Both eyes use 90 deg as their neutral command.
LEFT_EYE_CENTER = 90.0
RIGHT_EYE_CENTER = 90.0

# Eye soft limits (printed parts). Beyond these the base takes over.
LEFT_EYE_MIN = 60.0
LEFT_EYE_MAX = 130.0
RIGHT_EYE_MIN = 60.0
RIGHT_EYE_MAX = 130.0

# +1: a larger servo angle turns the camera toward image +X (right).
# If the eyes run AWAY from the face, flip BOTH to -1.
LEFT_EYE_DIRECTION = 1.0
RIGHT_EYE_DIRECTION = 1.0

# Neck pitch (PIT). animation.py hard limit is 1..80 deg.
# +1: a larger PIT angle turns the camera toward image +Y (down).
PITCH_CENTER = 50.0
PITCH_MIN = 3.0
PITCH_MAX = 78.0
PITCH_DIRECTION = 1.0

# Faster neck while tracking (animation.py default PIT accel is 400 deg/s^2,
# which made the head feel sluggish). Restored when pitch tracking stops.
PITCH_TRACK_MAX_SPEED = 600.0
PITCH_TRACK_MAX_ACCEL = 900.0

# ----------------------------------------------------------- base handoff
# animation.py YAW range is 30..150 deg.
BASE_YAW_CENTER = 90.0
BASE_YAW_MIN = 30.0
BASE_YAW_MAX = 150.0
# +1: a larger YAW angle turns the camera toward image +X (same as the eyes).
BASE_YAW_DIRECTION = 1.0
# Eye-servo degrees equivalent to one base-servo degree (camera turn).
BASE_TO_GAZE_RATIO = 1.0
# The eyes may use their full soft range briefly, but should not rest near
# it: the base turns whenever the wanted gaze is more than COMFORT_MARGIN
# inside the soft limit, until the eyes are back in the comfortable zone.
# Base speed is proportional to the excess (deg/s per deg), capped.
BASE_COMFORT_MARGIN_DEG = 10.0
BASE_HANDOFF_DEADBAND_DEG = 1.0
BASE_HANDOFF_GAIN = 2.5
BASE_MAX_SPEED_DEG_S = 45.0

# ------------------------------------------------------------- smoothing
# One-Euro filter on the face direction (degrees).
#   MIN_CUTOFF: lower = calmer when the face is still (more lag)
#   BETA:       higher = less lag when the face moves fast
X_MIN_CUTOFF_HZ = 1.2
X_BETA = 0.04
Y_MIN_CUTOFF_HZ = 0.9
Y_BETA = 0.03
DERIVATIVE_CUTOFF_HZ = 1.0

# Predict the face motion between frames (fraction of the measured velocity
# applied for the time since capture). 0 disables prediction.
PREDICTION_GAIN = 0.8
PREDICTION_MAX_DEG = 6.0
# Below this face speed (deg/s) there is no prediction, so detector noise on
# a still face is not turned into eye twitching.
PREDICTION_MIN_SPEED_DEG_S = 8.0

# Fraction of the measured pixel error applied per frame. 1.0 = jump straight
# to the face (fastest, but overshoots if DEG_PER_PX is set too high);
# 0.75 keeps a safety margin and still lands within 2-3 frames.
CORRECTION_GAIN = 0.75

# Ignore pixel errors this close to the image centre (detector noise).
X_DEADZONE_PX = 3.0
Y_DEADZONE_PX = 4.0

# --------------------------------------------------------------- timing
# Continuous inference stream (recommended). Falls back to single-shot.
CONTINUOUS_INVOKE = True
# Sensor exposure/readout before preprocessing starts (not in SSCMA perf).
SENSOR_LATENCY_MS = 12
# Used when a reply carries no perf field.
DEFAULT_PIPELINE_MS = 40
# Restart the stream if no frame arrives for this long.
STREAM_STALL_MS = 1500
# Single-shot mode only: pause between frames.
INVOKE_GAP_MS = 5

# If the face disappears for this long, glide back to centre.
TARGET_LOST_MS = 650
RETURN_SPEED_DEG_S = 40.0

# Servo position history (for capture-time lookup).
HISTORY_INTERVAL_MS = 4
HISTORY_LENGTH = 120          # ~480 ms

# Logging
FRAME_LOG_EVERY = 30
CONTROL_LOG_EVERY_MS = 1000

# Do not override special animations/calibration-like modes.
ACTIVE_STATES = (
    "speaking",
    "listening",
    "thinking",
    "neutral",
    "happy",
    "sad",
)

# SAD owns the PIT servo for its head-down expression.
# X tracking (eyes + base handoff) still remains active in SAD.
PITCH_TRACKING_STATES = (
    "speaking",
    "listening",
    "thinking",
    "neutral",
    "happy",
)


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def move_towards(current, target, maximum_delta):
    if current < target:
        return min(current + maximum_delta, target)
    if current > target:
        return max(current - maximum_delta, target)
    return current


class OneEuroFilter:
    """One-Euro filter (Casiez et al.): adaptive low-pass, x in degrees."""

    def __init__(self, min_cutoff, beta, d_cutoff):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.ready = False
        self.x = 0.0
        self.dx = 0.0
        self.t = 0.0

    @staticmethod
    def _alpha(dt, cutoff):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self, x, t):
        self.ready = True
        self.x = x
        self.dx = 0.0
        self.t = t

    def update(self, x, t):
        if not self.ready:
            self.reset(x, t)
            return self.x
        dt = t - self.t
        if dt <= 0.0005:
            dt = 0.0005
        raw_dx = (x - self.x) / dt
        a_d = self._alpha(dt, self.d_cutoff)
        self.dx = a_d * raw_dx + (1.0 - a_d) * self.dx
        cutoff = self.min_cutoff + self.beta * abs(self.dx)
        a = self._alpha(dt, cutoff)
        self.x = a * x + (1.0 - a) * self.x
        self.t = t
        return self.x


class GroveVisionAI:
    """
    Non-blocking SSCMA UART driver.

    Startup queries: AT+ID? AT+VER? AT+STAT? AT+MODEL? AT+SENSOR?
    Runtime: AT+INVOKE=-1,0,1 (continuous) or AT+INVOKE=1,0,1 (single-shot).

    Exposes for the follower:
      frame_id          increments on every inference result
      last_boxes        boxes of the newest result
      last_capture_ms   estimated capture time of the newest result
    """

    def __init__(self):
        self.uart = self._open_uart()

        self.rx_buffer = b""
        self.max_buffer = 8192

        self.boot_queries = (
            "AT+ID?",
            "AT+VER?",
            "AT+STAT?",
            "AT+MODEL?",
            "AT+SENSOR?",
        )
        self.query_index = 0

        self.waiting_command = None
        self.waiting_since = 0

        self.invoke_pending = False
        self.invoke_since = 0

        self.continuous = CONTINUOUS_INVOKE
        self.streaming = False

        now = time.ticks_ms()
        self.next_action_at = time.ticks_add(now, 1800)
        self.last_no_rx_warning = now

        self.online = False
        self.frames = 0
        self.frame_id = 0
        self.last_boxes = []
        self.last_frame_at = now
        self.last_capture_ms = now
        self.last_perf = None

        # FPS / latency statistics
        self.stat_frames = 0
        self.stat_pipeline_sum = 0
        self.stat_since = now

        # Logical run control (no hardware enable pin): OFF stops inference.
        self.run_enabled = True

        print("")
        print("========== Grove Vision AI V2 ==========")
        print("UART0 TX=GPIO0 -> Vision RX")
        print("UART0 RX=GPIO1 <- Vision TX")
        print("921600 baud, 8N1")
        print("mode: {}".format("continuous" if self.continuous else "single-shot"))
        print("========================================")

    def _open_uart(self):
        try:
            return UART(
                VISION_UART_ID,
                baudrate=VISION_BAUDRATE,
                bits=8,
                parity=None,
                stop=1,
                tx=Pin(VISION_TX_PIN),
                rx=Pin(VISION_RX_PIN),
                rxbuf=4096,
            )
        except TypeError:
            return UART(
                VISION_UART_ID,
                baudrate=VISION_BAUDRATE,
                bits=8,
                parity=None,
                stop=1,
                tx=Pin(VISION_TX_PIN),
                rx=Pin(VISION_RX_PIN),
            )

    @staticmethod
    def _expected_name(command):
        """
        SSCMA response name for an AT command.
          AT+ID?          -> "ID?"   (query names keep the '?')
          AT+INVOKE=...   -> "INVOKE"
          AT+BREAK        -> "BREAK"
        """
        body = command[3:] if command.startswith("AT+") else command
        if "=" in body:
            return body.split("=", 1)[0]
        return body

    def _send(self, command):
        self.uart.write((command + "\r").encode())
        self.waiting_command = command
        self.waiting_since = time.ticks_ms()
        if not command.startswith("AT+INVOKE=1,"):
            print("[VISION TX]", command)

    def _read_uart(self):
        if not self.uart.any():
            return
        chunk = self.uart.read()
        if not chunk:
            return
        # Arrival time of this chunk; used for the capture-time estimate.
        rx_ms = time.ticks_ms()
        self.online = True
        self.rx_buffer += chunk
        if len(self.rx_buffer) > self.max_buffer:
            self.rx_buffer = self.rx_buffer[-self.max_buffer:]

        while b"\n" in self.rx_buffer:
            line, self.rx_buffer = self.rx_buffer.split(b"\n", 1)
            line = line.strip()
            if line:
                self._handle_line(line, rx_ms)

    def _handle_line(self, line, rx_ms):
        try:
            text = line.decode("utf-8")
        except UnicodeError:
            return
        if not text.startswith("{"):
            return
        try:
            message = json.loads(text)
        except Exception:
            return

        response_type = message.get("type")
        name = message.get("name", "")
        code = message.get("code")
        data = message.get("data")

        if response_type == 0:
            self._handle_operation(name, code, data)
        elif response_type == 1:
            self._handle_event(name, code, data, rx_ms, len(line))

    def _handle_operation(self, name, code, data):
        # Single-shot mode gets an INVOKE reply every frame: don't log those.
        single_shot_reply = (name == "INVOKE" and self.waiting_command is not None
                             and self.waiting_command.startswith("AT+INVOKE=1,"))
        if not single_shot_reply:
            print("[VISION RX] {} code={} data={}".format(name, code, data))

        if self.waiting_command is None:
            return
        if name != self._expected_name(self.waiting_command):
            return

        command = self.waiting_command
        self.waiting_command = None
        now = time.ticks_ms()

        if command.startswith("AT+INVOKE=-1"):
            if code == 0:
                self.streaming = True
                self.last_frame_at = now
                print("[VISION] continuous inference stream STARTED")
            else:
                # Module refused continuous mode: use single-shot from now on.
                self.continuous = False
                self.streaming = False
                self.next_action_at = time.ticks_add(now, 200)
                print("[VISION] continuous mode refused (code={}), using single-shot".format(code))
            return

        if command.startswith("AT+INVOKE"):
            if code == 0:
                self.invoke_pending = True
                self.invoke_since = now
            else:
                self.invoke_pending = False
                self.next_action_at = time.ticks_add(now, 500)
            return

        if command == "AT+BREAK":
            self.streaming = False
            self.next_action_at = time.ticks_add(now, 50)
            return

        print("[VISION OK]", command)
        if self.query_index < len(self.boot_queries):
            self.query_index += 1
        self.next_action_at = time.ticks_add(now, 120)

    def _handle_event(self, name, code, data, rx_ms, line_bytes):
        if name != "INVOKE":
            return

        self.invoke_pending = False
        self.frames += 1
        self.last_frame_at = rx_ms
        if not self.streaming:
            self.next_action_at = time.ticks_add(rx_ms, INVOKE_GAP_MS)

        if not self.run_enabled:
            # A frame already in flight when Facetrack was switched off.
            self.last_boxes = []
            return

        pipeline_ms = DEFAULT_PIPELINE_MS
        perf = data.get("perf") if isinstance(data, dict) else None
        if isinstance(perf, (list, tuple)) and len(perf) >= 3:
            try:
                pipeline_ms = int(perf[0]) + int(perf[1]) + int(perf[2])
                self.last_perf = perf
            except (TypeError, ValueError):
                pass
        # UART transfer of this line (10 bits per byte).
        transfer_ms = (line_bytes * 10 * 1000) // VISION_BAUDRATE
        self.last_capture_ms = time.ticks_add(
            rx_ms, -(pipeline_ms + transfer_ms + SENSOR_LATENCY_MS))

        self.stat_frames += 1
        self.stat_pipeline_sum += pipeline_ms + transfer_ms + SENSOR_LATENCY_MS

        if code != 0 or not isinstance(data, dict):
            self.last_boxes = []
        else:
            boxes = data.get("boxes", [])
            self.last_boxes = boxes if isinstance(boxes, list) else []
        # Publish the frame only after boxes and capture time are consistent.
        self.frame_id += 1

        if self.frames % FRAME_LOG_EVERY != 0:
            return
        best = self.get_best_box()
        if best is None:
            print("[VISION FRAME {}] no target".format(self.frames))
        else:
            print("[VISION FRAME {}] target={} score={} x={} y={}".format(
                self.frames, best[5], best[4], best[0], best[1]))

    def get_best_box(self):
        best = None
        for box in self.last_boxes:
            if not isinstance(box, (list, tuple)):
                continue
            if len(box) < 6:
                continue
            if best is None or box[4] > best[4]:
                best = box
        return best

    def take_stats(self, now):
        """Return (fps, average latency ms) since the previous call."""
        elapsed = time.ticks_diff(now, self.stat_since)
        if elapsed <= 0:
            return 0.0, 0.0
        fps = self.stat_frames * 1000.0 / elapsed
        latency = (self.stat_pipeline_sum / self.stat_frames) if self.stat_frames else 0.0
        self.stat_frames = 0
        self.stat_pipeline_sum = 0
        self.stat_since = now
        return fps, latency

    def set_enabled(self, enabled, now=None):
        enabled = bool(enabled)
        if now is None:
            now = time.ticks_ms()
        if enabled == self.run_enabled:
            return
        self.run_enabled = enabled
        self.last_boxes = []

        if enabled:
            self.next_action_at = now
            print("[VISION] ENABLED: startup/inference requests resumed")
        else:
            if self.streaming:
                # Stop the stream; frames already in flight are drained/ignored.
                self._send("AT+BREAK")
                self.streaming = False
            print("[VISION] DISABLED: inference stopped")

    def update(self, now=None):
        if now is None:
            now = time.ticks_ms()

        self._read_uart()

        # Recover from a lost command response.
        if self.waiting_command is not None:
            if time.ticks_diff(now, self.waiting_since) > 1800:
                print("[VISION TIMEOUT]", self.waiting_command)
                if self.waiting_command.startswith("AT+INVOKE=-1"):
                    self.continuous = False
                    print("[VISION] no reply to continuous INVOKE, using single-shot")
                self.waiting_command = None
                self.streaming = False
                self.next_action_at = time.ticks_add(now, 350)
            return

        if self.streaming:
            if time.ticks_diff(now, self.last_frame_at) > STREAM_STALL_MS:
                print("[VISION] stream stalled, restarting")
                self._send("AT+BREAK")
            return

        # Single-shot: INVOKE returns an operation response, then an event.
        if self.invoke_pending:
            if time.ticks_diff(now, self.invoke_since) > 3000:
                print("[VISION TIMEOUT] INVOKE event")
                self.invoke_pending = False
                self.next_action_at = time.ticks_add(now, 500)
            return

        if not self.run_enabled:
            return
        if time.ticks_diff(now, self.next_action_at) < 0:
            return

        if self.query_index < len(self.boot_queries):
            self._send(self.boot_queries[self.query_index])
            return

        if self.continuous:
            self._send("AT+INVOKE=-1,0,1")
        else:
            self._send("AT+INVOKE=1,0,1")

        if not self.online and time.ticks_diff(now, self.last_no_rx_warning) > 5000:
            print(
                "[VISION WARN] no UART reply: check power/GND, "
                "Vision TX->GPIO1, Vision RX<-GPIO0"
            )
            self.last_no_rx_warning = now


class EyeFollower:
    """
    Visual follower for a camera mounted inside the eye.

    X: face direction -> EYL + EYR, base YAW takes over beyond the eye limit
    Y: face direction -> PIT

    The class name stays EyeFollower for app.py compatibility.
    """

    def __init__(self, servos):
        self.servos = servos
        self.vision = GroveVisionAI()

        now = time.ticks_ms()

        self.last_frame_id = -1
        self.last_target_at = now
        self.last_control_at = now
        self.last_log_at = now
        self.last_history_at = now

        self.has_target = False
        self.target_capture_ms = now

        self.filter_x = OneEuroFilter(X_MIN_CUTOFF_HZ, X_BETA, DERIVATIVE_CUTOFF_HZ)
        self.filter_y = OneEuroFilter(Y_MIN_CUTOFF_HZ, Y_BETA, DERIVATIVE_CUTOFF_HZ)

        # Face direction estimates (degrees, image-axis sign convention):
        #   x: in the head frame (eye gaze offset + base offset)
        #   y: in the body frame (pitch offset)
        self.face_x = 0.0
        self.face_y = 0.0
        self.raw_err_x = 0.0
        self.raw_err_y = 0.0

        # Current commands as offsets from centre (image-axis sign convention)
        self.gaze_cmd = 0.0
        self.pitch_cmd = 0.0
        self.base_command = BASE_YAW_CENTER
        self.base_handoff_active = False
        self.tracking_enabled_prev = True
        self.pitch_tuning_applied = False
        self.pitch_default_speed = servos["PIT"].max_speed
        self.pitch_default_accel = servos["PIT"].max_accel

        # Ring buffer of (t_ms, gaze_offset, pitch_offset, base_offset)
        self.history = [None] * HISTORY_LENGTH
        self.history_index = 0
        self.history_count = 0
        self._record_history(now)

        print("")
        print("========== Visual follower R18 (camera in eye) ==========")
        print("deg/px X={} Y={}".format(X_SERVO_DEG_PER_PX, Y_SERVO_DEG_PER_PX))
        print("eye range L={}..{} R={}..{}".format(
            LEFT_EYE_MIN, LEFT_EYE_MAX, RIGHT_EYE_MIN, RIGHT_EYE_MAX))
        print("PIT center/range: {} / {}..{}".format(PITCH_CENTER, PITCH_MIN, PITCH_MAX))
        print("base yaw center/range: {} / {}..{} (handoff beyond eye limit)".format(
            BASE_YAW_CENTER, BASE_YAW_MIN, BASE_YAW_MAX))
        print("=========================================================")

    # ------------------------------------------------------------ geometry
    def _gaze_offset(self):
        left = (self.servos["EYL"].pos - LEFT_EYE_CENTER) * LEFT_EYE_DIRECTION
        right = (self.servos["EYR"].pos - RIGHT_EYE_CENTER) * RIGHT_EYE_DIRECTION
        return 0.5 * (left + right)

    def _pitch_offset(self):
        return (self.servos["PIT"].pos - PITCH_CENTER) * PITCH_DIRECTION

    def _base_offset(self):
        return ((self.servos["YAW"].pos - BASE_YAW_CENTER) * BASE_YAW_DIRECTION
                * BASE_TO_GAZE_RATIO)

    @staticmethod
    def _gaze_limits():
        # Soft limits of both eyes expressed as a common gaze offset range.
        def offsets(center, low, high, direction):
            a = (low - center) * direction
            b = (high - center) * direction
            return (a, b) if a < b else (b, a)
        l_lo, l_hi = offsets(LEFT_EYE_CENTER, LEFT_EYE_MIN, LEFT_EYE_MAX, LEFT_EYE_DIRECTION)
        r_lo, r_hi = offsets(RIGHT_EYE_CENTER, RIGHT_EYE_MIN, RIGHT_EYE_MAX, RIGHT_EYE_DIRECTION)
        return max(l_lo, r_lo), min(l_hi, r_hi)

    @staticmethod
    def _pitch_limits():
        a = (PITCH_MIN - PITCH_CENTER) * PITCH_DIRECTION
        b = (PITCH_MAX - PITCH_CENTER) * PITCH_DIRECTION
        return (a, b) if a < b else (b, a)

    def _record_history(self, now):
        self.history[self.history_index] = (
            now, self._gaze_offset(), self._pitch_offset(), self._base_offset())
        self.history_index = (self.history_index + 1) % HISTORY_LENGTH
        if self.history_count < HISTORY_LENGTH:
            self.history_count += 1
        self.last_history_at = now

    def _history_at(self, t_ms):
        """Servo offsets at time t_ms (linear interpolation, clamped)."""
        newest = (self.history_index - 1) % HISTORY_LENGTH
        after = self.history[newest]
        if time.ticks_diff(t_ms, after[0]) >= 0:
            return after
        for i in range(1, self.history_count):
            entry = self.history[(newest - i) % HISTORY_LENGTH]
            if time.ticks_diff(t_ms, entry[0]) >= 0:
                span = time.ticks_diff(after[0], entry[0])
                if span <= 0:
                    return entry
                f = time.ticks_diff(t_ms, entry[0]) / span
                return (
                    t_ms,
                    entry[1] + (after[1] - entry[1]) * f,
                    entry[2] + (after[2] - entry[2]) * f,
                    entry[3] + (after[3] - entry[3]) * f,
                )
            after = entry
        return after  # older than the history: use the oldest sample

    # ------------------------------------------------------------ commands
    def _apply_gaze(self, gaze):
        self.gaze_cmd = gaze
        left = clamp(LEFT_EYE_CENTER + gaze * LEFT_EYE_DIRECTION, LEFT_EYE_MIN, LEFT_EYE_MAX)
        right = clamp(RIGHT_EYE_CENTER + gaze * RIGHT_EYE_DIRECTION, RIGHT_EYE_MIN, RIGHT_EYE_MAX)
        self.servos["EYL"].set_target(left)
        self.servos["EYR"].set_target(right)

    def _apply_pitch(self, pitch):
        self.pitch_cmd = pitch
        self.servos["PIT"].set_target(
            clamp(PITCH_CENTER + pitch * PITCH_DIRECTION, PITCH_MIN, PITCH_MAX))

    def _set_pitch_tuning(self, active):
        servo = self.servos["PIT"]
        if active:
            servo.max_speed = PITCH_TRACK_MAX_SPEED
            servo.max_accel = PITCH_TRACK_MAX_ACCEL
            self.pitch_tuning_applied = True
        elif self.pitch_tuning_applied:
            servo.max_speed = self.pitch_default_speed
            servo.max_accel = self.pitch_default_accel
            self.pitch_tuning_applied = False

    def release_to_home(self):
        """
        Release only the Facetrack-owned eye/pitch servos to neutral.
        Other servos (and the base) are intentionally untouched.
        """
        self.gaze_cmd = 0.0
        self.pitch_cmd = 0.0
        self.servos["EYL"].set_immediate(LEFT_EYE_CENTER)
        self.servos["EYR"].set_immediate(RIGHT_EYE_CENTER)
        self.servos["PIT"].set_immediate(PITCH_CENTER)
        self._set_pitch_tuning(False)
        self.has_target = False
        self.filter_x.ready = False
        self.filter_y.ready = False
        self.last_frame_id = self.vision.frame_id

    # ------------------------------------------------------------ frames
    def _accept_new_frame(self, now):
        if self.vision.frame_id == self.last_frame_id:
            return
        self.last_frame_id = self.vision.frame_id

        best = self.vision.get_best_box()
        if best is None:
            return
        try:
            x = float(best[0])
            y = float(best[1])
        except (TypeError, ValueError):
            return
        if x < 0 or x > FRAME_WIDTH or y < 0 or y > FRAME_HEIGHT:
            return

        capture_ms = self.vision.last_capture_ms
        _, gaze_at, pitch_at, base_at = self._history_at(capture_ms)

        err_x = x - FRAME_CENTER_X
        err_y = y - FRAME_CENTER_Y
        self.raw_err_x = err_x
        self.raw_err_y = err_y
        if abs(err_x) <= X_DEADZONE_PX:
            err_x = 0.0
        if abs(err_y) <= Y_DEADZONE_PX:
            err_y = 0.0

        # Face direction where the camera was pointing at capture time.
        meas_x = gaze_at + base_at + CORRECTION_GAIN * err_x * X_SERVO_DEG_PER_PX
        meas_y = pitch_at + CORRECTION_GAIN * err_y * Y_SERVO_DEG_PER_PX

        t_s = capture_ms / 1000.0
        reacquired = (not self.has_target or
                      time.ticks_diff(now, self.last_target_at) > TARGET_LOST_MS)
        if reacquired:
            self.filter_x.reset(meas_x, t_s)
            self.filter_y.reset(meas_y, t_s)
            self.face_x = meas_x
            self.face_y = meas_y
        else:
            self.face_x = self.filter_x.update(meas_x, t_s)
            self.face_y = self.filter_y.update(meas_y, t_s)

        self.target_capture_ms = capture_ms
        self.last_target_at = now
        self.has_target = True

    def _predicted(self, value, flt, now):
        if PREDICTION_GAIN <= 0:
            return value
        lead_s = time.ticks_diff(now, self.target_capture_ms) / 1000.0
        if lead_s < 0:
            lead_s = 0.0
        if lead_s > 0.25:
            lead_s = 0.25
        speed = flt.dx
        if speed > PREDICTION_MIN_SPEED_DEG_S:
            speed -= PREDICTION_MIN_SPEED_DEG_S
        elif speed < -PREDICTION_MIN_SPEED_DEG_S:
            speed += PREDICTION_MIN_SPEED_DEG_S
        else:
            return value
        lead = clamp(speed * lead_s * PREDICTION_GAIN, -PREDICTION_MAX_DEG, PREDICTION_MAX_DEG)
        return value + lead

    # ------------------------------------------------------------ update
    def update(self, now, state_name, enabled=True):
        enabled = bool(enabled)

        # GP21 logical enable reaches the Vision driver: OFF stops inference
        # while UART is still serviced so a pending reply cannot wedge it.
        self.vision.set_enabled(enabled, now)
        self.vision.update(now)

        if time.ticks_diff(now, self.last_history_at) >= HISTORY_INTERVAL_MS:
            self._record_history(now)

        if enabled != self.tracking_enabled_prev:
            self.tracking_enabled_prev = enabled
            self.has_target = False
            self.filter_x.ready = False
            self.filter_y.ready = False
            self.last_frame_id = self.vision.frame_id
            if not enabled:
                self._set_pitch_tuning(False)

        if not enabled:
            return

        self._accept_new_frame(now)

        if state_name not in ACTIVE_STATES:
            self._set_pitch_tuning(False)
            return

        pitch_tracking_active = state_name in PITCH_TRACKING_STATES
        self._set_pitch_tuning(pitch_tracking_active)

        dt = time.ticks_diff(now, self.last_control_at) / 1000.0
        self.last_control_at = now
        if dt < 0 or dt > 0.1:
            dt = 0.0

        target_fresh = (self.has_target and
                        time.ticks_diff(now, self.last_target_at) <= TARGET_LOST_MS)

        gaze_lo, gaze_hi = self._gaze_limits()

        if target_fresh:
            # ---------------------------------------------- X: eyes + base
            wanted_head = self._predicted(self.face_x, self.filter_x, now)
            base_now = self._base_offset()
            wanted_gaze = wanted_head - base_now
            gaze = clamp(wanted_gaze, gaze_lo, gaze_hi)
            self._apply_gaze(gaze)

            # Base handoff: excess of the wanted gaze beyond the comfort zone.
            comfort_lo = gaze_lo + BASE_COMFORT_MARGIN_DEG
            comfort_hi = gaze_hi - BASE_COMFORT_MARGIN_DEG
            if wanted_gaze > comfort_hi:
                excess = wanted_gaze - comfort_hi
            elif wanted_gaze < comfort_lo:
                excess = wanted_gaze - comfort_lo
            else:
                excess = 0.0
            self.base_handoff_active = abs(excess) > BASE_HANDOFF_DEADBAND_DEG
            if self.base_handoff_active and dt > 0:
                speed = clamp(excess * BASE_HANDOFF_GAIN,
                              -BASE_MAX_SPEED_DEG_S, BASE_MAX_SPEED_DEG_S)
                step = speed * dt / BASE_TO_GAZE_RATIO
                self.base_command = clamp(
                    self.base_command + BASE_YAW_DIRECTION * step,
                    BASE_YAW_MIN, BASE_YAW_MAX)

            # ---------------------------------------------- Y: pitch
            if pitch_tracking_active:
                pitch_lo, pitch_hi = self._pitch_limits()
                wanted_pitch = self._predicted(self.face_y, self.filter_y, now)
                self._apply_pitch(clamp(wanted_pitch, pitch_lo, pitch_hi))
        else:
            # Face lost: glide eyes (and pitch) back to centre; base holds.
            step = RETURN_SPEED_DEG_S * dt
            self._apply_gaze(move_towards(self.gaze_cmd, 0.0, step))
            if pitch_tracking_active:
                self._apply_pitch(move_towards(self.pitch_cmd, 0.0, step))
            self.base_handoff_active = False

        # The base is Facetrack-owned while tracking is active.
        self.servos["YAW"].set_target(self.base_command)

        if time.ticks_diff(now, self.last_log_at) >= CONTROL_LOG_EVERY_MS:
            fps, latency = self.vision.take_stats(now)
            print(
                "[TRACK] fps={:.1f} lat={:.0f}ms {} | errX={:.0f}px errY={:.0f}px | "
                "face X={:.1f} Y={:.1f} | gaze={:.1f} PIT={:.1f} YAW={:.1f}{}".format(
                    fps, latency,
                    "stream" if self.vision.streaming else "single",
                    self.raw_err_x, self.raw_err_y,
                    self.face_x, self.face_y,
                    self.gaze_cmd, self.servos["PIT"].target, self.base_command,
                    " HANDOFF" if self.base_handoff_active else "",
                )
            )
            self.last_log_at = now
