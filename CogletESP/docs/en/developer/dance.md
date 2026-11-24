# Dances and songs

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/developer/dance.md) · [Español](../../es/developer/dance.md) · [日本語](../../ja/developer/dance.md)

When the user asks Coglet to dance, the MCP tool `self.coglet.dance(style)`:

1. lets the LLM answer with one short line ("Watch this!");
2. ends the conversation;
3. plays the song while the RP2040 moves every servo to the beat;
4. opens a new session by itself with the cue `（跳完舞了）` and asks how the
   user liked it.

| | Built-in tracks | Custom songs |
|---|---|---|
| Music | three original or public-domain arrangements of about 30 s per edition | `Music/` folder (compiled in) or *My songs* on the Coglet Updater (song library) |
| Dance | hand-written choreography, generated from the same score as the music | automatic: beats detected in advance, streamed to the RP2040 while the song plays |
| RP2040 files | `music.py` + `dance_data.py` / `dance_xmas.py` / `dance_elf.py` / `dance_snow.py` | `music.py` only |

## Built-in tracks

| Edition | `style` | Music | Tempo |
|---|---|---|---|
| Standard | `mecha` | heavy mecha electro, F minor | 128 BPM |
| | `evil` | gloomy gothic, D harmonic minor | 96 BPM |
| | `cat` | gentle anime cat pop, C major | 120 BPM |
| Christmas | `lyrical` | Silent Night | 104 BPM, 3/4 |
| | `classic` | Jingle Bells | 136 BPM |
| | `grand` | Joy to the World | 84 BPM, 2/4 |
| Elf | `workshop` | Deck the Halls | 132 BPM |
| | `mischief` | God Rest Ye Merry Gentlemen | 156 BPM |
| | `party` | We Wish You a Merry Christmas | 160 BPM, 3/4 |
| Snowman | `lullaby` | Brahms, Wiegenlied Op. 49/4 | 104 BPM, 3/4 |
| | `stomp` | Good King Wenceslas | 108 BPM |
| | `blizzard` | Leontovych, Shchedryk (1914; Carol of the Bells) | 150 BPM, 3/4 |

`random` picks one of the edition's three. Only one edition's tracks fit in
the firmware; the RP2040 knows every edition's choreography and imports only
the module it needs. Every dance reaches its final pose 1.5 s before the music
ends, so Coglet settles before the follow-up session.

## Custom songs

Two sources, danced the same way:

- **My songs** on the Coglet Updater: converted in the browser, stored in the
  song library outside the firmware, kept through updates
  ([Coglet Updater internals](web-flasher.md#my-songs)).
- **The `Music/` folder**: compiled into your own build (below).

### Presets

| Preset | Moves | Style |
|---|---|---|
| energetic | every servo | head bob on every beat (deeper on accents), ear flicks, sway and base turns every bar, eyes on the beat, blinks, mouth on the biggest hits; scales with the song's loudness |
| calm | ears, head (pitch and roll) and base | slow nod on the felt pulse, drifting ears, small sway; **eyelid and both eye servos have their torque released** for the whole song |

Calm songs follow the felt pulse: a 136 BPM ballad that feels like 68 nods at 68.

### The `Music/` folder

1. Put audio files in `CogletESP/Music/`: mp3, wav, flac, m4a, aac, ogg, opus,
   wma, aiff, or a video (mp4, mov, m4v, webm, mkv; its audio is used).
2. `idf.py build`. `tools/coglet_music/build_music.py` converts each file to
   Ogg/Opus (mono, 24 kHz, 60 ms frames, loudness-normalised), cuts it to the
   maximum length with a fade-out, detects tempo, beats, accents, sections
   and bar starts, picks a preset, and compiles it in. Results are cached in
   `build/coglet_music/cache/`.
3. Flash and say "dance to *Night Rain*" or "dance to one of my songs". The
   song name is the file name without extension and tags.

Force the preset or tempo with tags before the extension:

```
Night Rain.calm.mp3
Drop It.energetic.wav
Free Fall.calm.68bpm.m4a
```

Needs ffmpeg with libopus; without it the songs are skipped with a warning and
the build still succeeds. `Music/.gitignore` keeps your songs out of git.
**Do not publish firmware images with music you have no rights to.**

menuconfig, *NMRobotics Coglet Dance*:

| Option | Default | |
|---|---|---|
| Custom songs from the Music folder | on | |
| ffmpeg executable | `ffmpeg` | name or full path; on Windows with forward slashes, e.g. `C:/ffmpeg/bin/ffmpeg.exe` |
| Maximum length per song | 60 s | |
| Opus bitrate | 32 kbps | about 240 KB per minute |
| Flash budget for all custom songs | 400 KB | songs that don't fit are skipped |
| Song library size | 2048 KB | space for songs added from the Coglet Updater |
| Beat timing offset | 20 ms | moves late → lower it, moves early → raise it |

## How it works

ESP (`main/application.cc`):

```
self.coglet.dance(style)
  WaitAck   wait for the one-line reply (TTS stopped, audio idle; 10–20 s max)
  Starting  "prep:<style>" (RP2040 keeps the servos on, goes to the start pose),
            close the audio channel → idle
  Playing   built-in: "dance:<style>", a task plays the track
            custom:   "groove:<preset>:<bpm>", a task plays the song, another
                      sends "gb:<strength><energy><bar>" on every beat, then "groove:end"
  FollowUp  1 s after the music: proactive session with "（跳完舞了）"
```

- A wake word or the button stops the dance at once (`dance:stop`) and the
  user's own conversation starts instead of the follow-up.
- A reminder that falls due during a dance waits for the end and replaces the
  follow-up.
- `AudioService::PlaySound()` takes a cancel flag, so songs stop within ~10 ms.

RP2040 (`RP2040/music.py`): a dance owns every servo (only Calibration Mode is
higher). Sync: `AUDIO_LATENCY_MS = 120` (command to sound) and
`SERVO_LEAD_MS = 100` (moves start early to land on the beat). If the beats
stop for 4 s during a custom song, the dance ends by itself. Afterwards the
default motion limits are restored and the current state is applied again.

## Regenerating the built-in tracks

`tools/coglet_dj/` (Python with numpy and scipy, plus ffmpeg):

```bash
cd tools/coglet_dj
python3 render.py mecha evil cat                    # out/*.ogg, previews, choreography json
python3 export_rp2040.py ../../RP2040/dance_data.py
```

To change only the choreography: edit `choreo.py`, run `choreo_only.py`, then
`export_rp2040.py`. The holiday editions work the same way with `xmas.py` /
`choreo_xmas.py` / `export_xmas_rp2040.py` / `export_xmas_headers.py`, and the
`elf` and `snow` equivalents. The header exporters read `out/approved/`, so
only audio someone has listened to ends up in `main/coglet_sounds/`.
The generated `dance_*.py` files are not edited by hand.
