# CogletESP — Coglet ESP32-S3 firmware

Firmware for the ESP32-S3 on the CogNog PCB of [Coglet](https://nmrobots.com/pages/coglet),
NMRobotics' DIY desktop companion. It handles Wi-Fi, voice chat, the wake word,
the camera and the MCP tools, and drives the RP2040 (servos, face tracking)
over UART. The RP2040 program lives in [`RP2040/`](RP2040) and is carried
inside this firmware, which keeps the RP2040 up to date by itself.

Based on the open-source [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
chatbot (MIT, see [LICENSE](LICENSE)).

## Updating a Coglet

Most users never need to build anything: use the web flasher, see
[docs/coglet-web-flasher.md](docs/coglet-web-flasher.md).

## Building

Requires ESP-IDF 5.5 (the release workflow uses v5.5.3).

```bash
idf.py set-target esp32s3   # only once
idf.py build flash
```

Board type: `Xiaozhi Assistant → Board Type → NMRobotics Coglet (CogNog V3.0 PCB)`,
already selected in `sdkconfig`. Board files: [`main/boards/cognog-v3/`](main/boards/cognog-v3).

Editions (different built-in dances, startup and reminder sounds) are overlays:

```bash
idf.py -B build-christmas -D SDKCONFIG=build-christmas/sdkconfig \
       -D SDKCONFIG_DEFAULTS="sdkconfig;sdkconfig.christmas" build
```

Use `sdkconfig.elf` or `sdkconfig.snowman` the same way. Custom songs for your
own build go in [`Music/`](Music).

## Documentation

Coglet:

- [Web flasher, RP2040 updates, settings, "My songs"](docs/coglet-web-flasher.md)
- [Music dance](docs/coglet-dance.md)
- [Device-side AEC (talk over Coglet)](docs/coglet-device-aec.md)
- [Servo power-up and standby power](docs/coglet-power.md)

Inherited from xiaozhi-esp32:

- [MCP protocol](docs/mcp-protocol.md) and [MCP usage](docs/mcp-usage.md)
- [WebSocket protocol](docs/websocket.md) and [MQTT + UDP protocol](docs/mqtt-udp.md)
- [Adding a custom board](docs/custom-board.md)
