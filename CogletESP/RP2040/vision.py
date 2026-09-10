
        # ==========================================================
        # Y -> neck pitch
        # ==========================================================
# Grove Vision AI V2 -> eyes-only visual follower
# MicroPython / RP2040 / Coglet PCB V2.0
#
# PCB wiring:
#   RP2040 GPIO0 / UART0 TX -> Grove Vision AI V2 RX
#   RP2040 GPIO1 / UART0 RX <- Grove Vision AI V2 TX
#
# Grove Vision AI V2 default UART:
#   921600 baud, 8N1
#
# V2 visual-follow mapping:
#   X -> EYR / EYL  (right + left eyeballs)
#   Y -> PIT        (neck pitch)
#
# Facetrack intentionally owns ONLY these three servos.
# It does NOT control YAW/base, neck left-right, eyelid, ears, or mouth.
#
# SSCMA detection box format observed in the existing project:
#   [x, y, w, h, score, target]
# where x/y are treated as target-center coordinates in the 240x240 image.

from machine import Pin, UART
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

# Both eyes currently use 90 deg as their neutral command.
LEFT_EYE_CENTER = 90.0
RIGHT_EYE_CENTER = 90.0

# Current eye visual-follow range.
# animation.py hard limit is currently 5..150 deg;
# keep 2 deg of software margin here.
LEFT_EYE_MIN = 60.0
LEFT_EYE_MAX = 130.0
RIGHT_EYE_MIN = 60.0
RIGHT_EYE_MAX = 130.0

# The original V1 animation moved both eye servos with the same numeric angle.
# Therefore both directions start at +1.
#
# If the eyes move opposite to the detected target, change BOTH to -1.
# If only one eye is reversed, change only that eye.
LEFT_EYE_DIRECTION = 1.0
RIGHT_EYE_DIRECTION = 1.0

# ==============================================================
# Neck pitch visual-follow tuning
#
# Current animation.py PIT hard limit in this project is 1..80 deg.
# Start with a conservative visual-follow range and tune mechanically.
#
# IMPORTANT:
# If the head pitches the wrong way when the target moves vertically,
# change PITCH_DIRECTION from +1.0 to -1.0.
# ==============================================================
PITCH_CENTER = 50.0
PITCH_MIN = 3.0
PITCH_MAX = 78.0
PITCH_DIRECTION = 1.0

# ==============================================================
# Base/body yaw handoff tuning
#
# animation.py YAW hard/software limit is 10..170 deg.
# R16 keeps a small safety margin at 15..165 deg.
#
# The base moves incrementally only while the requested eye position
# is beyond the eye visual soft limit. Once the eyes are back inside
# their range, the base HOLDS its new angle.
# ==============================================================
BASE_YAW_CENTER = 90.0
BASE_YAW_MIN = 30.0
BASE_YAW_MAX = 150.0
BASE_YAW_DIRECTION = 1.0

# Require this much eye-command overflow before handing motion to base.
BASE_HANDOFF_HYSTERESIS_DEG = 3.0

# Maximum incremental base command change per control update.
BASE_MAX_COMMAND_STEP_DEG = 1.0

# Pixels around image center that produce no eye motion.
X_DEADZONE_PX = 8.0

# Horizontal proportional gain.
EYE_GAIN_DEG_PER_PX = 0.75

# ==============================================================
# R14 anti-jitter / anti-shake tuning
#
# Why the old version can still shake:
#   - dead-zone only exists around CAMERA CENTER
#   - EMA smooths x, but still follows every tiny detector fluctuation
#   - slew limiting slows the chasing, but does not stop the chasing
#
# R14 adds three layers:
#   1) 5-frame median filter: rejects one-frame box jumps
#   2) adaptive EMA: responsive while target moves, heavy smoothing when stable
#   3) command hysteresis: tiny desired-angle changes are ignored completely
# ==============================================================

# Number of recent detector x samples used by the median filter.
X_MEDIAN_WINDOW = 5

# Adaptive EMA:
# small detector movement -> strong smoothing
# large detector movement -> fast response
TARGET_X_ALPHA_STABLE = 0.10
TARGET_X_ALPHA_MOVING = 0.50
TARGET_X_MOVING_THRESHOLD_PX = 14.0

# If the desired eye command changes less than this, do not update it.
# This is the most important "settle down and stay still" threshold.
EYE_COMMAND_HYSTERESIS_DEG = 3.0

