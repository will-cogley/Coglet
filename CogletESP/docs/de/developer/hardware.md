# Hardware: CogNog V3.0

[Dokumentation](../README.md) · [English](../../en/developer/hardware.md) · **Deutsch** · [Español](../../es/developer/hardware.md) · [日本語](../../ja/developer/hardware.md)

Designdateien: `PCB/SCH_CogletESPV3.0_2026-09-10.pdf` (Schaltplan) und
`PCB/CogletESPV3.0_0906_2026-09-10.epro2` (EasyEDA Pro). Jeder Pin unten wurde
mit der V3.0-Netzliste abgeglichen. Mehr im
[CogNog-Datenblatt](../../../../CogNogDatasheet.md).

## Überblick

| Bauteil | Aufgabe |
|---|---|
| ESP32-S3-WROOM-1-N16R8 (U1) | WLAN, Sprache, Aktivierungswort, Kamera, MCP-Tools. 16 MB Flash, 8 MB PSRAM |
| RP2040 (U7) | Servos und Gesichtsverfolgung, MicroPython |
| PCA9685 (U9) | 16-Kanal-PWM-Servotreiber, I²C-Adresse 0x40 |
| MAX98357A (U16) | I2S-Lautsprecherverstärker |
| CH343P (U14) | USB-Seriell zum Programmieren; der Modusschalter wählt ESP oder RP2040 |
| Kamera GC0308 (FPC1) | Fotos für die KI („Was siehst du?“) |
| Grove Vision AI V2 | Gesichtsverfolgung, Kamera im Auge |
| I2S-MEMS-Mikrofon | Spracheingang |

Strom: **5 V / 3 A** am JST-XH-Eingang; LDOs erzeugen 3,3 V für beide MCUs,
die Servos laufen an der 5-V-Schiene. Nur über den USB-Programmieranschluss
versorgt, läuft die Logik, aber die Servos bekommen keinen Strom.

## ESP32-S3

| GPIO | Netz | Verwendung |
|---|---|---|
| 0 | ESP_GPIO0 | Taste BOOT |
| 3 | ESP_GPIO3 | Rote „Zuhören“-LED (Gate von Q4, aktiv high, 100-kΩ-Pull-down) |
| 4 | MICWS | Mikrofon WS |
| 5 | MICSCK | Mikrofon SCK |
| 6 | MICSD | Mikrofon-Daten |
| 7 | MAXDIN | Verstärker-Daten |
| 15 | MAXBCLK | Verstärker BCLK |
| 16 | MAXLRCLK | Verstärker LRCLK |
| 17 | ESP_GPIO17 | UART1 TX → RP2040 GPIO5 |
| 18 | ESP_GPIO18 | UART1 RX ← RP2040 GPIO4 |
| 19, 20 | USB D−/D+ | Natives USB |
| 43, 44 | ESP_TX / ESP_RX | UART0, Programmieren und Log (CH343P) |
| 1, 2, 45, 46 | ESP_GPIO1, EIO2, EIO45, EIO46 | Frei |

Kamera (GC0308, DVP 8 Bit; CAMD2…CAMD9 sind Y2…Y9 des Sensors):

| Signal | GPIO | Signal | GPIO |
|---|---|---|---|
| D0 (CAMD2) | 41 | XCLK | 14 |
| D1 (CAMD3) | 47 | PCLK | 9 |
| D2 (CAMD4) | 48 | VSYNC | 8 |
| D3 (CAMD5) | 38 | HREF | 40 |
| D4 (CAMD6) | 42 | SIOC (SCCB SCL) | 10 |
| D5 (CAMD7) | 21 | SIOD (SCCB SDA) | 12 |
| D6 (CAMD8) | 11 | RESET | 39 |
| D7 (CAMD9) | 13 | PWDN | — (über R30 an GND) |

Coglet verwendet ein angepasstes GC0308-Modul mit umgekehrter Pinbelegung.

Im Code: [`main/boards/cognog-v3/config.h`](../../../main/boards/cognog-v3/config.h)
und [`main/uart_component.h`](../../../main/uart_component.h).

## RP2040

| GPIO | Verwendung |
|---|---|
| 0, 1 | UART0 TX / RX zum Grove Vision AI V2, 921600 Baud |
| 4, 5 | UART1 TX / RX zum ESP32-S3, 115200 Baud |
| 6, 7 | I²C SDA / SCL zum PCA9685 |
| 8 | PCA9685 nOE (high = alle Servoausgänge aus) |
| 12 | Taste Servotest (aktiv low) |
| 20 | Schalter Kalibrierung (aktiv low) |
| 21 | Schalter Gesichtsverfolgung (aktiv low) |
| 25 | Front-LED (Bestückungsdruck „RP25“) |

Im Code: `RP2040/app.py`, `RP2040/servoclass.py`, `RP2040/vision.py`.

## Servo-Steckplätze

Die neben jedem Steckplatz aufgedruckte Nummer ist sein PCA9685-Kanal.

| Steckplatz | Servo | Schlüssel im Code | Bereich (°) |
|---|---|---|---|
| 0 | Rechtes Ohr | `EAR` | 30–120 |
| 1 | Linkes Ohr | `EAL` | 60–150 |
| 2 | Augenlid | `LID` | 30–160 |
| 3 | Mund | `MOU` | 5–150 |
| 4 | Linkes Auge | `EYL` | 50–140 |
| 5 | Rechtes Auge | `EYR` | 50–140 |
| 8 | Nacken Nicken | `PIT` | 1–80 |
| 9 | Nacken Neigen | `ROL` | 30–120 |
| 10 | Sockel Drehen | `YAW` | 30–150 |
| 6, 7, 11 | Frei | | |

Grenzen, Geschwindigkeiten und Beschleunigungen stehen in `RP2040/animation.py`
(`servos`), die Kalibrierpose in `pose_calibrate`.
