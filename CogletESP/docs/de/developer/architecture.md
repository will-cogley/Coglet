# Architektur

[Dokumentation](../README.md) · [English](../../en/developer/architecture.md) · **Deutsch** · [Español](../../es/developer/architecture.md) · [日本語](../../ja/developer/architecture.md)

```
 xiaozhi.me-Server ──WLAN── ESP32-S3 ──UART1 115200── RP2040 ──I²C── PCA9685 ── 9 Servos
   (Sprache, LLM)           Sprache, Aktivierungswort,  MicroPython  └─UART0 921600── Grove Vision AI V2
                            Kamera, MCP-Tools,
                            Erinnerungen, Tänze
```

Der ESP32-S3 führt die Firmware [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
mit Coglet-Erweiterungen aus. Er entscheidet, **was** Coglet tut, und teilt es
dem RP2040 in kurzen Textzeilen mit. Der RP2040 entscheidet, **wie** sich die
Servos bewegen.

## ESP32-S3-Firmware

| Wo | Was |
|---|---|
| `main/application.cc` | Gerätezustände, Sprachsitzungen, Coglets Boot-Auto-Awake, Tanz- und Erinnerungsabläufe; meldet jeden Zustandswechsel an den RP2040 |
| `main/boards/cognog-v3/` | Platine: Pins, Kamera, rote LED, Coglets MCP-Tools |
| `main/uart_component.cc` | UART1-Verbindung zum RP2040 |
| `main/coglet_rp2040_sync.cc` | Hält das RP2040-Programm aktuell |
| `main/coglet_reminder.cc` | Erinnerungen (NVS) |
| `main/coglet_settings.cc` | Im Coglet Updater gespeicherte Einstellungen |
| `main/coglet_music*.{h,cc}`, `main/coglet_sounds*` | Songs, eingebaute Tanzstücke, Start- und Erinnerungstöne |
| `main/audio/` | Audiopfad, Aktivierungswort, Software-AEC-Referenz |

### Gerätezustände

`starting → wifi_configuring / activating → idle ⇄ connecting → listening ⇄ speaking → idle`

Die rote LED leuchtet nur in `listening`. In `idle` nimmt der RP2040 seine
Schlafpose ein und gibt das Haltemoment der Servos frei.

**Boot-Auto-Awake:** Einige Sekunden nach dem Startton öffnet Coglet von selbst
eine Zuhör-Sitzung. Solange der RP2040 aktualisiert wird, wartet er (höchstens
2 Minuten), damit sich eine Übertragung nie mit dem ersten Gespräch
überschneidet. Das geschieht einmal pro Start; schlägt es fehl, wartet Coglet
auf das Aktivierungswort.

**Proaktive Sitzungen:** Nach einem Tanz und bei einer fälligen Erinnerung
öffnet Coglet von selbst eine Sitzung und sendet einen kurzen Hinweistext, als
wäre er ein erkanntes Aktivierungswort: `（跳完舞了）` („fertig getanzt“) oder
`（有提醒到点了）` („eine Erinnerung ist fällig“). Die Beschreibungen der
MCP-Tools sagen dem LLM, was damit zu tun ist. Sie bleiben absichtlich
chinesisch: Das LLM versteht sie in jeder Sprache, und sie dürfen für
xiaozhi.me höchstens 13 Zeichen lang sein.

## UART-Protokoll (ESP → RP2040)

Ein Befehl pro Zeile, mit `\r\n` am Ende. Jede Zeile wird in einem Aufruf
geschrieben, sodass sich Zeilen verschiedener Tasks nie vermischen.

| Zeile | Bedeutung |
|---|---|
| `idle`, `listening`, `speaking`, `thinking`, `configuring` … | Gerätezustand |
| `neutral`, `happy`, `sad`, `angry`, `surprised`, `sleepy`, `silly`, `confused`, `cool`, `loving`, … | Emotion, die das LLM mit seiner Antwort sendet |
| `action:shake_head` / `blink` / `left_ear` / `right_ear` / `ears` | Einmalige Bewegung aus einem MCP-Tool (drei Durchgänge) |
| `dance:<style>` | Eingebauten Tanz starten, z. B. `dance:mecha` |
| `dance:stop` | Jeden Tanz sofort beenden |
| `groove:<energetic\|calm>:<bpm>` | Tanz zu einem eigenen Song starten |
| `gb:<s><e><b>` | Ein Beat eines eigenen Songs: Akzent 0–9, Abschnittsenergie 0–9, Taktbeginn 0/1 |
| `groove:end` | Eigener Song zu Ende |
| `upd:…` | RP2040-Updateprotokoll (unten) |

Der RP2040 ordnet Zustände und Emotionen in `animation.state_map` Animationen
zu; unbekannte Zeilen werden ignoriert. Emotionen stoppen den Mund nicht: Nur
Zustandszeilen (`idle`, `listening`, `thinking`, `neutral`, …) beenden die
Sprechanimation.

## RP2040-Programm

| Datei | Aufgabe |
|---|---|
| `main.py` | Kleiner Starter: beendet ein unterbrochenes Update, startet `app.py`, fällt in den Wiederherstellungsmodus, wenn `app.py` nicht startet |
| `app.py` | Hauptschleife: UART, Schalter, Servo-Zuständigkeit, Freigabe des Haltemoments |
| `animation.py` | Servotabelle, Posen, Zustandsanimationen, Blinzeln, Sprechmund, MCP-Aktionen |
| `servoclass.py` | PCA9685-Treiber und `Servo` mit Geschwindigkeits- und Beschleunigungsgrenzen |
| `vision.py` | Gesichtsverfolgung mit Grove Vision AI (Augen und Nicken, an den Augengrenzen übernimmt die Sockeldrehung) |
| `music.py`, `dance_*.py` | Tanzwiedergabe und generierte Choreografien |
| `coglet_updater.py` | Empfängt Updates vom ESP |

Wer die Servos steuert, höchste Priorität zuerst:

1. **Kalibriermodus** (Schalter): alles in der Kalibrierpose; die Taste
   Servotest bewegt um ±10°.
2. **Tanz**
3. **MCP-Aktion** (`action:…`)
4. **Zustandsanimation**, Blinzeln, Gesichtsverfolgung (nur außerhalb von idle
   und mit eingeschaltetem Schalter Gesichtsverfolgung), Sprechmund.

Hat sich die idle-Pose gesetzt, wartet der RP2040 500 ms und setzt PCA9685 nOE
auf high, wodurch das gesamte Haltemoment freigegeben wird. Jeder andere
Zustand schaltet die Servos nacheinander wieder ein ([Stromversorgung](power.md)).

## RP2040-Updates

`tools/rp2040_bundle/build_bundle.py` packt bei jedem Build `RP2040/*.py` in
die ESP-Firmware; die Bundle-ID ist ein Hash über alle Dateien. Etwa 5 s nach
dem Start fragt der ESP die Bundle-ID des RP2040 ab. Weicht sie ab, fragt er
Größe und CRC jeder Datei ab und sendet nur die geänderten Dateien:

```
ESP → upd:ver?                       RP → upd:ver:<id>|none
ESP → upd:crc?:<name>                RP → upd:crc:<name>:<size>:<crc32> | upd:crc:<name>:none
ESP → upd:begin:<id>:<files>         RP → upd:ready
ESP → upd:file:<name>:<size>:<crc>   RP → upd:ok:f
ESP → upd:d:<seq>:<base64>           RP → upd:ok:<seq>      (Wiederholungen werden erneut bestätigt)
ESP → upd:end                        RP → upd:ok:e | upd:err:<why>
ESP → upd:commit                     RP → upd:done, dann Neustart
ESP → upd:abort                      vorbereitete Dateien werden gelöscht
```

Der RP2040 schreibt `<name>.new`-Dateien, prüft Größe und CRC-32 und benennt
sie erst um, wenn alle angekommen sind. Die Liste der umzubenennenden Dateien
wird zuerst geschrieben, sodass ein Stromausfall mittendrin beim nächsten Start
abgeschlossen wird. Während einer Übertragung sind die Servos freigegeben.
Eine vollständige Übertragung dauert etwa eine halbe Minute, eine übliche
wenige Sekunden.

ESP-Log (Tag `CogletRp2040`): `RP2040 up to date`, `RP2040 updated (bundle …)`,
`RP2040 did not answer: it needs the one-time setup from the web flasher`,
`RP2040 update failed … retried on the next boot`.

Ältere RP2040 ohne den Updater brauchen einmal die Einrichtung im Coglet
Updater ([Coglet Updater intern](web-flasher.md#einmalige-einrichtung-des-rp2040)).

## Erinnerungen

Bis zu 12 einmalige Erinnerungen mit je höchstens 120 Byte, in NVS als
UTC-Zeiten gespeichert, sodass ein Zeitzonenwechsel eine gespeicherte
Erinnerung nie verschiebt. Die Zeitzone kommt aus dem `timezone_offset` des
Servers (OTA-Prüfung) oder aus einem POSIX-TZ-String in menuconfig. Ist eine
Erinnerung fällig und Coglet im Leerlauf (ein Tanz wird zuerst beendet), spielt
Coglet den Erinnerungston und öffnet dann eine proaktive Sitzung, in der das
LLM `self.coglet.reminder.last_due` aufruft und die Erinnerung in einem Satz
ausspricht.

## Gespeicherte Daten

| Daten | Wo | Bei Updates erhalten |
|---|---|---|
| WLAN, Kopplung, Erinnerungen | NVS-Partition | ja |
| Einstellungen (Sektor `CGST`) | 4 KB vor der Songbibliothek, in `assets` | ja |
| Songbibliothek (`CGML`) | letzte 2 MB von `assets` (0xE00000–0x1000000) | ja |
| App, Assets-Image | `ota_0` / `ota_1`, `assets` | ersetzt |

Partitionstabelle: `partitions/v2/16m.csv`.
