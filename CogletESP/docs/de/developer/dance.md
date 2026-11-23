# Tänze und Songs

[Dokumentation](../README.md) · [English](../../en/developer/dance.md) · **Deutsch** · [Español](../../es/developer/dance.md) · [日本語](../../ja/developer/dance.md)

Bittet der Nutzer Coglet zu tanzen, macht das MCP-Tool `self.coglet.dance(style)`
Folgendes:

1. Es lässt das LLM mit einer kurzen Zeile antworten („Watch this!“);
2. beendet das Gespräch;
3. spielt den Song, während der RP2040 jeden Servo im Takt bewegt;
4. öffnet danach von selbst eine neue Sitzung mit dem Hinweis `（跳完舞了）` und
   fragt, wie es dem Nutzer gefallen hat.

| | Eingebaute Stücke | Eigene Songs |
|---|---|---|
| Musik | drei eigene oder gemeinfreie Arrangements von etwa 30 s pro Edition | Ordner `Music/` (einkompiliert) oder *Meine Songs* im Coglet Updater (Songbibliothek) |
| Tanz | handgeschriebene Choreografie, aus derselben Partitur wie die Musik erzeugt | automatisch: Beats werden vorab erkannt und während des Songs an den RP2040 gestreamt |
| RP2040-Dateien | `music.py` + `dance_data.py` / `dance_xmas.py` / `dance_elf.py` / `dance_snow.py` | nur `music.py` |

## Eingebaute Stücke

| Edition | `style` | Musik | Tempo |
|---|---|---|---|
| Standard | `mecha` | wuchtiger Mecha-Elektro, f-Moll | 128 BPM |
| | `evil` | düsterer Gothic, d-Moll harmonisch | 96 BPM |
| | `cat` | sanfter Anime-Katzen-Pop, C-Dur | 120 BPM |
| Weihnachten | `lyrical` | Stille Nacht | 104 BPM, 3/4 |
| | `classic` | Jingle Bells | 136 BPM |
| | `grand` | Freue dich, Welt (Joy to the World) | 84 BPM, 2/4 |
| Elfen | `workshop` | Deck the Halls | 132 BPM |
| | `mischief` | God Rest Ye Merry Gentlemen | 156 BPM |
| | `party` | We Wish You a Merry Christmas | 160 BPM, 3/4 |
| Schneemann | `lullaby` | Brahms, Wiegenlied op. 49/4 | 104 BPM, 3/4 |
| | `stomp` | Good King Wenceslas | 108 BPM |
| | `blizzard` | Leontowytsch, Schtschedryk (1914; Carol of the Bells) | 150 BPM, 3/4 |

`random` wählt eines der drei Stücke der Edition. Nur die Stücke einer Edition
passen in die Firmware; der RP2040 kennt die Choreografien aller Editionen und
importiert nur das Modul, das er braucht. Jeder Tanz erreicht seine Schlusspose
1,5 s vor dem Ende der Musik, sodass Coglet vor der Folgesitzung zur Ruhe kommt.

## Eigene Songs

Zwei Quellen, die gleich getanzt werden:

- **Meine Songs** im Coglet Updater: im Browser umgewandelt, in der
  Songbibliothek außerhalb der Firmware gespeichert, bleiben bei Updates
  erhalten ([Coglet Updater intern](web-flasher.md#meine-songs)).
- **Der Ordner `Music/`**: in Ihren eigenen Build kompiliert (unten).

### Presets

| Preset | Bewegt | Stil |
|---|---|---|
| energetic (lebhaft) | jeden Servo | Kopfnicken auf jedem Beat (tiefer auf Akzenten), Ohrenzucken, Wiegen und Sockeldrehungen in jedem Takt, Augen im Takt, Blinzeln, Mund auf den stärksten Schlägen; skaliert mit der Lautstärke des Songs |
| calm (ruhig) | Ohren, Kopf (Nicken und Neigen) und Sockel | langsames Nicken auf dem gefühlten Puls, treibende Ohren, leichtes Wiegen; **Augenlid und beide Augenservos sind** für den ganzen Song **ohne Haltemoment** |

Ruhige Songs folgen dem gefühlten Puls: Eine Ballade mit 136 BPM, die sich wie
68 anfühlt, nickt mit 68.

### Der Ordner `Music/`

1. Legen Sie Audiodateien in `CogletESP/Music/`: mp3, wav, flac, m4a, aac, ogg,
   opus, wma, aiff oder ein Video (mp4, mov, m4v, webm, mkv; dessen Tonspur
   wird verwendet).
2. `idf.py build`. `tools/coglet_music/build_music.py` wandelt jede Datei in
   Ogg/Opus um (mono, 24 kHz, 60-ms-Frames, lautheitsnormalisiert), kürzt sie
   mit Ausblendung auf die Maximallänge, erkennt Tempo, Beats, Akzente,
   Abschnitte und Taktanfänge, wählt ein Preset und kompiliert sie ein. Die
   Ergebnisse werden in `build/coglet_music/cache/` zwischengespeichert.
3. Flashen und „tanz zu *Night Rain*“ oder „tanz zu einem meiner Songs“ sagen.
   Der Songname ist der Dateiname ohne Endung und Tags.

Preset oder Tempo erzwingen Sie mit Tags vor der Endung:

```
Night Rain.calm.mp3
Drop It.energetic.wav
Free Fall.calm.68bpm.m4a
```

Benötigt ffmpeg mit libopus; ohne ffmpeg werden die Songs mit einer Warnung
übersprungen, und der Build gelingt trotzdem. `Music/.gitignore` hält Ihre
Songs aus Git heraus. **Veröffentlichen Sie keine Firmware-Images mit Musik,
an der Sie keine Rechte haben.**

menuconfig, *NMRobotics Coglet Dance*:

| Option | Standard | |
|---|---|---|
| Custom songs from the Music folder | an | |
| ffmpeg executable | `ffmpeg` | Name oder voller Pfad; unter Windows mit Schrägstrichen, z. B. `C:/ffmpeg/bin/ffmpeg.exe` |
| Maximum length per song | 60 s | |
| Opus bitrate | 32 kbps | etwa 240 KB pro Minute |
| Flash budget for all custom songs | 400 KB | Songs, die nicht passen, werden übersprungen |
| Song library size | 2048 KB | Platz für im Coglet Updater hinzugefügte Songs |
| Beat timing offset | 20 ms | Bewegungen zu spät → senken, zu früh → erhöhen |

## Funktionsweise

ESP (`main/application.cc`):

```
self.coglet.dance(style)
  WaitAck   auf die einzeilige Antwort warten (TTS beendet, Audio still; max. 10–20 s)
  Starting  Audiokanal schließen → idle
  Playing   eingebaut: "dance:<style>", ein Task spielt das Stück
            eigener Song: "groove:<preset>:<bpm>", ein Task spielt den Song, ein
                      anderer sendet auf jedem Beat "gb:<strength><energy><bar>", dann "groove:end"
  FollowUp  1 s nach der Musik: proaktive Sitzung mit "（跳完舞了）"
```

- Ein Aktivierungswort oder die Taste beendet den Tanz sofort (`dance:stop`),
  und statt der Folgefrage beginnt das eigene Gespräch des Nutzers.
- Eine Erinnerung, die während eines Tanzes fällig wird, wartet auf dessen Ende
  und ersetzt die Folgefrage.
- `AudioService::PlaySound()` nimmt ein Abbruch-Flag, sodass Songs innerhalb
  von ~10 ms stoppen.

RP2040 (`RP2040/music.py`): Ein Tanz steuert jeden Servo (nur der Kalibriermodus
hat Vorrang). Synchronisation: `AUDIO_LATENCY_MS = 120` (Befehl bis Ton) und
`SERVO_LEAD_MS = 100` (Bewegungen starten früher, um auf dem Beat zu landen).
Bleiben die Beats bei einem eigenen Song 4 s aus, endet der Tanz von selbst.
Danach werden die Standard-Bewegungsgrenzen wiederhergestellt und der aktuelle
Zustand erneut angewendet.

## Die eingebauten Stücke neu erzeugen

`tools/coglet_dj/` (Python mit numpy und scipy, dazu ffmpeg):

```bash
cd tools/coglet_dj
python3 render.py mecha evil cat                    # out/*.ogg, Vorschauen, Choreografie-JSON
python3 export_rp2040.py ../../RP2040/dance_data.py
```

Nur die Choreografie ändern: `choreo.py` bearbeiten, `choreo_only.py` und dann
`export_rp2040.py` ausführen. Die Feiertags-Editionen funktionieren genauso mit
`xmas.py` / `choreo_xmas.py` / `export_xmas_rp2040.py` / `export_xmas_headers.py`
und den Entsprechungen für `elf` und `snow`. Die Header-Exporter lesen
`out/approved/`, sodass nur angehörtes Audio in `main/coglet_sounds/` landet.
Die erzeugten `dance_*.py`-Dateien werden nicht von Hand bearbeitet.
