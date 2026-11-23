# Device-side echo cancellation (AEC)

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/developer/audio-aec.md) · [Español](../../es/developer/audio-aec.md) · [日本語](../../ja/developer/audio-aec.md)

AEC lets the user talk over Coglet: it keeps listening while it speaks and can
be interrupted without the wake word. Users switch it with **Talk over Coglet**
on the Coglet Updater.

## How it works

The microphone and the MAX98357A amplifier are on two separate I2S ports, and
there is no hardware loopback of the speaker signal, so the stock device-side
AEC can't run. Coglet builds the reference in software, on the ESP32-S3,
without server-side AEC:

1. Each time the speaker I2S TX DMA has sent a 10 ms block, its `on_sent`
   callback sees the PCM that actually went to the amplifier.
2. Each time the microphone I2S RX DMA has received a 15 ms block, `on_recv`
   sees it as well.
3. Both callbacks are timestamped with `esp_timer`. `SoftwareAecReference`
   smooths the timestamps with a clock tracker, pairs every microphone sample
   with the speaker sample played at the same moment, and resamples 24 kHz to
   16 kHz with anti-aliasing.
4. `Read()` returns interleaved `[mic, ref]`, the `MR` format of the esp-sr
   AFE AEC.
5. With AEC on, every wake path uses **realtime** listening mode, including
   boot Auto-Awake.

With AEC off, nothing of this runs: the audio path is the same as in a build
without AEC.

## Configuration

| Option | Published firmware | |
|---|---|---|
| `CONFIG_USE_DEVICE_AEC` | on | AEC compiled in |
| `CONFIG_COGLET_AEC_DEFAULT_OFF` | on | off until the user enables it (settings key `aec=on`) |
| `CONFIG_COGLET_AEC_REF_DELAY_MS` | 0 | reference offset, −10…20 ms |
| `CONFIG_USE_SERVER_AEC` | off | must stay off: the two exclude each other |

The setting is read once at boot (`CogletSettings::DeviceAec()`), so changing
it restarts Coglet. If the reference can't be allocated, Coglet logs
`Device AEC unavailable on this boot` and listens as without AEC.

## Checking it on the device

Boot log:

```
NoAudioCodec: [AEC-REF] software loopback ENABLED: mic 16000 Hz (slot 0/2), speaker 24000 Hz ...
CogletAutoAwake: BOOT_LISTENING: mode=realtime
CogletSettings: Device AEC: on (from settings)
```

`AfeAudioProcessor` must not say `no reference channel`.

With *Coglet: log microphone levels every second* (`CONFIG_COGLET_MIC_DIAG_LOG`)
there is one line per second:

```
[MIC] mode=aec-ref ... | [AEC-REF] refPeak=... offset=..us missing=.. late=.. micOvr=.. refOvr=.. resync=a/b torn=..
```

| Field | Healthy |
|---|---|
| `refPeak` | clearly above 0 while Coglet speaks, 0 in silence |
| `offset` | steady within a few milliseconds (steady matters more than the value) |
| `missing` / `late` | barely grow |
| `micOvr` | grows when switching between wake word and conversation: normal |
| `resync` | 1 each at boot, then stable |
| `torn` | always 0 |

Listening test: let Coglet give a long answer and interrupt it; it should stop
and understand you. While you stay silent, it must not interrupt itself.

## Aligning the reference

1. Enable *Enable Audio Debugger* in menuconfig and set your computer's
   `IP:8000`.
2. Run `python scripts/audio_debug_server.py` on the computer (16 kHz, 2
   channels by default).
3. Let Coglet speak, then open the WAV in Audacity: left is the microphone,
   right the reference.
4. The echo in the microphone should come slightly **after** the reference
   (0–3 ms).
   - Echo **before** the reference: set the reference delay negative (−1, −2, …).
   - Echo more than 10 ms late: the timestamps are off; please report it with
     the recording.

## Known limits

- **Servo noise** is not echo: gear noise while the mouth, ears and neck move
  can't be cancelled and may interrupt Coglet.
- **Loud volume**: distortion from the small speaker and the case isn't fully
  cancelled. AEC works best at 50 % volume or lower.
- With AEC the AFE's local VAD is off (as on the upstream ESP-Box boards); the
  server decides where speech starts and ends.

## Files

- `main/audio/codecs/software_aec_reference.{h,cc}`: time alignment, IDF-free
- `main/audio/codecs/no_audio_codec.{h,cc}`: DMA callbacks, `EnableSoftwareAecReference()`, `MR` output
- `main/boards/cognog-v3/cognog_v3_board.cc`: starts the reference when AEC is on
- `main/audio/processors/afe_audio_processor.cc`: falls back without a reference channel
- `main/application.cc`: realtime mode for Auto-Awake with AEC
