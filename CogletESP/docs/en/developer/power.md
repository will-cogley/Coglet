# Power

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/developer/power.md) · [Español](../../es/developer/power.md) · [日本語](../../ja/developer/power.md)

## Supply

CogNog V3.0 is designed for a plain **5 V / 3 A** supply on the JST-XH input.
Multi-port fast chargers may not deliver 3 A at 5 V and can cut power briefly
when they rebalance between devices. Thin USB cables also drop a lot of voltage
under load. Powered from the programming USB port alone, the servos get no power.

## Staggered servo power-up

Switching all nine servos on at once makes them all jump to their targets at
the same moment. On a weak supply the current spike can pull the 5 V rail down
far enough to reset the board, which looks like a boot loop with dimming LEDs.

Whenever PWM output is (re)enabled (`RP2040/app.py`), every PCA9685 channel is
switched fully off, nOE is enabled, and the servos come on one at a time,
heavy axes first:

```
YAW → PIT → ROL → LID → MOU → EAL → EAR → EYL → EYR
```

| When | Gap | Total |
|---|---|---|
| Boot | `POWER_UP_GAP_BOOT_MS` = 150 ms | ~1.2 s |
| Entering Calibration Mode from standby | 150 ms | ~1.2 s |
| Waking from standby (state, MCP action, dance) | `POWER_UP_GAP_WAKE_MS` = 60 ms | ~0.5 s |

The sequence doesn't block the main loop. If torque is released before it
finishes, it is cancelled. A calm custom song keeps LID, EYL and EYR off.

While a servo is switched off, its position in the program is frozen. When it
is switched on again it starts from where it physically stopped and moves to
its new target at its normal speed, instead of jumping there. Before a dance
the servos are not switched off at all (`prep:`, see
[Architecture](architecture.md#uart-protocol-esp--rp2040)).

Log: `[POWER] staggered power-up (...)`, `[POWER] all servos on after ... ms`.

## Standby

Once the idle pose has settled, the RP2040 waits 500 ms and raises nOE: all
servo torque is released (the 5 V rail stays on).

Grove Vision AI inference is paused (`AT+BREAK`) while Coglet is idle, in
Calibration Mode and during dances, and resumes on wake. With the Face-track
switch off it never starts. The module itself stays powered; the board has no
power switch for it.

## Reset reason

- ESP32-S3: the first log line is `main: Reset reason: ...`; a brown-out is
  logged as an error: `Reset reason: BROWN-OUT (supply voltage dropped)`.
- RP2040: `[BOOT] RP2040 reset cause: ...`. The RP2040 reports a brown-out as
  a power-on reset, so use the ESP line to tell them apart.
