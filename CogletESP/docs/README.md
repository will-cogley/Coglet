# Coglet documentation

**English** · [Deutsch](de/README.md) · [Español](es/README.md) · [日本語](ja/README.md)

Coglet is NMRobotics' DIY desktop companion: a CogNog PCB with an ESP32-S3
(voice, Wi-Fi, camera) and an RP2040 (nine servos, face tracking).

## I want to use and update my Coglet

Everything works from the browser with the **Coglet Updater** page:
<https://will-cogley.github.io/Coglet/>. No software to install.

- [Getting started](en/user/getting-started.md): update, Wi-Fi, pairing
- [Using Coglet](en/user/using-coglet.md): talking, moves, dances, reminders, switches
- [Settings and songs](en/user/settings-and-songs.md): wake word, sounds, "Talk over Coglet", your own songs
- [Troubleshooting](en/user/troubleshooting.md)

## I want to build or change the firmware

You need **ESP-IDF v5.5.3** (exactly this version: the release builds use it).

- [Building the firmware](en/developer/build.md)
- [Hardware: CogNog V3.0 pins](en/developer/hardware.md)
- [Architecture: ESP32-S3, RP2040 and the UART link](en/developer/architecture.md)
- [Protocols: server, MCP tools](en/developer/protocols.md)
- [Dances and songs](en/developer/dance.md)
- [Device-side echo cancellation (AEC)](en/developer/audio-aec.md)
- [Power](en/developer/power.md)
- [Coglet Updater internals](en/developer/web-flasher.md)
- [Releasing](en/developer/releasing.md)

Further reading: the [NMRobots knowledge base](https://nmrobots.com/pages/coglet)
and the upstream [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) project
this firmware is based on.
