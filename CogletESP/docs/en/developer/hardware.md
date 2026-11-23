# Hardware: CogNog V3.0

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/developer/hardware.md) · [Español](../../es/developer/hardware.md) · [日本語](../../ja/developer/hardware.md)

Design files: `PCB/SCH_CogletESPV3.0_2026-09-10.pdf` (schematic) and
`PCB/CogletESPV3.0_0906_2026-09-10.epro2` (EasyEDA Pro). Every pin below was
checked against the V3.0 netlist. More in the
[CogNog datasheet](../../../../CogNogDatasheet.md).

## Overview

| Part | Role |
|---|---|
| ESP32-S3-WROOM-1-N16R8 (U1) | Wi-Fi, voice, wake word, camera, MCP tools. 16 MB flash, 8 MB PSRAM |
| RP2040 (U7) | Servos and face tracking, MicroPython |
| PCA9685 (U9) | 16-channel PWM servo driver, I²C address 0x40 |
| MAX98357A (U16) | I2S speaker amplifier |
| CH343P (U14) | USB serial for programming; the mode switch selects ESP or RP2040 |
| GC0308 camera (FPC1) | Photos for the AI ("what do you see?") |
| Grove Vision AI V2 | Face tracking, camera in the eye |
| I2S MEMS microphone | Voice input |

Power: **5 V / 3 A** on the JST-XH input; LDOs make 3.3 V for both MCUs, and
the servos run from the 5 V rail. Powered from the programming USB port alone,
the logic runs but the servos get no power.

## ESP32-S3

| GPIO | Net | Use |
|---|---|---|
| 0 | ESP_GPIO0 | BOOT button |
| 3 | ESP_GPIO3 | Red "listening" LED (Q4 gate, active high, 100 kΩ pull-down) |
| 4 | MICWS | Microphone WS |
| 5 | MICSCK | Microphone SCK |
| 6 | MICSD | Microphone data |
| 7 | MAXDIN | Amplifier data |
| 15 | MAXBCLK | Amplifier BCLK |
| 16 | MAXLRCLK | Amplifier LRCLK |
| 17 | ESP_GPIO17 | UART1 TX → RP2040 GPIO5 |
| 18 | ESP_GPIO18 | UART1 RX ← RP2040 GPIO4 |
| 19, 20 | USB D−/D+ | Native USB |
| 43, 44 | ESP_TX / ESP_RX | UART0, programming and log (CH343P) |
| 1, 2, 45, 46 | ESP_GPIO1, EIO2, EIO45, EIO46 | Spare |

Camera (GC0308, DVP 8-bit; CAMD2…CAMD9 are the sensor's Y2…Y9):

| Signal | GPIO | Signal | GPIO |
|---|---|---|---|
| D0 (CAMD2) | 41 | XCLK | 14 |
| D1 (CAMD3) | 47 | PCLK | 9 |
| D2 (CAMD4) | 48 | VSYNC | 8 |
| D3 (CAMD5) | 38 | HREF | 40 |
| D4 (CAMD6) | 42 | SIOC (SCCB SCL) | 10 |
| D5 (CAMD7) | 21 | SIOD (SCCB SDA) | 12 |
| D6 (CAMD8) | 11 | RESET | 39 |
| D7 (CAMD9) | 13 | PWDN | — (tied to GND via R30) |

Coglet uses a customised GC0308 module with an inverted pin layout.

In code: [`main/boards/cognog-v3/config.h`](../../../main/boards/cognog-v3/config.h)
and [`main/uart_component.h`](../../../main/uart_component.h).

## RP2040

| GPIO | Use |
|---|---|
| 0, 1 | UART0 TX / RX to the Grove Vision AI V2, 921600 baud |
| 4, 5 | UART1 TX / RX to the ESP32-S3, 115200 baud |
| 6, 7 | I²C SDA / SCL to the PCA9685 |
| 8 | PCA9685 nOE (high = all servo outputs off) |
| 12 | Servo test button (active low) |
| 20 | Calibration switch (active low) |
| 21 | Face-track switch (active low) |
| 25 | Front LED (silkscreen "RP25") |

In code: `RP2040/app.py`, `RP2040/servoclass.py`, `RP2040/vision.py`.

## Servo sockets

The number printed next to each socket is its PCA9685 channel.

| Socket | Servo | Code key | Range (°) |
|---|---|---|---|
| 0 | Right ear | `EAR` | 30–120 |
| 1 | Left ear | `EAL` | 60–150 |
| 2 | Eyelid | `LID` | 30–160 |
| 3 | Mouth | `MOU` | 5–150 |
| 4 | Left eye | `EYL` | 50–140 |
| 5 | Right eye | `EYR` | 50–140 |
| 8 | Neck pitch | `PIT` | 1–80 |
| 9 | Neck roll | `ROL` | 30–120 |
| 10 | Base yaw | `YAW` | 30–150 |
| 6, 7, 11 | Free | | |

Limits, speeds and accelerations are in `RP2040/animation.py` (`servos`), the
calibration pose in `pose_calibrate`.
