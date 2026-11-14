# Coglet Web Flasher, automatic RP2040 updates, Settings and "My songs"

Update Coglet, change its wake word and reminder sound, and add your own songs
from the browser, with no ESP-IDF, Thonny or ffmpeg install. Flashing the ESP32-S3 is all users ever need to do:
the ESP then keeps the RP2040 (servo board) up to date by itself.

**Page:** https://will-cogley.github.io/Coglet/

## For users

1. Open the page in **Chrome or Edge** on a computer (Windows, macOS, Linux).
2. Plug Coglet in through the **top (programming) USB-C port** with a data cable.
   Leave the board switch on **ESP** (factory setting).
3. Click **Connect & Update**, pick Coglet in the list, and wait for **Done**.

The port list only shows the USB-serial chips Coglet uses (Espressif, WCH
CH34x, Silicon Labs CP210x, FTDI, Prolific; the RP2040 setup shows only
Raspberry Pi devices). **Advanced options → Show all ports** lists everything.
The page remembers the choice by USB id, also after replugging or reloading;
a port that turns out wrong (not an ESP32-S3, or no answer) is forgotten so
the next try asks again.

Wi-Fi settings, the xiaozhi.me pairing, reminders, and the settings and songs
saved on the page are kept: only the bootloader, partition table, OTA data,
app and assets images are written, never the NVS partition, the settings
sector or the song library.
**Advanced options → Fresh install** erases the whole chip first (Wi-Fi,
pairing, settings and songs then need to be set up again).

After an update the page restarts Coglet, shows its boot log and reads it:

| Coglet's log says | The page shows |
|---|---|
| `RP2040 did not answer` | "One more step": the servo board setup card is highlighted and gets the focus |
| `sending N files` | Coglet is updating its servo board, keep it plugged in |
| `RP2040 updated` / `up to date` | All set |
| `RP2040 update failed` | It retries on the next start; the setup card is the fallback |

**Show device log** opens the log at any time and **Copy log** copies it for
support requests.

The page states plainly that it installs the official firmware, so people
who build their own (songs in `Music/`, menuconfig changes) know their build
is replaced; songs added under *My songs* are not affected.

### One-time RP2040 setup

Coglets whose RP2040 was set up before automatic updates need this once:

1. Unplug Coglet, set the board switch to **RP2040**, plug it back in.
2. Click **Set up RP2040** and choose the RP2040's port.
3. When it says **Done**, unplug, set the switch back to **ESP**, plug in,
   and click **Check Coglet**: the page restarts Coglet and confirms that the
   servo board answers.

The page stops the running program through MicroPython's raw REPL, writes
every file as `<name>.tmp`, checks the sizes, renames them into place,
records the bundle id in `coglet_bundle.txt` and soft-reboots the RP2040.
Nothing is replaced until every file has been written.

## Settings

The *Settings* card changes, without rebuilding:

| Setting | Values | Replaces menuconfig |
|---|---|---|
| Wake word | English words, e.g. `hey coglet` (lowercase letters, `'` and spaces, 3-40 characters) | Custom Wake Word |
| Wake-up sensitivity | 1-50 (lower wakes up more easily) | Custom Wake Word Threshold |
| Startup sound | Mecha, Evil, Cat | Startup Sound |
| Reminder sound | Mecha, Evil, Cat | Reminder Sound |

The wake word is plain text: the MultiNet model on Coglet turns it into
phonemes itself, so any English phrase works without a list. `hello coglet`
keeps its extra accent variants (`main/audio/wake_words/custom_wake_word.cc`).
If the model can't use a phrase (an odd spelling it can't turn into
phonemes), Coglet falls back to the firmware's own wake word and logs
`Wake word "..." from settings can't be used`; the page shows that too, so
Coglet can always still be woken up. All three startup and all three
reminder sounds are in the firmware (about 40 KB more than one of each), so
switching needs no rebuild.

Settings are one 4 KB sector right before the song library
(`main/coglet_settings.h`): `CGST`, version, length, CRC-32, then
`key=value` lines. Missing or invalid values fall back to the menuconfig
defaults, which `make_manifest.py` publishes in `manifest.json` so the page
can show them. Firmware updates never write there. At boot:

```
I (900) CogletSettings: settings: wake word "hey coglet", threshold 3, startup cat, reminder evil
```

## My songs

The *My songs* card adds songs without building firmware:

1. **Add songs**: choose or drop audio/video files. The browser decodes each
   one, finds the beat with the same analysis as `tools/coglet_music/build_music.py`
   (`tools/web_flasher/coglet_songs.js` is a port of it and gives the same
   beats), levels it to -14 LUFS with a limiter, cuts it at 60 s with a
   fade-out, and encodes Ogg/Opus (mono, 24 kHz, 60 ms frames, 32 kbps) with
   WebCodecs. Name and dance style (automatic / energetic / calm) can be
   changed before saving; `.calm` / `.energetic` in the file name preset it.
2. **Save to Coglet** writes the new songs and the song list over USB.
   **Show songs on Coglet** lists what is stored, to remove songs.

Songs live in the **song library**: the last 2 MB of the `assets` partition
(`0xE00000`-`0x1000000` with the 16 MB layout), which the assets image never
reaches. `make_manifest.py` refuses to publish a build whose assets would reach
into it and tells the page where it is (`songs` in `manifest.json`). Size:
menuconfig **NMRobotics Coglet Dance → Song library size** (`0` turns it off).

