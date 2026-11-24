# Architecture

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/developer/architecture.md) · [Español](../../es/developer/architecture.md) · [日本語](../../ja/developer/architecture.md)

```
 xiaozhi.me server ──Wi-Fi── ESP32-S3 ──UART1 115200── RP2040 ──I²C── PCA9685 ── 9 servos
   (speech, LLM)            voice, wake word,          MicroPython   └─UART0 921600── Grove Vision AI V2
                            camera, MCP tools,
                            reminders, dances
```

The ESP32-S3 runs the [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
firmware with Coglet additions. It decides **what** Coglet does and tells the
RP2040 in short text lines. The RP2040 decides **how** the servos move.

## ESP32-S3 firmware

| Where | What |
|---|---|
| `main/application.cc` | Device states, voice sessions, Coglet's boot Auto-Awake, dance and reminder flows; sends every state change to the RP2040 |
| `main/boards/cognog-v3/` | Board: pins, camera, red LED, Coglet's MCP tools |
| `main/uart_component.cc` | UART1 link to the RP2040 |
| `main/coglet_rp2040_sync.cc` | Keeps the RP2040 program up to date |
| `main/coglet_reminder.cc` | Reminders (NVS) |
| `main/coglet_settings.cc` | Settings saved from the Coglet Updater |
| `main/coglet_music*.{h,cc}`, `main/coglet_sounds*` | Songs, built-in dance tracks, startup and reminder sounds |
| `main/audio/` | Audio pipeline, wake word, software AEC reference |

### Device states

`starting → wifi_configuring / activating → idle ⇄ connecting → listening ⇄ speaking → idle`

The red LED is on only in `listening`. In `idle` the RP2040 settles into its
sleep pose and releases servo torque.

**Boot Auto-Awake:** a few seconds after the startup sound, Coglet opens one
listening session by itself. It waits (at most 2 minutes) while the RP2040 is
being updated, so a transfer never overlaps the first conversation. It runs
once per boot; if it fails, Coglet stays on the wake word.

**Proactive sessions:** after a dance and when a reminder is due, Coglet opens
a session by itself and sends a short cue text as if it were a detected wake
word: `（跳完舞了）` ("finished dancing") or `（有提醒到点了）` ("a reminder is
due"). The MCP tool descriptions tell the LLM what to do with these cues. They
stay in Chinese on purpose: the LLM understands them in every language, and
they must stay at most 13 characters for xiaozhi.me.

## UART protocol (ESP → RP2040)

One command per line, ending in `\r\n`. Each line is written in one call, so
lines from different tasks never interleave.

| Line | Meaning |
|---|---|
| `idle`, `listening`, `speaking`, `thinking`, `configuring` … | Device state |
| `neutral`, `happy`, `sad`, `angry`, `surprised`, `sleepy`, `silly`, `confused`, `cool`, `loving`, … | Emotion sent by the LLM with its reply |
| `action:shake_head` / `blink` / `left_ear` / `right_ear` / `ears` | One-shot move from an MCP tool (three cycles) |
| `dance:<style>` | Start a built-in dance, e.g. `dance:mecha` |
| `dance:stop` | Stop any dance now |
| `prep:<style>` / `prep:groove-<preset>` | The conversation is closing for a dance: keep the servos powered and move to the dance's start pose instead of sleeping (ends when the dance starts, on `dance:stop`, or after 15 s) |
| `groove:<energetic\|calm>:<bpm>` | Start dancing to a custom song |
| `gb:<s><e><b>` | One beat of a custom song: accent 0–9, section energy 0–9, bar start 0/1 |
| `groove:end` | Custom song finished |
| `upd:…` | RP2040 update protocol (below) |

The RP2040 maps states and emotions to animations in `animation.state_map`;
unknown lines are ignored. Emotions don't stop the mouth: only state lines
(`idle`, `listening`, `thinking`, `neutral`, …) end the speaking animation.

## RP2040 program

| File | Role |
|---|---|
| `main.py` | Tiny launcher: finishes an interrupted update, runs `app.py`, falls back to recovery mode if `app.py` can't start |
| `app.py` | Main loop: UART, switches, servo ownership, torque release |
| `animation.py` | Servo table, poses, state animations, blinking, speaking mouth, MCP actions |
| `servoclass.py` | PCA9685 driver and `Servo` with speed and acceleration limits |
| `vision.py` | Grove Vision AI face tracking (eyes and neck pitch, base yaw takes over at the eye limits) |
| `music.py`, `dance_*.py` | Dance player and generated choreographies |
| `coglet_updater.py` | Receives updates from the ESP |

Who owns the servos, highest first:

1. **Calibration Mode** (switch): everything in the calibration pose; the
   Servo test button wiggles ±10°.
2. **Dance**
3. **MCP action** (`action:…`)
4. **State animation**, blinking, face tracking (only when not idle and the
   Face-track switch is on), speaking mouth.

After the idle pose has settled, the RP2040 waits 500 ms and raises PCA9685
nOE, which releases all torque. Any other state switches the servos back on
one by one ([Power](power.md)).

## RP2040 updates

`tools/rp2040_bundle/build_bundle.py` packs `RP2040/*.py` into the ESP
firmware on every build; the bundle id is a hash of all files. About 5 s after
boot the ESP asks for the RP2040's bundle id. If it differs, it asks for each
file's size and CRC and sends only the changed files:

```
ESP → upd:ver?                       RP → upd:ver:<id>|none
ESP → upd:crc?:<name>                RP → upd:crc:<name>:<size>:<crc32> | upd:crc:<name>:none
ESP → upd:begin:<id>:<files>         RP → upd:ready
ESP → upd:file:<name>:<size>:<crc>   RP → upd:ok:f
ESP → upd:d:<seq>:<base64>           RP → upd:ok:<seq>      (repeats are re-acknowledged)
ESP → upd:end                        RP → upd:ok:e | upd:err:<why>
ESP → upd:commit                     RP → upd:done, then restarts
ESP → upd:abort                      staged files are deleted
```

The RP2040 writes `<name>.new` files, checks size and CRC-32, and renames them
only when all have arrived. The list of files being renamed is written first,
so a power cut halfway is finished at the next boot. The servos are released
during a transfer. A full transfer takes about half a minute, a usual one a
few seconds.

ESP log (tag `CogletRp2040`): `RP2040 up to date`, `RP2040 updated (bundle …)`,
`RP2040 did not answer: it needs the one-time setup from the web flasher`,
`RP2040 update failed … retried on the next boot`.

Older RP2040s without the updater need the one-time setup from the Coglet
Updater once ([Coglet Updater internals](web-flasher.md#one-time-rp2040-setup)).

## Reminders

Up to 12 one-off reminders of at most 120 bytes each, stored in NVS as UTC
times, so a time zone change never moves a saved reminder. The time zone comes
from the server's `timezone_offset` (OTA check) or a POSIX TZ string from
menuconfig. When a reminder is due and Coglet is idle (a dance finishes first),
Coglet plays the reminder sound, then opens a proactive session in which the
LLM calls `self.coglet.reminder.last_due` and says it in one sentence.

## Stored data

| Data | Where | Kept by updates |
|---|---|---|
| Wi-Fi, pairing, reminders | NVS partition | yes |
| Settings (`CGST` sector) | 4 KB before the song library, in `assets` | yes |
| Song library (`CGML`) | last 2 MB of `assets` (0xE00000–0x1000000) | yes |
| App, assets image | `ota_0` / `ota_1`, `assets` | replaced |

Partition table: `partitions/v2/16m.csv`.
