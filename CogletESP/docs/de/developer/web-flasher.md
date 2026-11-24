# Coglet Updater intern

[Dokumentation](../README.md) · [English](../../en/developer/web-flasher.md) · **Deutsch** · [Español](../../es/developer/web-flasher.md) · [日本語](../../ja/developer/web-flasher.md)

Der Coglet Updater (<https://will-cogley.github.io/Coglet/>) ist eine einzige
statische Seite in `tools/web_flasher/`: `index.html`, `coglet_i18n.js`
(Übersetzungen) und `coglet_songs.js` (Songumwandlung). Er verwendet
[esptool-js](https://github.com/espressif/esptool-js) 0.6.1 und Web Serial und
braucht daher einen Chromium-basierten Desktop-Browser über HTTPS oder
`localhost`; Songs brauchen zusätzlich WebCodecs (Chrome / Edge 94+).
Anleitung für Nutzer: [Erste Schritte](../user/getting-started.md).

## Aktualisieren

- Die Seite lehnt alles ab, was kein ESP32-S3 ist. Jeder Teil wird vor und nach
  dem Schreiben gegen die MD5 im Manifest geprüft; Flash-Modus, -Frequenz und
  -Größe bleiben wie gebaut.
- Sie schreibt Bootloader, Partitionstabelle, OTA-Daten, App und Assets-Image,
  nie NVS, den Einstellungssektor oder die Songbibliothek. **Neuinstallation**
  löscht zuerst den ganzen Chip.
- Jede Schaltfläche fragt nach dem Port, bevor etwas heruntergeladen wird
  (Browser zeigen die Portliste nur direkt nach einem Klick). Die Portwahl wird
  nach USB-ID gespeichert. Die Liste zeigt nur die USB-Seriell-Chips, die
  Coglet verwendet; **Alle Ports anzeigen** listet alles auf.
- Verliert die USB-Verbindung Daten, schreibt sie mit der nächstniedrigeren
  Geschwindigkeit neu (921600 → 460800 → 115200) und merkt sich, was
  funktioniert hat.
- Nach dem Schreiben startet sie Coglet neu, zeigt das Startprotokoll und
  wertet es aus:

| Coglets Log meldet | Die Seite zeigt |
|---|---|
| `RP2040 did not answer` | „Noch ein Schritt“: die Karte zur Einrichtung der Servoplatine |
| `sending N of M files` | Servoplatine wird aktualisiert, angeschlossen lassen |
| `RP2040 running again` / `up to date` | alles bereit |
| `RP2040 update failed` / `did not answer within` | wird beim nächsten Start wiederholt; die Einrichtungskarte ist der Ausweg |

### Meinen Coglet prüfen

Liest die Partitionstabelle (0x8000), `otadata` (welcher Slot startet) und das
erste 1 KB dieses App-Slots. Aus der App-Beschreibung von ESP-IDF (Version) und
Coglets eigener Beschreibung (`main/coglet_app_desc.h`: Magic `COGLET`,
Edition, Build-Commit) meldet sie: Update verfügbar, aktuell, neuer (Testbuild),
eigener Build des Nutzers (`local`), anderer Build derselben Version, Firmware
von vor v2.3.0 oder keine Firmware. Sie wählt auch Coglets eigene Edition aus,
startet Coglet dann neu und meldet den Zustand der Servoplatine.

### Einmalige Einrichtung des RP2040

Für RP2040, die vor den automatischen Updates eingerichtet wurden. Mit dem
Modusschalter auf RP2040 stoppt die Seite das laufende Programm über den Raw
REPL von MicroPython, schreibt jede Datei als `<name>.tmp`, prüft die Größen,
benennt sie um, schreibt die Bundle-ID nach `coglet_bundle.txt` und führt
einen Soft-Reboot aus. Nichts wird ersetzt, bevor alle Dateien geschrieben
sind. MicroPython muss bereits auf dem RP2040 sein (jedes Kit wird so
ausgeliefert).

## Einstellungen

Ein 4-KB-Sektor direkt vor der Songbibliothek (`main/coglet_settings.h`):
`CGST`, Version, Länge, CRC-32 (zlib), dann `key=value`-Zeilen:

| Schlüssel | Werte |
|---|---|
| `wake_word` | englische Phrase, Kleinbuchstaben a–z, `'` und Leerzeichen |
| `threshold` | 1–99 % (die Seite bietet 1–50) |
| `startup`, `reminder` | `mecha`, `evil`, `cat`, `christmas`, `elf`, `snowman` |
| `aec` | `on` / `off` |

Gespeichert werden nur Werte, die von den Standardwerten der gewählten Edition
abweichen; der Rest folgt der Firmware (`make_manifest.py` veröffentlicht die
Standardwerte in `manifest.json`). Fehlende oder ungültige Werte fallen auf
menuconfig zurück. `idf.py flash` schreibt hier einen leeren Sektor
(`coglet_settings_reset.bin`, von `main/CMakeLists.txt` hinzugefügt), damit ein
eigener Build mit seiner menuconfig startet; `make_manifest.py` lässt diesen
Teil weg, sodass die Seite und die Release-Zips die Einstellungen der Nutzer
behalten. Das MultiNet-Modell wandelt das
Aktivierungswort selbst in Phoneme um; gelingt das nicht, behält Coglet sein
eingebautes Aktivierungswort und protokolliert
`Wake word "..." from settings can't be used`.

```
I (900) CogletSettings: settings: wake word "hey coglet", threshold 3, startup cat, reminder evil, aec on
```

## Meine Songs

Der Browser dekodiert jede Datei und findet die Beats mit derselben Analyse wie
`tools/coglet_music/build_music.py` (`coglet_songs.js` ist eine Portierung und
liefert dieselben Beats). Er pegelt den Song mit einem Limiter auf −14 LUFS ein,
kürzt ihn mit Ausblendung auf 60 s und kodiert mit WebCodecs Ogg/Opus (mono,
24 kHz, 60-ms-Frames, 32 kbps).

Die **Songbibliothek** sind die letzten 2 MB der Partition `assets`
(0xE00000–0x1000000), die das Assets-Image nie erreicht; `make_manifest.py`
lehnt einen Build ab, dessen Assets hineinreichen würden. Aufbau
(`main/coglet_music.h`): Sektor 0 enthält den Header `CGML` und bis zu 32
Einträge (Name, Preset, BPM, Länge, Offsets, CRC-32); Ogg-Daten und Beattabelle
jedes Songs beginnen in einem eigenen 4-KB-Sektor. Die Liste wird zuletzt
geschrieben, und jeder Song hat seine eigene CRC, sodass ein unterbrochenes
Speichern die vorherigen Songs behält und ein beschädigter Song übersprungen
wird.

```
I (5120) CogletMusic: song library: 3 songs at assets+0x600000
```

## Sprachen

Englisch, Deutsch, Spanisch und Japanisch. Die Seite folgt der Sprache des
Browsers (sonst Englisch); das Menü 🌐 wechselt sie und merkt sie sich;
`?lang=de|es|ja|en` erzwingt eine. Der englische Text steht in `index.html`
(`data-i18n="key"`), die anderen Sprachen sind Wörterbücher in
`coglet_i18n.js`; Skriptmeldungen verwenden `t("key", {name: value})` mit
Pluralregeln und lokalen Zahlenformaten. Das Geräteprotokoll bleibt englisch.

Eine Sprache hinzufügen: in `LANGS` eintragen, ein Wörterbuch mit jedem
Schlüssel (gleiche `{placeholders}` und Auszeichnung) anlegen und eine
`<option>` im Menü 🌐 ergänzen.

## Aussehen

- *Darstellung*: hell, dunkel, Tag und Nacht (hell 7:00–19:00) oder die
  Browsereinstellung.
- 1. Dezember bis 6. Januar: ein Weihnachtslook aus SVG und CSS (Girlande,
  Lichter, fallende Sterne oder Schneeflocken). Eine Schaltfläche schaltet ihn
  für die Saison aus; `?season=christmas|plain` erzwingt ihn. Mit *Bewegung
  reduzieren* bewegt sich nichts.
- Barrierefreiheit: nur Tastatur, beschriftete Bedienelemente, angesagter
  Fortschritt und Fehler (beginnen mit „Error:“), WCAG-AA-Kontrast, 200 % Zoom.

## Lokal testen

Stellen Sie `index.html`, `coglet_i18n.js` und `coglet_songs.js` neben einen mit
`make_manifest.py` aus Ihrem Build erzeugten Ordner `firmware/` (und `rp2040/`
für die einmalige Einrichtung) auf `localhost` bereit. Für die anderen
Editionen führen Sie zusätzlich `make_manifest.py --edition christmas` (oder
`elf`, `snowman`) auf deren Build aus; ohne sie zeigt die Seite keine
Editionsauswahl.