# ==============================================================
# R15 Y-axis anti-jitter / neck-pitch tuning
#
# Neck is heavier than the eyeballs, so Y is deliberately more stable
# and a little slower than X.
# ==============================================================
Y_DEADZONE_PX = 12.0
PITCH_GAIN_DEG_PER_PX = 0.55

Y_MEDIAN_WINDOW = 5
TARGET_Y_ALPHA_STABLE = 0.08
TARGET_Y_ALPHA_MOVING = 0.35
TARGET_Y_MOVING_THRESHOLD_PX = 16.0

PITCH_COMMAND_HYSTERESIS_DEG = 4.0
PITCH_MAX_COMMAND_STEP_DEG = 1.5

# Limit how much the commanded eye angle can change per control update.
# This is separate from Servo.update(dt), which still performs smooth motion.
MAX_COMMAND_STEP_DEG = 2.5

# Eye-control update interval. Inference may arrive at another rate.
CONTROL_INTERVAL_MS = 25

# If target disappears for this long, slowly return both eyes to center.
TARGET_LOST_MS = 650

# After startup diagnostics, invoke inference continuously.
INVOKE_GAP_MS = 25

# Sparse serial logging to avoid slowing the control loop.
FRAME_LOG_EVERY = 30
CONTROL_LOG_EVERY_MS = 1000

# Do not override special animations/calibration-like modes yet.
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


