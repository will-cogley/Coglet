# Coglet partition table (16 MB)

`16m.csv`, used by every Coglet build (`CONFIG_PARTITION_TABLE_CUSTOM_FILENAME`).

| Name | Type | Offset | Size | Contents |
|---|---|---|---|---|
| `nvs` | data / nvs | 0x9000 | 16 KB | Wi-Fi, xiaozhi.me pairing, reminders |
| `otadata` | data / ota | 0xD000 | 8 KB | Which app slot boots |
| `phy_init` | data / phy | 0xF000 | 4 KB | RF calibration |
| `ota_0` | app | 0x20000 | 4032 KB | Firmware slot A |
| `ota_1` | app | 0x410000 | 4032 KB | Firmware slot B |
| `assets` | data / spiffs | 0x800000 | 8 MB | See below |

The `assets` partition holds, from its start:

1. the **assets image** built with the firmware (wake word models, fonts,
   sounds; `build/generated_assets.bin`), written by every update;
2. the **settings** sector (4 KB, `CGST`) right before the song library,
   written only by the Coglet Updater's Settings;
3. the **song library** (`CGML`), the last 2 MB (0xE00000–0x1000000),
   written only by the Coglet Updater's *My songs*.

Updates (Coglet Updater or `idf.py flash`) never write NVS, the settings or the
song library. `tools/web_flasher/make_manifest.py` refuses to publish a build
whose assets image would reach the settings sector.

Changing this table moves data that users already have on their Coglets: keep
the offsets and sizes as they are. Details:
[Architecture](../../docs/en/developer/architecture.md#stored-data).
