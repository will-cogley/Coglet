# Coglet Updater internals

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/developer/web-flasher.md) · [Español](../../es/developer/web-flasher.md) · [日本語](../../ja/developer/web-flasher.md)

The Coglet Updater (<https://will-cogley.github.io/Coglet/>) is one static page
in `tools/web_flasher/`: `index.html`, `coglet_i18n.js` (translations) and
`coglet_songs.js` (song conversion). It uses
[esptool-js](https://github.com/espressif/esptool-js) 0.6.1 and Web Serial, so
it needs a Chromium-based desktop browser on HTTPS or `localhost`; songs also
need WebCodecs (Chrome / Edge 94+). User instructions:
[Getting started](../user/getting-started.md).

## Updating

- The page refuses anything that isn't an ESP32-S3. Each part is checked
  against the MD5 in the manifest before and after writing; flash mode,
  frequency and size are kept as built.
- It writes the bootloader, partition table, OTA data, app and assets image,
  never NVS, the settings sector or the song library. **Fresh install** erases
  the whole chip first.
- Every button asks for the port before downloading anything (browsers only
  show the port list right after a click). The port choice is remembered by
  USB id. The list only shows the USB-serial chips Coglet uses;
  **Show all ports** lists everything.
- If the USB link loses data, it writes again at the next lower speed
  (921600 → 460800 → 115200) and remembers what worked.
- After writing it restarts Coglet, shows the boot log and reads it:

| Coglet's log says | The page shows |
|---|---|
| `RP2040 did not answer` | "One more step": the servo board setup card |
| `sending N of M files` | updating the servo board, keep it plugged in |
| `RP2040 running again` / `up to date` | all set |
| `RP2040 update failed` / `did not answer within` | retried at the next start; the setup card is the fallback |

### Check my Coglet

Reads the partition table (0x8000), `otadata` (which slot boots) and the first
1 KB of that app slot. From ESP-IDF's app description (version) and Coglet's
own description (`main/coglet_app_desc.h`: magic `COGLET`, edition, build
commit) it reports: update available, up to date, newer (test build), the
user's own build (`local`), another build of the same version, firmware from
before v2.3.0, or no firmware. It also selects the Coglet's own edition, then
restarts Coglet and reports on the servo board.

### One-time RP2040 setup

For RP2040s set up before automatic updates. With the mode switch on RP2040,
the page stops the running program through MicroPython's raw REPL, writes
every file as `<name>.tmp`, checks the sizes, renames them, writes the bundle
id to `coglet_bundle.txt` and soft-reboots. Nothing is replaced until every
file is written. It needs MicroPython already on the RP2040 (every kit ships
with it).

## Settings

One 4 KB sector right before the song library (`main/coglet_settings.h`):
`CGST`, version, length, CRC-32 (zlib), then `key=value` lines:

| Key | Values |
|---|---|
| `wake_word` | English phrase, lowercase a–z, `'` and spaces |
| `threshold` | 1–99 % (the page offers 1–50) |
| `startup`, `reminder` | `mecha`, `evil`, `cat`, `christmas`, `elf`, `snowman` |
| `aec` | `on` / `off` |

Only values that differ from the selected edition's defaults are saved; the
rest follows the firmware (`make_manifest.py` publishes the defaults in
`manifest.json`). Missing or invalid values fall back to menuconfig, also after
`idf.py flash`. The MultiNet model turns the wake word into phonemes itself; if
it can't, Coglet keeps its built-in wake word and logs
`Wake word "..." from settings can't be used`.

```
I (900) CogletSettings: settings: wake word "hey coglet", threshold 3, startup cat, reminder evil, aec on
```

## My songs

The browser decodes each file and finds the beats with the same analysis as
`tools/coglet_music/build_music.py` (`coglet_songs.js` is a port and gives the
same beats). It levels the song to −14 LUFS with a limiter, cuts it at 60 s
with a fade-out, and encodes Ogg/Opus (mono, 24 kHz, 60 ms frames, 32 kbps)
with WebCodecs.

The **song library** is the last 2 MB of the `assets` partition
(0xE00000–0x1000000), which the assets image never reaches; `make_manifest.py`
refuses a build whose assets would. Layout (`main/coglet_music.h`): sector 0
holds the `CGML` header and up to 32 entries (name, preset, BPM, length,
offsets, CRC-32); each song's Ogg data and beat table start on their own 4 KB
sector. The list is written last and each song has its own CRC, so an
interrupted save keeps the previous songs and a damaged song is skipped.

```
I (5120) CogletMusic: song library: 3 songs at assets+0x600000
```

## Languages

English, German, Spanish and Japanese. The page follows the browser language
(else English); the 🌐 menu switches and remembers it; `?lang=de|es|ja|en`
forces one. The English text stays in `index.html` (`data-i18n="key"`), the
other languages are dictionaries in `coglet_i18n.js`; script messages use
`t("key", {name: value})` with plural rules and local number formats. The
device log stays in English.

To add a language: add it to `LANGS`, add a dictionary with every key (same
`{placeholders}` and markup), and an `<option>` to the 🌐 menu.

## Look

- *Appearance*: light, dark, day and night (light 7:00–19:00), or the browser
  setting.
- December 1 to January 6: a Christmas look drawn in SVG and CSS (garland,
  lights, falling stars or snowflakes). A button turns it off for the season;
  `?season=christmas|plain` forces it. Nothing moves with *reduce motion*.
- Accessibility: keyboard only, labelled controls, announced progress and
  errors (starting with "Error:"), WCAG AA contrast, 200 % zoom.

## Testing locally

Serve `index.html`, `coglet_i18n.js` and `coglet_songs.js` next to a
`firmware/` folder made by `make_manifest.py` from your build (and `rp2040/`
for the one-time setup), on `localhost`. For the other editions also run
`make_manifest.py --edition christmas` (or `elf`, `snowman`) on that build;
without them the page shows no edition choice.
