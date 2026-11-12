"""Run the real RP2040 main.py (launcher -> app.py) on the host and check:

* staggered servo power-up at boot / wake / Calibration Mode (order, gaps,
  no channel driven before its turn, nOE handling);
* Grove inference paused (AT+BREAK, no INVOKE) in standby, resumed on wake;
* a calm groove keeps LID / EYL / EYR switched off through a wake power-up.

python3 test_main_power.py
"""
import builtins
import os
import random
import runpy
import select
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vision_sim"))
import sim  # noqa: E402

RP = os.path.abspath(os.path.join(HERE, "..", "..", "RP2040"))
CHANNEL = {"YAW": 10, "ROL": 9, "PIT": 8, "MOU": 3, "EYL": 4, "EYR": 5, "LID": 2, "EAL": 1, "EAR": 0}
NAME_OF = {v: k for k, v in CHANNEL.items()}


class Stop(BaseException):    # not an Exception: the launcher must not catch it
    pass


def run(script, until_ms, pins=None):
    """script: [(t_ms, line)] sent by the 'ESP'. pins: {pin: [(t_ms, value)]}."""
    pins = dict(pins or {})
    pins.setdefault(21, [(0, 0)])      # Facetrack switch ON (active low)
    sim.SIM.now_ms = 0.0
    random.seed(3)
    t = sim.make_time_module()

    def sleep_ms(ms):
        sim.SIM.now_ms += max(1, ms) + 1          # +1 ms loop cost
        if sim.SIM.now_ms > until_ms:
            raise Stop()
    t.sleep_ms = sleep_ms

    log = {"i2c": [], "oe": [], "grove": [], "print": [], "to_esp": []}

    class NoFace:                      # nobody in front of the camera
        def detect(self, t):
            return None
    emu = sim.GroveEmu(NoFace(), 33.3, (2, 15, 1), True)
    orig_cmd = emu._command
    def cmd(c):
        log["grove"].append((sim.SIM.now_ms, c))
        orig_cmd(c)
    emu._command = cmd

    class EspUart:
        def __init__(self):
            self.queue = sorted(script)
        def _ready(self):
            return [l for tt, l in self.queue if tt <= sim.SIM.now_ms]
        def any(self):
            return len(self._ready())
        def read(self, *a):
            out = b""
            while self.queue and self.queue[0][0] <= sim.SIM.now_ms:
                out += (self.queue.pop(0)[1] + "\r\n").encode()
            return out
        def write(self, data):
            log["to_esp"].append((sim.SIM.now_ms, bytes(data)))
            return len(data)
    esp = EspUart()

    m = types.ModuleType("machine")
    class Pin:
        OUT, IN, PULL_UP = 1, 0, 2
        def __init__(self, num=None, *a, **k):
            self.num = num
            self._v = 1
        def value(self, v=None):
            if v is None:
                sched = pins.get(self.num)
                if sched:
                    val = None
                    for tt, vv in sched:
                        if tt <= sim.SIM.now_ms:
                            val = vv
                    if val is not None:
                        return val
                return self._v
            self._v = v
            if self.num == 8:
                log["oe"].append((sim.SIM.now_ms, v))
    class I2C:
        def __init__(self, *a, **k):
            pass
        def scan(self):
            return [0x40]
        def writeto_mem(self, addr, reg, data):
            if 0x06 <= reg < 0x06 + 16 * 4 and (reg - 6) % 4 == 0 and len(data) == 4:
                ch = (reg - 6) // 4
                off = data[3] & 0x10
                log["i2c"].append((sim.SIM.now_ms, ch, "off" if off else "pwm"))
        def readfrom_mem(self, addr, reg, n):
            return bytes(n)
    def UART(uart_id, *a, **k):
        return emu if uart_id == 0 else esp
    m.Pin, m.I2C, m.UART = Pin, I2C, UART
    m.PWRON_RESET, m.WDT_RESET = 1, 3
    m.reset_cause = lambda: 1

    saved = {k: sys.modules.get(k) for k in
             ("time", "machine", "urandom", "uselect", "animation", "servoclass", "vision", "music",
              "dance_data", "app", "coglet_updater")}
    for k in ("animation", "servoclass", "vision", "music", "dance_data", "app", "coglet_updater"):
        sys.modules.pop(k, None)
    sys.modules["time"] = t
    sys.modules["machine"] = m
    sys.modules["urandom"] = random
    sys.modules["uselect"] = select
    sys.path.insert(0, RP)
    real_print = builtins.print
    builtins.print = lambda *a, **k: log["print"].append((sim.SIM.now_ms, " ".join(map(str, a))))
    try:
        runpy.run_path(os.path.join(RP, "main.py"), run_name="__main__")
    except Stop:
        pass
    finally:
        builtins.print = real_print
        sys.path.remove(RP)
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return log


