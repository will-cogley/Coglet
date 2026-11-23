# Firmware bauen

[Dokumentation](../README.md) · [English](../../en/developer/build.md) · **Deutsch** · [Español](../../es/developer/build.md) · [日本語](../../ja/developer/build.md)

## ESP-IDF-Version: v5.5.3

Verwenden Sie **ESP-IDF v5.5.3**, keine ältere und keine neuere Version. Die
Release-Builds laufen im offiziellen Container `espressif/idf:v5.5.3`
(`.github/workflows/firmware.yml`), und `dependencies.lock` legt die verwalteten
Komponenten für diese Version fest. Eine andere Version mag bauen, aber das ist
nicht das, was auf Coglets läuft.

### Installation

**Windows:** Starten Sie den [ESP-IDF-Installer für Windows](https://dl.espressif.com/dl/esp-idf/)
und wählen Sie **v5.5.3**. Bauen Sie in der dabei installierten
*ESP-IDF 5.5 PowerShell* (oder CMD).

**Linux / macOS:**

```bash
git clone -b v5.5.3 --recursive https://github.com/espressif/esp-idf.git ~/esp/esp-idf-v5.5.3
cd ~/esp/esp-idf-v5.5.3
./install.sh esp32s3
. ./export.sh          # in jedem neuen Terminal
```

Prüfen: `idf.py --version` gibt `ESP-IDF v5.5.3` aus.

Optional: **ffmpeg** mit libopus, nur für Songs im Ordner `Music/`
([Tänze und Songs](dance.md#der-ordner-music)). Windows: `winget install Gyan.FFmpeg`.

## Bauen und flashen

```bash
cd CogletESP
idf.py build
idf.py -p <port> flash monitor
```

- Ziel (esp32s3), Platinentyp und alle Coglet-Optionen stehen in der
  eingecheckten `sdkconfig`. **Führen Sie nicht `idf.py set-target` aus**: Es
  erzeugt `sdkconfig` aus den Standardwerten neu und verwirft Coglets
  Konfiguration.
- Schließen Sie den oberen USB-C-Anschluss (Programmieranschluss) an, mit dem
  Modusschalter auf **ESP**.
- `<port>` ist zum Beispiel `COM5` unter Windows, `/dev/ttyACM0` oder
  `/dev/ttyUSB0` unter Linux, `/dev/cu.usbmodem…` unter macOS.
- `idf.py flash` behält WLAN, Kopplung, Erinnerungen, die im Coglet Updater
  gespeicherten Einstellungen und die dort hinzugefügten Songs.
  `idf.py erase-flash` löscht all das.
- Der erste Build lädt die verwalteten Komponenten herunter; spätere Builds
  sind inkrementell.

Platinentyp: **NMRobotics Coglet (CogNog V3.0 PCB)**
(`CONFIG_BOARD_TYPE_COGNOG_V3`), Platinendateien in
[`main/boards/cognog-v3/`](../../../main/boards/cognog-v3). Er meldet sich als
`cognog-v3`. Firmware bis 2.3.x verwendete den allgemeinen Platinentyp
`bread-compact-wifi-s3cam`, der für alte lokale Konfigurationen weiterhin
existiert.

## Editionen

Standard, Weihnachten, Elfen und Schneemann unterscheiden sich nur in den drei
eingebauten Tänzen und den Standard-Start- und -Erinnerungstönen. Jede ist eine
Überlagerung auf `sdkconfig` und wird in einem eigenen Ordner gebaut:

```bash
idf.py -B build-christmas -D SDKCONFIG=build-christmas/sdkconfig \
       -D SDKCONFIG_DEFAULTS="sdkconfig;sdkconfig.christmas" build
idf.py -B build-christmas -p <port> flash
```

`sdkconfig.elf` / `build-elf` und `sdkconfig.snowman` / `build-snowman`
funktionieren genauso. Oder wählen Sie sie in menuconfig: *NMRobotics Coglet
Dance → Firmware edition*.

## menuconfig

`idf.py menuconfig`. Die Coglet-Optionen:

| Menü | Optionen |
|---|---|
| Xiaozhi Assistant | Platinentyp, Aktivierungswort (Standard „hello coglet“), Echounterdrückung im Gerät (`USE_DEVICE_AEC`, `COGLET_AEC_DEFAULT_OFF`, `COGLET_AEC_REF_DELAY_MS`), Mikrofonpegel-Log (`COGLET_MIC_DIAG_LOG`) |
| NMRobotics Coglet Reminder | Erinnerung nach dem Ton aussprechen; Zeitzone (automatisch vom Server oder ein POSIX-TZ-String) |
| NMRobotics Coglet RP2040 | RP2040-Programm automatisch aktualisieren |
| NMRobotics Coglet Dance | Eingebaute Tänze, Firmware-Edition, Songs aus `Music/`, Größe der Songbibliothek, Beat-Zeitversatz |
| NMRobotics Coglet Sounds | Standard-Start- und -Erinnerungstöne |

Im Coglet Updater gespeicherte Werte (Aktivierungswort, Aufweckschwelle, Töne,
AEC) haben Vorrang vor menuconfig, bis sie dort mit **Standardwerte verwenden**
gelöscht werden.

## Firmware-Version

Die Version ist `PROJECT_VER` in `CogletESP/CMakeLists.txt` (Release-Builds
nehmen sie aus dem Git-Tag). Verwenden Sie nur Zahlen wie `2.3.2`, optional
mit `-Suffix`: Die OTA-Prüfung vergleicht sie Zahl für Zahl.

## Das RP2040-Programm ändern

Der RP2040 läuft mit MicroPython; sein Programm liegt in
[`RP2040/`](../../../RP2040). Jeder ESP-Build packt diese Dateien in die
Firmware, und der ESP schickt nach dem Start jede geänderte Datei an den
RP2040 ([Architektur](architecture.md#rp2040-updates)). Der normale Weg, den
RP2040 zu ändern, ist also: Dateien bearbeiten und den ESP flashen.

Mit Thonny (Modusschalter auf **RP2040**) können Sie beim Experimentieren
Dateien direkt hochladen. Der ESP sieht dann beim nächsten Start ein anderes
Bundle und spielt seine eigene Kopie zurück. Halten Sie also ESP-Firmware und
`RP2040/` auf demselben Commit oder schalten Sie *NMRobotics Coglet RP2040 →
Update the RP2040 program automatically* beim Experimentieren aus.

Hinweis: Jede Änderung an einer RP2040-Datei, auch an einem Kommentar, lässt
jeden Coglet diese Datei bei seinem nächsten Update erneut übertragen.

## Logs

`idf.py monitor` zeigt das ESP-Log; **Geräteprotokoll anzeigen** im Coglet
Updater zeigt dasselbe. Der RP2040 schreibt auf seine eigene USB-Seriell-
Schnittstelle (Modusschalter auf RP2040). Nützliche Tags: `CogletRp2040`
(Updates der Servoplatine), `CogletDance`, `CogletReminder`, `CogletSettings`,
`CogletMusic`, `CogletAutoAwake`.
