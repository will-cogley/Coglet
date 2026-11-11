# Coglet power-up and standby power

## Staggered servo power-up (RP2040 `main.py`)

Switching all 9 servos on at the same instant makes every servo jump to its
target at once. On a weak supply or cable the current spike can pull the 5 V
rail down far enough to reset the board, which looks like a boot loop with the
LEDs dimming.

Whenever PWM output is (re)enabled, every PCA9685 channel is first switched
fully off, then nOE is enabled, and the servos are switched on one at a time,
heavy axes first:

```
YAW -> PIT -> ROL -> LID -> MOU -> EAL -> EAR -> EYL -> EYR
```

| When | Gap between servos | Total |
|---|---|---|
| Boot | `POWER_UP_GAP_BOOT_MS` = 150 ms | ~1.2 s |
| Entering Calibration Mode (from standby) | 150 ms | ~1.2 s |
| Waking from standby (state, MCP action, dance) | `POWER_UP_GAP_WAKE_MS` = 60 ms | ~0.5 s |

The sequence is non-blocking: UART, animations and timing keep running while
it switches the servos on. If torque is released again before it finishes, it
is cancelled. A calm groove (custom song) keeps LID / EYL / EYR off: the
sequence skips them until the song ends.

Log lines: `[POWER] staggered power-up (...)` and `[POWER] all servos on after ... ms`.

Standby behaviour is unchanged: once the idle pose has settled, all servo
torque is released.

## Grove Vision AI V2 in standby

In standby the eyelid is closed, so face tracking has nothing to see. Grove
inference is paused (`AT+BREAK`) while Coglet is idle and resumes on wake. It
is also paused in Calibration Mode and during dances, as before. The Facetrack
switch (GP21) still wins: when it's OFF, inference never starts.

Note: this stops the Grove's inference, but the module stays powered. There is
no power switch for it on the CogNog 3.0 board.

## Reset reason in the logs

* ESP32-S3: the first log line is `main: Reset reason: ...`. A brown-out is
  logged as an error: `Reset reason: BROWN-OUT (supply voltage dropped)`.
* RP2040: `[BOOT] RP2040 reset cause: ...`. The RP2040 reports a brown-out as
  a power-on reset, so use the ESP line to tell them apart.

## Power supply

CogNog 3.0 is designed for a plain **5 V / 3 A** USB-C supply. Multi-port
fast chargers may not deliver 3 A at 5 V, and can briefly cut power when they
rebalance between devices. Thin USB-A to USB-C cables can also drop a lot of
voltage under load.

## Tests

```bash
python3 tests/power_sim/test_main_power.py
```

This runs the real `main.py` on the host with simulated PCA9685, ESP UART and
Grove. It checks the order and gaps of the boot, wake and calibration
power-ups, that no two servos switch on together, Grove pause/resume in
standby, and that a calm groove keeps the eye servos off.
