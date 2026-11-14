#!/usr/bin/env python3
"""Collect the firmware parts of an ESP-IDF build for the Coglet web flasher.

Reads build/flasher_args.json (written by `idf.py build`), copies every flash
part into <site>/firmware/ and writes <site>/firmware/manifest.json, which the
web page (index.html) uses to flash each part at its own offset.

Only the parts the build flashes are written (bootloader, partition table,
OTA data, app, assets). The NVS partition, where Wi-Fi credentials, the
xiaozhi.me pairing and reminders live, is never part of the image, so an
update keeps them. Neither is the song library at the end of the assets
partition (songs added on the web page): the manifest tells the page where it
is, and the build is refused if the assets image would reach into it.

usage: make_manifest.py --build CogletESP/build --site site
                        [--version v1.2.3] [--commit abc1234] [--repo owner/name]
                        [--release-dir release]
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import struct
import sys
import zipfile

NVS_OFFSET = 0x9000
NVS_SIZE = 0x4000
DEFAULT_LIBRARY_KB = 2048


def read_partitions(build):
    """Partitions from build/partition_table/partition-table.bin, by label."""
    path = os.path.join(build, "partition_table", "partition-table.bin")
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, "rb") as f:
        data = f.read()
    for i in range(0, len(data) - 31, 32):
        entry = data[i:i + 32]
        if entry[:2] != b"\xaa\x50":
            break
        _, ptype, subtype, offset, size, label, _ = struct.unpack("<HBBII16sI", entry)
        out[label.split(b"\0")[0].decode("ascii", "replace")] = (offset, size)
    return out


SETTINGS_SIZE = 4096


def settings_defaults(build):
    """The firmware's own values, shown on the page when nothing was saved."""
    out = {"wake_word": "hello coglet", "threshold": 5, "startup": "mecha", "reminder": "mecha",
           "custom_wake_word": True}
    try:
        with open(os.path.join(build, "config", "sdkconfig.json"), encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return out
    if cfg.get("CUSTOM_WAKE_WORD"):
        out["wake_word"] = cfg["CUSTOM_WAKE_WORD"]
    if cfg.get("CUSTOM_WAKE_WORD_THRESHOLD"):
        out["threshold"] = int(cfg["CUSTOM_WAKE_WORD_THRESHOLD"])
    for name in ("mecha", "evil", "cat"):
        if cfg.get("COGLET_BOOT_SOUND_" + name.upper()):
            out["startup"] = name
        if cfg.get("COGLET_REMINDER_SOUND_" + name.upper()):
            out["reminder"] = name
    out["custom_wake_word"] = bool(cfg.get("USE_CUSTOM_WAKE_WORD", True))
    return out


def library_kb(build):
    """CONFIG_COGLET_MUSIC_LIBRARY_KB of this build (0 when the feature is off)."""
    path = os.path.join(build, "config", "sdkconfig.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return DEFAULT_LIBRARY_KB
    if not cfg.get("COGLET_MUSIC", True) or not cfg.get("COGLET_DANCE", True):
        return 0
    return int(cfg.get("COGLET_MUSIC_LIBRARY_KB", DEFAULT_LIBRARY_KB))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--site", required=True)
    ap.add_argument("--version", default="dev")
    ap.add_argument("--commit", default="")
    ap.add_argument("--repo", default="", help="owner/name on GitHub, for the release notes link")
    ap.add_argument("--release-dir", help="also write a zip of the parts here")
    args = ap.parse_args(argv)

    with open(os.path.join(args.build, "flasher_args.json"), encoding="utf-8") as f:
        flasher = json.load(f)

    chip = flasher.get("extra_esptool_args", {}).get("chip", "esp32s3")
    settings = flasher.get("flash_settings", {})
    out_dir = os.path.join(args.site, "firmware")
    os.makedirs(out_dir, exist_ok=True)

    songs = None
    settings = None
    assets = read_partitions(args.build).get("assets")
    kb = library_kb(args.build)
    if assets and kb > 0:
        start = assets[0] + assets[1] - kb * 1024
        songs = {"offset": start, "size": kb * 1024}
    if assets:
        # main/coglet_settings.h: the sector right before the song library
        settings = {"offset": assets[0] + assets[1] - kb * 1024 - SETTINGS_SIZE, "size": SETTINGS_SIZE,
                    "defaults": settings_defaults(args.build)}
    keep_out = settings["offset"] if settings else None   # nothing may be written from here on

    parts = []
    for offset_text, rel in sorted(flasher["flash_files"].items(), key=lambda kv: int(kv[0], 16)):
        offset = int(offset_text, 16)
        src = os.path.join(args.build, rel)
        with open(src, "rb") as f:
            data = f.read()
        if offset < NVS_OFFSET + NVS_SIZE and offset + len(data) > NVS_OFFSET:
            sys.exit("refusing to publish {}: it would overwrite the NVS partition".format(rel))
        if keep_out is not None and offset < assets[0] + assets[1] and offset + len(data) > keep_out:
            sys.exit("refusing to publish {}: it reaches into the settings / song library area at 0x{:x} "
                     "(lower CONFIG_COGLET_MUSIC_LIBRARY_KB, or make the assets smaller)"
                     .format(rel, keep_out))
        if assets and offset == assets[0]:
            free = keep_out - offset - len(data)
            print("  assets image: {} KB, {} KB to spare before the settings and song library".format(
                len(data) // 1024, free // 1024))
        name = os.path.basename(rel)
        shutil.copyfile(src, os.path.join(out_dir, name))
        parts.append({
            "path": name,
            "offset": offset,
            "size": len(data),
            "md5": hashlib.md5(data).hexdigest(),
        })
        print("  0x{:07x}  {:>9} bytes  {}".format(offset, len(data), name))

    manifest = {
        "name": "Coglet",
        "version": args.version,
        "commit": args.commit,
        "repo": args.repo,
        "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "chip": chip,
        "flash_mode": settings.get("flash_mode", "keep"),
        "flash_freq": settings.get("flash_freq", "keep"),
        "flash_size": settings.get("flash_size", "keep"),
        "parts": parts,
    }
    if settings:
        manifest["settings"] = settings
        print("settings: 0x{:x}, defaults {}".format(settings["offset"], settings["defaults"]))
    if songs:
        manifest["songs"] = songs
        print("song library: 0x{:x}, {} KB".format(songs["offset"], songs["size"] // 1024))
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("manifest: {} parts, version {}".format(len(parts), args.version))

    if args.release_dir:
        os.makedirs(args.release_dir, exist_ok=True)
        zpath = os.path.join(args.release_dir, "coglet-firmware-{}.zip".format(args.version))
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for p in parts:
                z.write(os.path.join(out_dir, p["path"]), p["path"])
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            z.writestr("FLASH.txt", flash_instructions(manifest))
        print("release zip:", zpath)
    return 0


def flash_instructions(manifest):
    args = " ".join("0x{:x} {}".format(p["offset"], p["path"]) for p in manifest["parts"])
    return (
        "Coglet firmware {v}\n\n"
        "Easiest: use the web flasher (link in the repository README).\n\n"
        "With esptool (keeps Wi-Fi and pairing):\n"
        "  esptool.py --chip {chip} -b 921600 write_flash {args}\n"
    ).format(v=manifest["version"], chip=manifest["chip"], args=args)


if __name__ == "__main__":
    sys.exit(main())