class GroveVisionAI:
    """
    Minimal non-blocking SSCMA UART driver.

    Startup:
      AT+ID?
      AT+VER?
      AT+STAT?
      AT+MODEL?
      AT+SENSOR?

    Runtime:
      AT+INVOKE=1,0,1

    The driver stores:
      frame_id
      last_boxes
      last_frame_at
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

        now = time.ticks_ms()
        self.next_action_at = time.ticks_add(now, 1800)
        self.last_no_rx_warning = now

        self.online = False
        self.frames = 0
        self.frame_id = 0
        self.last_boxes = []
        self.last_frame_at = now

        # Logical Grove Vision run control.  There is no dedicated hardware
        # power-enable pin in this RP2040 firmware, so OFF means:
        #   - keep UART alive/drain pending replies
        #   - stop issuing new startup/inference commands
        #   - do not let Vision write servo targets
        self.run_enabled = True

        print("")
        print("========== Grove Vision AI V2 ==========")
        print("UART0 TX=GPIO0 -> Vision RX")
        print("UART0 RX=GPIO1 <- Vision TX")
        print("921600 baud, 8N1")
        print("V2 mode: X->EYES, Y->PITCH only; YAW/base not controlled")
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
        Return the SSCMA response name for an AT command.

        Important:
        Query responses from Grove Vision AI V2 preserve the '?' suffix:
            AT+ID?      -> name == "ID?"
            AT+VER?     -> name == "VER?"
            AT+STAT?    -> name == "STAT?"
            AT+MODEL?   -> name == "MODEL?"
            AT+SENSOR?  -> name == "SENSOR?"

        Set/invoke commands still match by the name before '=':
            AT+INVOKE=1,0,1 -> name == "INVOKE"
        """
        body = command[3:] if command.startswith("AT+") else command

        if "=" in body:
            return body.split("=", 1)[0]

        return body

    def _send(self, command):
        self.uart.write((command + "\r").encode())

        self.waiting_command = command
        self.waiting_since = time.ticks_ms()

        if not command.startswith("AT+INVOKE"):
            print("[VISION TX]", command)

    def _read_uart(self):
        if not self.uart.any():
            return

        chunk = self.uart.read()
        if not chunk:
            return

        self.online = True
        self.rx_buffer += chunk

        if len(self.rx_buffer) > self.max_buffer:
            self.rx_buffer = self.rx_buffer[-self.max_buffer:]

        while b"\n" in self.rx_buffer:
            line, self.rx_buffer = self.rx_buffer.split(b"\n", 1)
            line = line.strip()

            if line:
                self._handle_line(line)

    def _handle_line(self, line):
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
            self._handle_event(name, code, data)

    def _handle_operation(self, name, code, data):
        if name != "INVOKE":
            print(
                "[VISION RX] {} code={} data={}".format(
                    name,
                    code,
                    data,
                )
            )

        if self.waiting_command is None:
            return

        expected = self._expected_name(self.waiting_command)

        if name != expected:
            return

        command = self.waiting_command
        self.waiting_command = None

        if not command.startswith("AT+INVOKE"):
            print("[VISION OK]", command)

        if command.startswith("AT+INVOKE"):
            if code == 0:
                self.invoke_pending = True
                self.invoke_since = time.ticks_ms()
            else:
                self.invoke_pending = False
                self.next_action_at = time.ticks_add(
                    time.ticks_ms(),
                    500,
                )
            return

        if self.query_index < len(self.boot_queries):
            self.query_index += 1

        self.next_action_at = time.ticks_add(
            time.ticks_ms(),
            120,
        )

    def _handle_event(self, name, code, data):
        if name != "INVOKE":
            return

        self.invoke_pending = False
        self.frames += 1
        self.frame_id += 1
        self.last_frame_at = time.ticks_ms()
        self.next_action_at = time.ticks_add(
            self.last_frame_at,
            INVOKE_GAP_MS,
        )

        if code != 0 or not isinstance(data, dict):
            self.last_boxes = []
            return

        boxes = data.get("boxes", [])
        self.last_boxes = boxes if isinstance(boxes, list) else []

        if self.frames % FRAME_LOG_EVERY != 0:
            return

        best = self.get_best_box()

        if best is None:
            print("[VISION FRAME {}] no target".format(self.frames))
            return

        print(
            "[VISION FRAME {}] target={} score={} x={} y={}".format(
                self.frames,
                best[5],
                best[4],
                best[0],
                best[1],
            )
        )

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

    def set_enabled(self, enabled, now=None):
        enabled = bool(enabled)

        if now is None:
            now = time.ticks_ms()

        if enabled == self.run_enabled:
            return

        self.run_enabled = enabled
        self.last_boxes = []

        if enabled:
            # Resume immediately.  If startup queries were never completed,
            # update() continues from query_index; otherwise inference resumes.
            self.next_action_at = now
            print("[VISION] ENABLED: startup/inference requests resumed")
        else:
            # Do not tear down UART or power.  Any already-sent command/event
            # may still arrive and is drained by update(), but no new command
            # is issued until the switch is turned back ON.
            print("[VISION] DISABLED: no new AT queries / AT+INVOKE requests")

    def update(self, now=None):
        if now is None:
            now = time.ticks_ms()

        self._read_uart()

        # Recover from a lost command response.
        if self.waiting_command is not None:
            if (
                time.ticks_diff(
                    now,
                    self.waiting_since,
                )
                > 1800
            ):
                print("[VISION TIMEOUT]", self.waiting_command)
                self.waiting_command = None
                self.next_action_at = time.ticks_add(now, 350)

            return

        # INVOKE returns an operation response followed by an event.
        if self.invoke_pending:
            if (
                time.ticks_diff(
                    now,
                    self.invoke_since,
                )
                > 3000
            ):
                print("[VISION TIMEOUT] INVOKE event")
                self.invoke_pending = False
                self.next_action_at = time.ticks_add(now, 500)

            return

        # OFF is a logical pause: finish/drain anything already in flight,
        # then stop generating new Vision traffic.
        if not self.run_enabled:
            return

        if time.ticks_diff(now, self.next_action_at) < 0:
            return

        if self.query_index < len(self.boot_queries):
            self._send(
                self.boot_queries[self.query_index]
            )
            return

        self._send("AT+INVOKE=1,0,1")

        if (
            not self.online
            and time.ticks_diff(
                now,
                self.last_no_rx_warning,
            )
            > 5000
        ):
            print(
                "[VISION WARN] no UART reply: check power/GND, "
                "Vision TX->GPIO1, Vision RX<-GPIO0"
            )
            self.last_no_rx_warning = now


