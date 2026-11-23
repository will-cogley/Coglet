# Building the firmware

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/developer/build.md) · [Español](../../es/developer/build.md) · [日本語](../../ja/developer/build.md)

## ESP-IDF version: v5.5.3

Use **ESP-IDF v5.5.3**, nothing older or newer. The release builds run in the
official `espressif/idf:v5.5.3` container (`.github/workflows/firmware.yml`),
and `dependencies.lock` pins the managed components for that version. Another
version may build, but it is not what Coglets run.

### Install

**Windows:** run the [ESP-IDF Windows installer](https://dl.espressif.com/dl/esp-idf/)
and choose **v5.5.3**. Build from the *ESP-IDF 5.5 PowerShell* (or CMD) it
installs.

**Linux / macOS:**

```bash
git clone -b v5.5.3 --recursive https://github.com/espressif/esp-idf.git ~/esp/esp-idf-v5.5.3
cd ~/esp/esp-idf-v5.5.3
./install.sh esp32s3
. ./export.sh          # in every new terminal
```

Check: `idf.py --version` prints `ESP-IDF v5.5.3`.

Optional: **ffmpeg** with libopus, only for songs in the `Music/` folder
([Dances and songs](dance.md#the-music-folder)). Windows: `winget install Gyan.FFmpeg`.

## Build and flash

```bash
cd CogletESP
idf.py build
idf.py -p <port> flash monitor
```

- The target (esp32s3), board type and every Coglet option are in the
  committed `sdkconfig`. **Do not run `idf.py set-target`**: it regenerates
  `sdkconfig` from the defaults and drops Coglet's configuration.
- Plug into the top (programming) USB-C port, with the mode switch on **ESP**.
- `<port>` is for example `COM5` on Windows, `/dev/ttyACM0` or `/dev/ttyUSB0`
  on Linux, `/dev/cu.usbmodem…` on macOS.
- `idf.py flash` keeps Wi-Fi, pairing, reminders, the settings saved from the
  Coglet Updater and the songs added there. `idf.py erase-flash` clears all of it.
- The first build downloads the managed components; later builds are
  incremental.

Board type: **NMRobotics Coglet (CogNog V3.0 PCB)**
(`CONFIG_BOARD_TYPE_COGNOG_V3`), board files in
[`main/boards/cognog-v3/`](../../../main/boards/cognog-v3). It reports itself as
`cognog-v3`. Firmware up to 2.3.x used the generic board type
`bread-compact-wifi-s3cam`, which still exists for old local configurations.

## Editions

Standard, Christmas, Elf and Snowman differ only in the three built-in dances
and the default startup and reminder sounds. Each is an overlay on `sdkconfig`,
built in its own folder:

```bash
idf.py -B build-christmas -D SDKCONFIG=build-christmas/sdkconfig \
       -D SDKCONFIG_DEFAULTS="sdkconfig;sdkconfig.christmas" build
idf.py -B build-christmas -p <port> flash
```

Use `sdkconfig.elf` / `build-elf` or `sdkconfig.snowman` / `build-snowman` the
same way. Or pick it in menuconfig: *NMRobotics Coglet Dance → Firmware edition*.

## menuconfig

`idf.py menuconfig`. The Coglet options:

| Menu | Options |
|---|---|
| Xiaozhi Assistant | Board type, wake word (default "hello coglet"), Device-side AEC (`USE_DEVICE_AEC`, `COGLET_AEC_DEFAULT_OFF`, `COGLET_AEC_REF_DELAY_MS`), microphone level log (`COGLET_MIC_DIAG_LOG`) |
| NMRobotics Coglet Reminder | Speak the reminder after the chime; time zone (automatic from the server, or a POSIX TZ string) |
| NMRobotics Coglet RP2040 | Update the RP2040 program automatically |
| NMRobotics Coglet Dance | Built-in dances, firmware edition, `Music/` folder songs, song library size, beat timing offset |
| NMRobotics Coglet Sounds | Default startup and reminder sounds |

Values saved from the Coglet Updater (wake word, sensitivity, sounds, AEC)
take priority over menuconfig until they are cleared there with **Use defaults**.

## Firmware version

The version is `PROJECT_VER` in `CogletESP/CMakeLists.txt` (release builds
take it from the git tag). Keep it plain numbers such as `2.3.2`, optionally
with a `-suffix`: the OTA check compares it number by number.

## Changing the RP2040 program

The RP2040 runs MicroPython; its program is in [`RP2040/`](../../../RP2040).
Every ESP build packs these files into the firmware, and the ESP sends any
changed file to the RP2040 after boot ([Architecture](architecture.md#rp2040-updates)).
So the normal way to change the RP2040 is to edit the files and flash the ESP.

With Thonny (mode switch on **RP2040**) you can upload files directly while
experimenting. The ESP then sees a different bundle on its next boot and
puts its own copy back, so either keep the ESP firmware and `RP2040/` from
the same commit, or turn off *NMRobotics Coglet RP2040 → Update the RP2040
program automatically* while you experiment.

Note: any change to an RP2040 file, even a comment, makes every Coglet
re-send that file on its next update.

## Logs

`idf.py monitor` shows the ESP log; the Coglet Updater's **Show device log**
shows the same. The RP2040 prints to its own USB serial (mode switch on
RP2040). Useful tags: `CogletRp2040` (servo board updates), `CogletDance`,
`CogletReminder`, `CogletSettings`, `CogletMusic`, `CogletAutoAwake`.
