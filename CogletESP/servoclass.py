from machine import Pin, I2C
import time


def clamp(x, a, b):
    return a if x < a else (b if x > b else x)


# ============================================================
# PCB V2.0 hardware configuration - checked against CogletESPV2.0 PDF
# ============================================================

PCA_ADDR = 0x40

# RP2040 -> PCA9685
PWM_SDA_PIN = 6
PWM_SCL_PIN = 7
PWM_NOE_PIN = 8

# GPIO6/7/8 are still taken directly from the PCB 2.0 schematic.

# Physical servo connector semantics.
#
# The number printed beside each PCB servo socket is the Socket ID, and the
# Socket ID is the PCA9685 channel number.  There is intentionally no second
# remapping table here:
#
#   Socket 0  -> PCA CH0   (Right Ear / EAR)
#   Socket 1  -> PCA CH1   (Left Ear / EAL)
#   Socket 2  -> PCA CH2   (Eyelid / LID)
#   Socket 3  -> PCA CH3   (Mouth / MOU)
#   Socket 4  -> PCA CH4   (Left Eye / EYL)
#   Socket 5  -> PCA CH5   (Right Eye / EYR)
#   Socket 8  -> PCA CH8   (Neck Pitch / PIT)
#   Socket 9  -> PCA CH9   (Neck Roll / ROL)
#   Socket 10 -> PCA CH10  (Base Yaw / YAW)
#
# Sockets 6, 7 and 11 remain valid physical/PCA channels even though they are
# not assigned to one of the named servos above.
SERVO_SOCKET_MIN = 0
SERVO_SOCKET_MAX = 11


# PCA9685 nOE is active LOW.
# Keep outputs disabled while modules are importing and pulses are preloaded.
_oe = Pin(PWM_NOE_PIN, Pin.OUT)
_oe.value(1)

_i2c = I2C(
    1,
    sda=Pin(PWM_SDA_PIN),
    scl=Pin(PWM_SCL_PIN),
    freq=400000,
)


class _PCA9685:
    MODE1 = 0x00
    MODE2 = 0x01
    LED0_ON_L = 0x06
    PRESCALE = 0xFE

    def __init__(self, i2c, address=0x40):
        self.i2c = i2c
        self.address = address
        self.freq = 50.0

    def _write8(self, reg, value):
        self.i2c.writeto_mem(
            self.address,
            reg,
            bytes((value & 0xFF,))
        )

    def _read8(self, reg):
        return self.i2c.readfrom_mem(
            self.address,
            reg,
            1
        )[0]

    def set_freq(self, freq):
        self.freq = float(freq)

        prescale = int(
            25000000.0 / (4096.0 * self.freq)
            - 1.0
            + 0.5
        )

        old_mode = self._read8(self.MODE1)

        # Sleep before changing PRESCALE.
        self._write8(
            self.MODE1,
            (old_mode & 0x7F) | 0x10
        )

        self._write8(self.PRESCALE, prescale)

        # Wake.
        self._write8(
            self.MODE1,
            old_mode & ~0x10
        )

        time.sleep_ms(5)

        # RESTART + AUTO-INCREMENT + ALLCALL.
        self._write8(
            self.MODE1,
            (old_mode & ~0x10) | 0xA1
        )

        # Totem-pole output driver.
        self._write8(self.MODE2, 0x04)

    def set_pwm(self, channel, on, off):
        reg = self.LED0_ON_L + channel * 4

        data = bytes((
            on & 0xFF,
            (on >> 8) & 0x0F,
            off & 0xFF,
            (off >> 8) & 0x0F,
        ))

        self.i2c.writeto_mem(
            self.address,
            reg,
            data
        )

    def write_us(self, channel, pulse_us):
        pulse_us = clamp(
            float(pulse_us),
            500.0,
            2500.0
        )

        counts = int(
            pulse_us
            * 4096.0
            * self.freq
            / 1000000.0
            + 0.5
        )

        counts = int(clamp(counts, 0, 4095))
        self.set_pwm(channel, 0, counts)


_pca = _PCA9685(_i2c, PCA_ADDR)
_ready = False

try:
    devices = _i2c.scan()

    print(
        "[PCB2] I2C1 scan:",
        ["0x{:02X}".format(x) for x in devices]
    )

    if PCA_ADDR in devices:
        _pca.set_freq(50)
        _ready = True
        print("[PCB2] PCA9685 OK: address 0x40, 50 Hz")
    else:
        print("[PCB2] ERROR: PCA9685 0x40 NOT FOUND")