class EyeFollower:
    """
    V2 visual follower.

    X image error -> EYL + EYR
    Y image error -> PIT neck pitch

    Facetrack deliberately owns only these three axes.  YAW/base is left
    entirely to XiaoZhi animations / other firmware behavior.

    The class name stays EyeFollower for main.py compatibility.
    """

    def __init__(self, servos):
        self.servos = servos
        self.vision = GroveVisionAI()

        now = time.ticks_ms()

        self.last_frame_id = -1
        self.last_target_at = now
        self.last_control_at = now
        self.last_log_at = now

        self.raw_x = FRAME_CENTER_X
        self.median_x = FRAME_CENTER_X
        self.filtered_x = FRAME_CENTER_X

        self.raw_y = FRAME_CENTER_Y
        self.median_y = FRAME_CENTER_Y
        self.filtered_y = FRAME_CENTER_Y

        self.filter_ready = False
        self.has_target = False

        # Small rolling histories for median filtering.
        self.x_history = []
        self.y_history = []

        self.left_command = LEFT_EYE_CENTER
        self.right_command = RIGHT_EYE_CENTER
        self.pitch_command = PITCH_CENTER
        # Legacy base variables are kept only for compatibility with older
        # tuning code/log readers; V2 Facetrack no longer writes YAW.
        self.base_command = BASE_YAW_CENTER
        self.base_handoff_active = False
        self.tracking_enabled_prev = True

        print("")
        print("========== Visual follower R17 =============")
        print("EYL center:", LEFT_EYE_CENTER)
        print("EYR center:", RIGHT_EYE_CENTER)
        print(
            "eye range L={}..{} R={}..{}".format(
                LEFT_EYE_MIN,
                LEFT_EYE_MAX,
                RIGHT_EYE_MIN,
                RIGHT_EYE_MAX,
            )
        )
        print(
            "PIT center/range: {} / {}..{}".format(
                PITCH_CENTER,
                PITCH_MIN,
                PITCH_MAX,
            )
        )
        print("vertical tracking: ENABLED -> PIT")
        print(
            "base yaw center/range: {} / {}..{}".format(
                BASE_YAW_CENTER,
                BASE_YAW_MIN,
                BASE_YAW_MAX,
            )
        )
        print("X overflow handoff: DISABLED (YAW/base untouched)")
        print("neck left/right tracking: DISABLED")
        print("============================================")

    def _set_eye_targets(self, left, right):
        self.left_command = clamp(
            left,
            LEFT_EYE_MIN,
            LEFT_EYE_MAX,
        )
        self.right_command = clamp(
            right,
            RIGHT_EYE_MIN,
            RIGHT_EYE_MAX,
        )

        self.servos["EYL"].set_target(
            self.left_command
        )
        self.servos["EYR"].set_target(
            self.right_command
        )

    def _set_pitch_target(self, angle):
        self.pitch_command = clamp(
            angle,
            PITCH_MIN,
            PITCH_MAX,
        )

        self.servos["PIT"].set_target(
            self.pitch_command
        )

    def _set_base_target(self, angle):
        self.base_command = clamp(
            angle,
            BASE_YAW_MIN,
            BASE_YAW_MAX,
        )

    def _return_center(self, include_pitch=True):
        self.left_command = move_towards(
            self.left_command,
            LEFT_EYE_CENTER,
            MAX_COMMAND_STEP_DEG,
        )
        self.right_command = move_towards(
            self.right_command,
            RIGHT_EYE_CENTER,
            MAX_COMMAND_STEP_DEG,
        )

        if include_pitch:
            self.pitch_command = move_towards(
                self.pitch_command,
                PITCH_CENTER,
                PITCH_MAX_COMMAND_STEP_DEG,
            )

        self._set_eye_targets(
            self.left_command,
            self.right_command,
        )

        if include_pitch:
            self._set_pitch_target(
                self.pitch_command
            )

    def release_to_home(self):
        """
        Release only the three Facetrack-owned servos to their neutral
        positions.  Other servos are intentionally untouched.
        """
        self.left_command = LEFT_EYE_CENTER
        self.right_command = RIGHT_EYE_CENTER
        self.pitch_command = PITCH_CENTER

        self.servos["EYL"].set_immediate(LEFT_EYE_CENTER)
        self.servos["EYR"].set_immediate(RIGHT_EYE_CENTER)
        self.servos["PIT"].set_immediate(PITCH_CENTER)

        self.has_target = False
        self.filter_ready = False
        self.x_history = []
        self.y_history = []
        self.last_frame_id = self.vision.frame_id

    def _accept_new_frame(self, now):
        if self.vision.frame_id == self.last_frame_id:
            return

        self.last_frame_id = self.vision.frame_id

        best = self.vision.get_best_box()

        if best is None:
            return

        x = float(best[0])
        y = float(best[1])

        # Guard against malformed detections.
        if x < 0 or x > FRAME_WIDTH:
            return
        if y < 0 or y > FRAME_HEIGHT:
            return

        self.raw_x = x
        self.raw_y = y

        # ----------------------------------------------------------
        # Layer 1: rolling median filters for both X and Y.
        # ----------------------------------------------------------
        self.x_history.append(x)
        self.y_history.append(y)

        if len(self.x_history) > X_MEDIAN_WINDOW:
            self.x_history.pop(0)
        if len(self.y_history) > Y_MEDIAN_WINDOW:
            self.y_history.pop(0)

        sorted_x = sorted(self.x_history)
        middle_x = len(sorted_x) // 2

        if len(sorted_x) % 2:
            median_x = sorted_x[middle_x]
        else:
            median_x = (
                sorted_x[middle_x - 1]
                + sorted_x[middle_x]
            ) / 2.0

        sorted_y = sorted(self.y_history)
        middle_y = len(sorted_y) // 2

        if len(sorted_y) % 2:
            median_y = sorted_y[middle_y]
        else:
            median_y = (
                sorted_y[middle_y - 1]
                + sorted_y[middle_y]
            ) / 2.0

        self.median_x = median_x
        self.median_y = median_y

        # ----------------------------------------------------------
        # Layer 2: independent adaptive EMA filters.
        #
        # X is a little more responsive.
        # Y is deliberately more stable because PIT moves the whole head.
        # ----------------------------------------------------------
        if not self.filter_ready:
            self.filtered_x = median_x
            self.filtered_y = median_y
            self.filter_ready = True
        else:
            x_delta = abs(
                median_x - self.filtered_x
            )
            y_delta = abs(
                median_y - self.filtered_y
            )

            if x_delta >= TARGET_X_MOVING_THRESHOLD_PX:
                alpha_x = TARGET_X_ALPHA_MOVING
            else:
                alpha_x = TARGET_X_ALPHA_STABLE

            if y_delta >= TARGET_Y_MOVING_THRESHOLD_PX:
                alpha_y = TARGET_Y_ALPHA_MOVING
            else:
                alpha_y = TARGET_Y_ALPHA_STABLE

            self.filtered_x = (
                alpha_x * median_x
                + (1.0 - alpha_x) * self.filtered_x
            )
            self.filtered_y = (
                alpha_y * median_y
                + (1.0 - alpha_y) * self.filtered_y
            )

        self.last_target_at = now
        self.has_target = True

    def update(
        self,
        now,
        state_name,
        enabled=True,
    ):
        enabled = bool(enabled)

        # GP21 logical enable reaches all the way down to the Vision driver:
        # OFF pauses new AT/startup/inference requests, while UART is still
        # serviced so an already-pending reply cannot wedge the parser.
        self.vision.set_enabled(enabled, now)
        self.vision.update(now)

        if enabled != self.tracking_enabled_prev:
            self.tracking_enabled_prev = enabled

            if enabled:
                # Do not jump toward a stale detection collected before OFF.
                self.has_target = False
                self.filter_ready = False
                self.x_history = []
                self.y_history = []
                self.last_frame_id = self.vision.frame_id
            else:
                self.has_target = False
                self.last_frame_id = self.vision.frame_id

        if not enabled:
            return

        self._accept_new_frame(now)

        active = state_name in ACTIVE_STATES

        if not active:
            return

        pitch_tracking_active = (
            state_name in PITCH_TRACKING_STATES
        )

        # Re-assert vision-owned axes every loop.
        # SAD deliberately owns PIT, so vision leaves PIT alone there.
        if pitch_tracking_active:
            self.servos["PIT"].set_target(
                self.pitch_command
            )

        self.servos["YAW"].set_target(
            self.base_command
        )

        if (
            time.ticks_diff(
                now,
                self.last_control_at,
            )
            < CONTROL_INTERVAL_MS
        ):
            return

        self.last_control_at = now

        target_is_fresh = (
            self.has_target
            and time.ticks_diff(
                now,
                self.last_target_at,
            )
            <= TARGET_LOST_MS
        )

        if not target_is_fresh:
            self._return_center(
                include_pitch=pitch_tracking_active
            )
            return

        # ==========================================================
        # X -> eyes
        # ==========================================================
        error_x = self.filtered_x - FRAME_CENTER_X

        if abs(error_x) <= X_DEADZONE_PX:
            desired_eye_offset = 0.0
        else:
            if error_x > 0:
                effective_x = error_x - X_DEADZONE_PX
            else:
                effective_x = error_x + X_DEADZONE_PX

            desired_eye_offset = (
                effective_x
                * EYE_GAIN_DEG_PER_PX
            )

        desired_left_unclamped = (
            LEFT_EYE_CENTER
            + LEFT_EYE_DIRECTION * desired_eye_offset
        )
        desired_right_unclamped = (
            RIGHT_EYE_CENTER
            + RIGHT_EYE_DIRECTION * desired_eye_offset
        )

        desired_left = clamp(
            desired_left_unclamped,
            LEFT_EYE_MIN,
            LEFT_EYE_MAX,
        )
        desired_right = clamp(
            desired_right_unclamped,
            RIGHT_EYE_MIN,
            RIGHT_EYE_MAX,
        )

        left_delta = abs(
            desired_left - self.left_command
        )
        right_delta = abs(
            desired_right - self.right_command
        )

        if (
            left_delta >= EYE_COMMAND_HYSTERESIS_DEG
            or right_delta >= EYE_COMMAND_HYSTERESIS_DEG
        ):
            next_left = move_towards(
                self.left_command,
                desired_left,
                MAX_COMMAND_STEP_DEG,
            )
            next_right = move_towards(
                self.right_command,
                desired_right,
                MAX_COMMAND_STEP_DEG,
            )

            self._set_eye_targets(
                next_left,
                next_right,
            )

        # ==========================================================
        # X overflow -> base/body YAW
        #
        # Incremental handoff avoids hunting:
        # eyes hit edge -> base follows -> camera recenters target
        # -> eyes come off edge -> base stops and holds.
        # ==========================================================
        left_overflow = 0.0
        right_overflow = 0.0

        if desired_left_unclamped > LEFT_EYE_MAX:
            left_overflow = desired_left_unclamped - LEFT_EYE_MAX
        elif desired_left_unclamped < LEFT_EYE_MIN:
            left_overflow = desired_left_unclamped - LEFT_EYE_MIN

        if desired_right_unclamped > RIGHT_EYE_MAX:
            right_overflow = desired_right_unclamped - RIGHT_EYE_MAX
        elif desired_right_unclamped < RIGHT_EYE_MIN:
            right_overflow = desired_right_unclamped - RIGHT_EYE_MIN

        eye_overflow = left_overflow
        if abs(right_overflow) > abs(eye_overflow):
            eye_overflow = right_overflow

        self.base_handoff_active = (
            abs(eye_overflow) >= BASE_HANDOFF_HYSTERESIS_DEG
        )

        if self.base_handoff_active:
            # Use image-X direction, independent of mirrored eye mechanics.
            if error_x > 0:
                base_step = (
                    BASE_YAW_DIRECTION * BASE_MAX_COMMAND_STEP_DEG
                )
            else:
                base_step = (
                    -BASE_YAW_DIRECTION * BASE_MAX_COMMAND_STEP_DEG
                )

            self._set_base_target(
                self.base_command + base_step
            )

        # ==========================================================
        # Y -> neck pitch
        # ==========================================================
        if pitch_tracking_active:
            error_y = self.filtered_y - FRAME_CENTER_Y

            if abs(error_y) <= Y_DEADZONE_PX:
                desired_pitch_offset = 0.0
            else:
                if error_y > 0:
                    effective_y = error_y - Y_DEADZONE_PX
                else:
                    effective_y = error_y + Y_DEADZONE_PX

                desired_pitch_offset = (
                    effective_y
                    * PITCH_GAIN_DEG_PER_PX
                )

            desired_pitch = (
                PITCH_CENTER
                + PITCH_DIRECTION * desired_pitch_offset
            )

            desired_pitch = clamp(
                desired_pitch,
                PITCH_MIN,
                PITCH_MAX,
            )

            pitch_delta = abs(
                desired_pitch - self.pitch_command
            )

            if pitch_delta >= PITCH_COMMAND_HYSTERESIS_DEG:
                next_pitch = move_towards(
                    self.pitch_command,
                    desired_pitch,
                    PITCH_MAX_COMMAND_STEP_DEG,
                )

                self._set_pitch_target(
                    next_pitch
                )

        if (
            time.ticks_diff(
                now,
                self.last_log_at,
            )
            >= CONTROL_LOG_EVERY_MS
        ):
            print(
                "[TRACK] "
                "X raw={:.1f} med={:.1f} filt={:.1f} "
                "EYL={:.1f} EYR={:.1f} | "
                "Y raw={:.1f} med={:.1f} filt={:.1f} "
                "PIT={:.1f}".format(
                    self.raw_x,
                    self.median_x,
                    self.filtered_x,
                    self.left_command,
                    self.right_command,
                    self.raw_y,
                    self.median_y,
                    self.filtered_y,
                    self.pitch_command,
                )
            )
            self.last_log_at = now

