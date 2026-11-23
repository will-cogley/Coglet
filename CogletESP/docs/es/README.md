# Documentación de Coglet

[English](../README.md) · [Deutsch](../de/README.md) · **Español** · [日本語](../ja/README.md)

Coglet es el compañero de escritorio DIY de NMRobotics: una placa CogNog con
un ESP32-S3 (voz, Wi-Fi, cámara) y un RP2040 (nueve servos, seguimiento de
caras).

## Quiero usar y actualizar mi Coglet

Todo funciona desde el navegador con la página **Coglet Updater**:
<https://will-cogley.github.io/Coglet/>. No hay que instalar nada.

- [Primeros pasos](user/getting-started.md): actualizar, Wi-Fi, vinculación
- [Usar Coglet](user/using-coglet.md): hablar, movimientos, bailes, recordatorios, interruptores
- [Ajustes y canciones](user/settings-and-songs.md): palabra de activación, sonidos, «Interrumpir a Coglet», tus propias canciones
- [Solución de problemas](user/troubleshooting.md)

## Quiero compilar o modificar el firmware

Necesitas **ESP-IDF v5.5.3** (exactamente esta versión: la usan las compilaciones oficiales).

- [Compilar el firmware](developer/build.md)
- [Hardware: pines de la CogNog V3.0](developer/hardware.md)
- [Arquitectura: ESP32-S3, RP2040 y el enlace UART](developer/architecture.md)
- [Protocolos: servidor, herramientas MCP](developer/protocols.md)
- [Bailes y canciones](developer/dance.md)
- [Cancelación de eco en el dispositivo (AEC)](developer/audio-aec.md)
- [Alimentación](developer/power.md)
- [Funcionamiento interno del Coglet Updater](developer/web-flasher.md)
- [Publicar versiones](developer/releasing.md)

Más información: la [base de conocimiento de NMRobots](https://nmrobots.com/pages/coglet)
y el proyecto original [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32), en
el que se basa este firmware.
