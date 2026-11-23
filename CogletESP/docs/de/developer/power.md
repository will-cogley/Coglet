# Stromversorgung

[Dokumentation](../README.md) · [English](../../en/developer/power.md) · **Deutsch** · [Español](../../es/developer/power.md) · [日本語](../../ja/developer/power.md)

## Netzteil

Die CogNog V3.0 ist für ein einfaches **5-V/3-A**-Netzteil am JST-XH-Eingang
ausgelegt. Mehrport-Schnellladegeräte liefern womöglich keine 3 A bei 5 V und
können kurz abschalten, wenn sie die Leistung zwischen Geräten neu verteilen.
Dünne USB-Kabel verlieren unter Last ebenfalls viel Spannung. Nur über den
USB-Programmieranschluss versorgt, bekommen die Servos keinen Strom.

## Gestaffeltes Einschalten der Servos

Schaltet man alle neun Servos auf einmal ein, springen alle gleichzeitig zu
ihrem Ziel. An einem schwachen Netzteil kann die Stromspitze die 5-V-Schiene so
weit herunterziehen, dass die Platine neu startet; das sieht aus wie eine
Bootschleife mit dunkler werdenden LEDs.

Immer wenn die PWM-Ausgabe (wieder) eingeschaltet wird (`RP2040/app.py`), wird
jeder PCA9685-Kanal ganz ausgeschaltet, nOE freigegeben, und die Servos werden
einzeln eingeschaltet, schwere Achsen zuerst:

```
YAW → PIT → ROL → LID → MOU → EAL → EAR → EYL → EYR
```

| Wann | Abstand | Gesamt |
|---|---|---|
| Start | `POWER_UP_GAP_BOOT_MS` = 150 ms | ~1,2 s |
| Kalibriermodus aus der Bereitschaft | 150 ms | ~1,2 s |
| Aufwachen aus der Bereitschaft (Zustand, MCP-Aktion, Tanz) | `POWER_UP_GAP_WAKE_MS` = 60 ms | ~0,5 s |

Die Abfolge blockiert die Hauptschleife nicht. Wird das Haltemoment vorher
wieder freigegeben, wird sie abgebrochen. Ein ruhiger eigener Song lässt LID,
EYL und EYR aus.

Log: `[POWER] staggered power-up (...)`, `[POWER] all servos on after ... ms`.

## Bereitschaft

Hat sich die idle-Pose gesetzt, wartet der RP2040 500 ms und setzt nOE auf
high: Das gesamte Haltemoment der Servos wird freigegeben (die 5-V-Schiene
bleibt an).

Die Inferenz des Grove Vision AI wird angehalten (`AT+BREAK`), solange Coglet
im Leerlauf, im Kalibriermodus oder beim Tanzen ist, und läuft beim Aufwachen
weiter. Mit ausgeschaltetem Schalter Gesichtsverfolgung startet sie nie. Das
Modul selbst bleibt versorgt; die Platine hat keinen Schalter dafür.

## Grund des Neustarts

- ESP32-S3: Die erste Logzeile ist `main: Reset reason: ...`; ein Brown-out
  wird als Fehler protokolliert: `Reset reason: BROWN-OUT (supply voltage dropped)`.
- RP2040: `[BOOT] RP2040 reset cause: ...`. Der RP2040 meldet einen Brown-out
  als Power-on-Reset; unterscheiden Sie beides anhand der ESP-Zeile.