def turn_on_times(log, after, before=1e12):
    """First PWM write per channel after the latest full-off in [after, before)."""
    first_off = {}
    on = {}
    for t, ch, kind in log["i2c"]:
        if not (after <= t < before):
            continue
        if kind == "off":
            first_off[ch] = t
            on.pop(ch, None)
        elif ch in first_off and ch not in on:
            on[ch] = t
    return {NAME_OF[c]: v for c, v in on.items() if c in NAME_OF}, first_off


def check_stagger(label, log, start, gap, expect_names, window=3000):
    on, offs = turn_on_times(log, start, start + window)
    errs = []
    missing = [n for n in expect_names if n not in on]
    if missing:
        errs.append("never switched on: {}".format(missing))
    order = sorted(on, key=lambda n: on[n])
    times = [on[n] for n in order]
    for a, b in zip(times, times[1:]):
        if b - a < gap * 0.8:
            errs.append("two servos switched on {} ms apart".format(b - a))
            break
    span = times[-1] - times[0] if times else 0
    print("{:<26} order={}  span={} ms  {}".format(
        label, ",".join(order), int(span), "OK" if not errs else errs))
    return order, errs


def main():
    fails = 0
    script = [
        (2500, "upd:ver?"),
        (3000, "idle"),
        (9000, "listening"),
        (13000, "idle"),
        (19000, "groove:calm:68"),
        (19100, "listening"),       # a state change mid-song must not re-arm the eyes
        (24000, "groove:end"),
    ]
    log = run(script, 30000)

    all9 = list(CHANNEL)
    # boot
    order, errs = check_stagger("boot (150 ms gap)", log, 0, 150, all9)
    fails += bool(errs)
    if order[:3] != ["YAW", "PIT", "ROL"]:
        print("   heavy axes not first:", order[:3]); fails += 1

    # torque release in standby, then wake on "listening"
    oe = log["oe"]
    released = [t for t, v in oe if v == 1 and 3000 < t < 9000]
    woke = [t for t, v in oe if v == 0 and 9000 <= t < 9500]
    print("standby torque release   at {} ms, nOE re-enabled at {} ms  {}".format(
        int(released[0]) if released else None, int(woke[0]) if woke else None,
        "OK" if released and woke else "FAIL"))
    fails += not (released and woke)
    order, errs = check_stagger("wake (60 ms gap)", log, 9000, 60, all9, window=1500)
    fails += bool(errs)

    # Grove in standby
    def grove_between(a, b):
        return [c for t, c in log["grove"] if a <= t < b]
    stand = grove_between(3000, 9000)
    brk = any(c == "AT+BREAK" for c in stand)
    inv_after = [t for t, c in log["grove"] if 3000 <= t < 9000 and c.startswith("AT+INVOKE")]
    brk_t = min([t for t, c in log["grove"] if 3000 <= t < 9000 and c == "AT+BREAK"] or [None]) if brk else None
    late_inv = [t for t in inv_after if brk_t is not None and t > brk_t]
    resumed = any(c.startswith("AT+INVOKE") for c in grove_between(9000, 12000))
    ok = brk and not late_inv and resumed
    print("Grove standby            BREAK={} INVOKE after BREAK={} resumed on wake={}  {}".format(
        brk, len(late_inv), resumed, "OK" if ok else "FAIL"))
    fails += not ok

    # calm groove from standby: LID/EYL/EYR stay off until the song ends
    on, _ = turn_on_times(log, 19000, 24000)
    eyes_on = [n for n in ("LID", "EYL", "EYR") if n in on]
    body_on = [n for n in ("YAW", "PIT", "ROL", "EAL", "EAR") if n in on]
    ok = not eyes_on and len(body_on) == 5
    print("calm groove              body on={} eyes on={}  {}".format(
        ",".join(body_on), eyes_on or "-", "OK" if ok else "FAIL"))
    fails += not ok
    after_end = [t for t, ch, k in log["i2c"] if t > 24000 and NAME_OF.get(ch) in ("LID", "EYL", "EYR") and k == "pwm"]
    print("eyes back after the song {}".format("OK" if after_end else "FAIL"))
    fails += not after_end

    # Calibration Mode from standby
    log2 = run([(3000, "idle")], 12000, pins={20: [(0, 1), (8000, 0)]})
    order, errs = check_stagger("calibration (150 ms gap)", log2, 8000, 150, all9)
    fails += bool(errs)

    ver = [d for t, d in log["to_esp"] if d.startswith(b"upd:ver:")]
    print("app answers upd:ver?       {}".format(ver[0].strip().decode() + "  OK" if ver else "FAIL"))
    fails += not ver

    reset_line = [p for t, p in log["print"] if p.startswith("[BOOT] RP2040 reset cause")]
    print("reset cause logged        {}".format(reset_line[0] if reset_line else "MISSING"))
    fails += not reset_line

    print("FAILURES:", fails)
    return fails


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
