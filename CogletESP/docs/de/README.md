# Coglet-Dokumentation

[English](../README.md) · **Deutsch** · [Español](../es/README.md) · [日本語](../ja/README.md)

Coglet ist der DIY-Schreibtischbegleiter von NMRobotics: eine CogNog-Platine
mit einem ESP32-S3 (Sprache, WLAN, Kamera) und einem RP2040 (neun Servos,
Gesichtsverfolgung).

## Ich möchte meinen Coglet benutzen und aktualisieren

Alles funktioniert im Browser mit der Seite **Coglet Updater**:
<https://will-cogley.github.io/Coglet/>. Keine Installation nötig.

- [Erste Schritte](user/getting-started.md): Update, WLAN, Kopplung
- [Coglet benutzen](user/using-coglet.md): Sprechen, Bewegungen, Tänze, Erinnerungen, Schalter
- [Einstellungen und Songs](user/settings-and-songs.md): Aktivierungswort, Töne, „Coglet ins Wort fallen“, eigene Songs
- [Fehlerbehebung](user/troubleshooting.md)

## Ich möchte die Firmware bauen oder ändern

Sie brauchen **ESP-IDF v5.5.3** (genau diese Version: Die Release-Builds verwenden sie).

- [Firmware bauen](developer/build.md)
- [Hardware: Pins der CogNog V3.0](developer/hardware.md)
- [Architektur: ESP32-S3, RP2040 und die UART-Verbindung](developer/architecture.md)
- [Protokolle: Server, MCP-Tools](developer/protocols.md)
- [Tänze und Songs](developer/dance.md)
- [Echounterdrückung im Gerät (AEC)](developer/audio-aec.md)
- [Stromversorgung](developer/power.md)
- [Coglet Updater intern](developer/web-flasher.md)
- [Releases veröffentlichen](developer/releasing.md)

Weiterführend: die [NMRobots-Wissensdatenbank](https://nmrobots.com/pages/coglet)
und das Upstream-Projekt [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32),
auf dem diese Firmware basiert.
