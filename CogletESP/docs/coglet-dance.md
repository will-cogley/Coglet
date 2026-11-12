# Coglet Music Dance (`self.coglet.dance`)

Ask Coglet to dance ("dance for me", "跳个舞", "play one of my songs") and it will:

1. answer with one short line ("Watch this!");
2. **end the current conversation**;
3. play a song while the RP2040 moves every servo to the beat;
4. **start talking again by itself** afterwards (it sends the cue text "（跳完舞了）")
   and ask how you liked it.

There are two kinds of songs:

| | Built-in tracks | Your own songs (`Music/` folder) |
|---|---|---|
| Music | 3 original ~30 s tracks | any audio file you drop in |
| Dance | hand-written choreography, generated from the same score as the music | automatic: beats are detected at build time and streamed to the RP2040 while the song plays |
| RP2040 files | `music.py` + `dance_data.py` | `music.py` only (no re-upload when you add songs) |

## Built-in tracks

| style | Feel | Tempo / key | Length | Highlights |
|---|---|---|---|---|
| `mecha` | heavy mecha electro | 128 BPM, F minor | 31.5 s | nods on the kick, slow crouch in the build-up, wide eyes + open mouth on the drop, sway and turns |
| `evil` | gloomy gothic | 96 BPM, D harmonic minor | 31.5 s | slow head roll on the bell, heavy nods, ears pressed down on the snare, shudders |
| `cat` | gentle anime cat pop | 120 BPM, C major | 31.0 s | bounces, head tilt + blink on every "nya", alternating ears |
| `random` | one of the three | | | default when the user names nothing |

The eyes dance too: both eyes looking left/right together on the beat, and
crossed / split eyes on accents.

## Your own songs

There are two ways:

* **Web page (easiest):** the *My songs* section of the web flasher
  (`docs/coglet-web-flasher.md`) converts and analyses songs in the browser
  and stores them on Coglet, outside the firmware, so they survive updates.
  No ESP-IDF or ffmpeg needed.
* **`Music/` folder:** songs compiled into your own firmware build, below.

Both kinds of songs work the same way when Coglet dances.

### The `Music/` folder

1. Put audio files in `CogletESP/Music/`: mp3, wav, flac, m4a, aac, ogg, opus,
   wma, aiff, or a video (mp4 / mov / m4v / webm / mkv; its audio track is used).
2. Run `idf.py build` as usual. For each file the build:
   - converts it to the format Coglet plays (Ogg/Opus, mono, 24 kHz, 60 ms frames,
     loudness-normalised, low end trimmed for the small speaker),
     cut to *Maximum length per song* with a fade-out;
   - detects tempo, beats, accents, quiet/loud sections and bar starts;
   - picks a dance preset, **energetic** or **calm**;
   - compiles everything into the firmware.
3. Flash, then ask: "dance to *Night Rain*", or "dance to one of my songs".

The MCP tool lists your songs by name, so the assistant can pick one. The
song name is the file name without extension and tags.

Conversions are cached in `build/coglet_music/cache/`. When nothing changed,
the check takes well under a second and nothing is recompiled.

### Presets

| Preset | What moves | Style |
|---|---|---|
| energetic | every servo | head bob on every beat (deeper on accents), ear flicks, sway + base turns every bar, eyes on the beat, blinks, mouth on the biggest hits; everything scales with the song's loudness |
| calm | ears, head (pitch / roll) and base only | a slow, gentle nod on the felt pulse, ears drifting every other beat, small sway every bar, small base turn every other bar; **eyelid and both eye servos have their torque released** for the whole song |

Calm songs dance on the *felt* pulse: a 136 BPM ballad that feels like 68
nods at 68.

### File name tags

The automatic preset is a best guess (tempo + how punchy the song is). A
heavy, slow-feeling trap song can be guessed "energetic", for example.
Override it, and the tempo if needed, with tags before the extension, in any
order:

```
Night Rain.calm.mp3
Drop It.energetic.wav
Free Fall.calm.68bpm.m4a
```

### menuconfig