except Exception as exc:
    print("[PCB2] PCA9685 init failed:", exc)
    _ready = False


def is_ready():
    return _ready


def enable_outputs():
    if not _ready:
        print("[PCB2] Refuse enable: PCA9685 is not ready")
        return False

    # Active-low nOE.
    _oe.value(0)
    print("[PCB2] GPIO8 PWM_nOE = 0 -> servo outputs ENABLED")
    return True


def disable_outputs():
    _oe.value(1)
    print("[PCB2] GPIO8 PWM_nOE = 1 -> servo outputs DISABLED")


class Servo:
    def __init__(
        self,
        pin_num,
        max_speed=120.0,
        max_accel=360.0,
        min_angle=0.0,
        max_angle=180.0,
        enabled=True
    ):
        # pin_num is the physical PCB Socket ID printed on the board.
        # By hardware definition, Socket ID == PCA9685 channel.
        self.port_num = int(pin_num)

        if not (SERVO_SOCKET_MIN <= self.port_num <= SERVO_SOCKET_MAX):
            raise ValueError(
                "Invalid PCB servo Socket ID: {} (expected {}..{})".format(
                    self.port_num,
                    SERVO_SOCKET_MIN,
                    SERVO_SOCKET_MAX,
                )
            )

        self.channel = self.port_num

        # motion state - same as V1
        self.pos = 90.0
        self.vel = 0.0
        self.target = 90.0

        # tuning - same as V1
        self.max_speed = float(max_speed)
        self.max_accel = float(max_accel)

        # limits - same as V1
        self.min_angle = float(min_angle)
        self.max_angle = float(max_angle)

        self.pos_tolerance = 0.6
        self.vel_tolerance = 1.0

        self.enabled = enabled

        # Preload 90 degrees while nOE remains disabled.
        self._write_pwm(self.pos)

        print(
            "[PCB2] SOCKET{} -> PCA CH{}".format(
                self.port_num,
                self.channel
            )
        )

    def set_target(self, angle):
        self.target = clamp(
            float(angle),
            self.min_angle,
            self.max_angle
        )

    def set_immediate(self, angle):
        """
        Write a servo position immediately, bypassing speed/acceleration
        interpolation while keeping pos/target/vel synchronized.
        """
        angle = clamp(
            float(angle),
            self.min_angle,
            self.max_angle
        )

        self.pos = angle
        self.target = angle
        self.vel = 0.0
        self._write_pwm(angle)

    def update(self, dt):
        if not self.enabled:
            return

        if dt <= 0:
            return

        error = self.target - self.pos
        dist = abs(error)

        desired_dir = (
            0
            if dist < 1e-9
            else (1.0 if error > 0 else -1.0)
        )

        if abs(self.vel) < 1e-9:
            vel_dir = 0.0
        else:
            vel_dir = (
                1.0 if self.vel > 0 else -1.0
            )

        if (
            dist <= self.pos_tolerance
            and abs(self.vel) <= self.vel_tolerance
        ):
            self.pos = self.target
            self.vel = 0.0
            self._write_pwm(self.pos)
            return

        if (
            vel_dir != 0
            and desired_dir != 0
            and vel_dir != desired_dir
        ):
            accel = -vel_dir * self.max_accel
        else:
            stopping_dist = (
                self.vel * self.vel
            ) / (2.0 * self.max_accel)

            if dist > stopping_dist:
                accel = (
                    desired_dir
                    * self.max_accel
                )
            else:
                accel = (
                    -desired_dir
                    * self.max_accel
                )

        new_vel = self.vel + accel * dt

        if self.vel > 0 and new_vel < 0:
            new_vel = 0.0
        elif self.vel < 0 and new_vel > 0:
            new_vel = 0.0

        new_vel = clamp(
            new_vel,
            -self.max_speed,
            self.max_speed
        )

        self.vel = new_vel
        self.pos = self.pos + self.vel * dt

        self.pos = clamp(
            self.pos,
            0.0,
            180.0
        )

        self._write_pwm(self.pos)

    def _write_pwm(self, angle):
        if not _ready:
            return

        # Preserve V1 pulse mapping:
        # 0..180 degrees -> 500..2500 us
        min_us = 500.0
        max_us = 2500.0

        pulse_us = min_us + (
            max_us - min_us
        ) * (
            float(angle) / 180.0
        )

        _pca.write_us(
            self.channel,
            pulse_us
        )
