# CogletESP — Coglet ESP32-S3 firmware

Firmware for the ESP32-S3 on the CogNog PCB of [Coglet](https://nmrobots.com/pages/coglet),
NMRobotics' DIY desktop companion. It handles Wi-Fi, voice chat, the wake word,
the camera and the MCP tools, and drives the RP2040 (servos, face tracking)
over UART. The RP2040 program lives in [`RP2040/`](RP2040) and is carried
inside this firmware, which keeps the RP2040 up to date by itself.

Based on the open-source [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
chatbot (MIT, see [LICENSE](LICENSE)).

**Documentation:** [English](docs/README.md) · [Deutsch](docs/de/README.md) ·
[Español](docs/es/README.md) · [日本語](docs/ja/README.md)

## Updating a Coglet

Most users never need to build anything: the
[Coglet Updater](https://will-cogley.github.io/Coglet/) updates Coglet from the
browser. See [Getting started](docs/en/user/getting-started.md).

## Building

Requires **ESP-IDF v5.5.3** (exactly this version; the release builds use it).

```bash
cd CogletESP
idf.py build
idf.py -p <port> flash monitor
```

The target, the board type (*NMRobotics Coglet (CogNog V3.0 PCB)*) and every
Coglet option are in the committed `sdkconfig`; do not run `idf.py set-target`.
Editions, menuconfig options and the RP2040 workflow are in
[Building the firmware](docs/en/developer/build.md).