`idf.py menuconfig` → **NMRobotics Coglet Dance**

| Option | Default | |
|---|---|---|
| Built-in music dance | on | the whole feature (tool, built-in tracks, Music folder) |
| Custom songs from the Music folder | on | |
| ffmpeg executable | `ffmpeg` | name or full path; on Windows use forward slashes, e.g. `C:/ffmpeg/bin/ffmpeg.exe` |
| Maximum length per song | 60 s | longer songs are cut with a fade-out |
| Opus bitrate | 32 kbps | about 240 KB per minute |
| Flash budget for all custom songs | 400 KB | songs that do not fit are skipped with a warning (the app partition has about this much room) |
| Song library size | 2048 KB | storage for songs added from the web page, at the end of the assets partition |
| Beat timing offset | 20 ms | moves late → lower it, moves early → raise it (no RP2040 upload needed) |

### Requirements

* **ffmpeg with libopus** on the build computer.
  Windows 11: `winget install Gyan.FFmpeg` (or download a "full" build from
  gyan.dev), then open a new ESP-IDF terminal and check that `ffmpeg -version`
  works. If ffmpeg cannot be found, the songs are skipped with a warning and
  the build still succeeds.
* Nothing else: the analysis uses the Python standard library only.

### Copyright

You are responsible for the music you put in the folder. Keep songs you do
not have the rights to for personal use: do not publish firmware images that
contain them. `Music/.gitignore` keeps the folder's contents out of git, so a
public repository only ever contains the empty folder.

## How it works

### ESP side (`application.cc`)

```
MCP self.coglet.dance(style)
  WaitAck    wait for the one-line reply (TTS stop + audio idle; 10-20 s max)
  Starting   CloseAudioChannel -> idle
  Playing    built-in: UART "dance:<style>"; feeder task plays the track
             custom:   UART "groove:<preset>:<bpm>"; feeder task plays the song,
                       beat task sends "gb:<strength><energy><bar>" on every beat
                       and "groove:end" when the song is over
  FollowUp   1 s after the music: StartDeviceSession("（跳完舞了）")
```

* Any wake (wake word, button) while dancing stops it at once: the audio is
  flushed, `dance:stop` is sent, and the user's own conversation starts
  instead of the follow-up.
* A reminder that falls due during a dance waits until the song ends, and
  then replaces the follow-up question.
* `AudioService::PlaySound()` takes an optional cancel flag, so long songs are
  fed packet by packet from a worker task and stop within ~10 ms.
* `uart_send_string()` writes each line in one call, so lines from the main
  loop and the beat task never interleave.

### RP2040 side (`music.py`)

* Priority: **Calibration > dance > MCP action > state / blink / vision / mouth**.
  No torque release while dancing; afterwards the default motion limits are
  restored, released servos are driven again, and the current state is
  re-applied (idle releases torque as usual).
* Built-in tracks follow `dance_data.py` (generated; do not edit by hand).
  Sync: `AUDIO_LATENCY_MS = 120` (command to sound) and `SERVO_LEAD_MS = 100`
  (moves start early so they arrive on the beat).
* Custom songs: `start_groove()`, `groove_beat()`, `groove_end()`. If the ESP
  goes quiet for 4 s mid-song the dance ends by itself.
* `servoclass.Servo.release()` / `hold()` switch one PCA9685 channel fully off
  and back on (used by the calm preset).

## Regenerating the built-in tracks

`tools/coglet_dj/` (numpy, scipy, ffmpeg):

```bash
cd tools/coglet_dj
python3 render.py mecha evil cat       # out/*.ogg, preview mp3s, choreography json
python3 export_rp2040.py ../../RP2040/dance_data.py
```

Then turn `out/<name>.ogg` into `main/coglet_sounds/coglet_dance_<name>.h`
(same layout as the other sound headers). To change only the choreography:
edit `choreo.py`, run `python3 choreo_only.py`, then `export_rp2040.py`.
`tracks.py` also holds `sad`, a solo piano piece (68 BPM, F minor) that is
still in progress and not part of the firmware.