Layout (`main/coglet_music.h`): the first 4 KB sector holds a header and up
to 32 entries (name, preset, BPM, length, offsets, CRC-32 of the song's
data); each song's Ogg data and beat table start on their own 4 KB sector.
Adding a song writes its sectors and then the list sector; removing one
rewrites only the list. When the free space is split up, the page reads the
songs that stay and packs them. The list is always written last, and each song
has its own CRC, so an interrupted save leaves the previous songs usable and
a damaged song is skipped without losing the others.

At boot the firmware (`main/coglet_music_library.cc`) reads the library
through the assets partition's existing memory mapping and adds the songs to
the dance tool next to the `Music/` folder songs:

```
I (5120) CogletMusic: song library: 3 songs at assets+0x600000
I (5121) CogletMusic:   "Night Rain" calm 68 BPM, 31 s
```

## Automatic RP2040 updates

The ESP firmware carries the RP2040 program. `tools/rp2040_bundle/build_bundle.py`
packs `CogletESP/RP2040/*.py` into the firmware on every build. The bundle id
is a hash of all files, so any change to any RP2040 file means a new id.

About 5 s after boot the ESP asks the RP2040 for its bundle id over the
existing UART link (`main/coglet_rp2040_sync.cc`). If the id differs, the ESP
sends every file:

* The RP2040 (`coglet_updater.py`) writes each file as `<name>.new`, checks
  its size and CRC-32, and only renames the files over the old ones once all
  of them have arrived.
* The list of files being renamed is written first, so if the power is cut
  halfway through, the next boot finishes the job.
* Each piece is acknowledged and resent if needed. If the transfer fails,
  the RP2040 keeps its old program and the ESP tries again on the next boot.
* The transfer takes roughly half a minute. The servos relax during it, then
  the RP2040 restarts and the ESP re-sends the current state.

The RP2040 is organised so that a broken update can't lock it out:

| File | Role |
|---|---|
| `main.py` | Tiny launcher. Finishes an interrupted update, runs `app.py`, and if `app.py` fails to start, stays in recovery mode so the ESP can send a working version. |
| `coglet_updater.py` | The receiver. |
| `app.py` | Coglet's program (formerly `main.py`). |
| `coglet_bundle.txt` | Id of the installed bundle. |

ESP log lines (tag `CogletRp2040`):

* `RP2040 updated (bundle ..., N s)` / `RP2040 up to date`
* `RP2040 did not answer: it needs the one-time setup from the web flasher`
* `RP2040 update failed ... retried on the next boot`

Turn it off in menuconfig: **NMRobotics Coglet RP2040 → Update the RP2040
program automatically**.

For developers using Thonny: upload all RP2040 files as before. The ESP
will see a different bundle id on the next boot and re-send its own copy,
so keep the ESP firmware and the RP2040 folder from the same commit (or turn
the option off while experimenting).

## For maintainers

### One-time setup
In the GitHub repository (admin rights needed):

1. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. **Settings → Environments → github-pages → Deployment branches and tags →
   Add deployment branch or tag rule → Ref type: Tag, pattern `v*`**.
   By default only `main` may deploy the page, so without this rule a
   release tag builds fine but its deploy job is rejected ("not allowed to
   deploy to github-pages due to environment protection rules").

### Publishing a release
Push a version tag:

```bash
git tag v2.1.0
git push origin v2.1.0
```

The **Firmware** workflow (`.github/workflows/firmware.yml`):

1. builds the firmware in the official `espressif/idf:v5.5.3` container,
   with the repository's `sdkconfig` (this also packs the RP2040 program);
2. copies every flash part listed in `build/flasher_args.json` and writes
   `firmware/manifest.json` (offsets, sizes, MD5, song library location,
   link to the release notes), using `tools/web_flasher/make_manifest.py`;
3. deploys the page (`index.html`, `coglet_songs.js`), the firmware and the
   RP2040 files (for the one-time setup) to GitHub Pages;
4. attaches `coglet-firmware-<version>.zip` to the GitHub release. The zip
   contains the parts and an esptool command line for manual flashing.

You can also start the workflow by hand from the **Actions** tab. That builds
and deploys a `dev-<commit>` version without creating a release.

### How the page works
`tools/web_flasher/index.html` is a single static page. It uses
[esptool-js](https://github.com/espressif/esptool-js) 0.6.1 (from jsDelivr) for the
flashing protocol and CryptoJS (from cdnjs) for MD5 checks. Before flashing,
each part is checked against the manifest's MD5, and the flash writes are
verified the same way. Flash mode, frequency and size are kept as built. The
page refuses to flash anything that isn't an ESP32-S3.

### Accessibility
The page works with a keyboard alone (skip link, visible focus, logical tab
order) and with screen readers: every control is labelled, progress and
results are announced (errors at once, and they start with "Error:" so they
never rely on colour), and after an update the focus moves to the next thing
to do. Text contrast meets WCAG AA in the light and dark themes, the layout
works at 200% zoom and on narrow screens, and nothing moves for people who
turned on "reduce motion". The switch pictures have text equivalents.

### Limits
* Web Serial only works in Chromium-based desktop browsers, on HTTPS or
  `localhost`. Converting songs also needs WebCodecs (Chrome / Edge 94+).
* Local testing: copy `index.html` **and** `coglet_songs.js` next to the
  `firmware/` and `rp2040/` folders.
* The published firmware is the repository's default build. Custom builds
  (own songs in `Music/`, menuconfig changes) still need ESP-IDF.
* The one-time RP2040 setup needs MicroPython already on the RP2040, which
  every Coglet kit ships with.
