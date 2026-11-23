# NMRobotics Coglet — CogNog V3.0 PCB

Board support for Coglet on the CogNog V3.0 PCB
(schematic: `PCB/SCH_CogletESPV3.0_2026-09-10.pdf`).

- ESP32-S3-WROOM-1-N16R8: Wi-Fi, voice, wake word, GC0308 camera, MCP tools
- RP2040: servos (PCA9685) and Grove Vision AI face tracking, driven by the ESP
  over UART1 (ESP GPIO17 TX → RP2040 GPIO5, ESP GPIO18 RX ← RP2040 GPIO4)
- No display. The red LED on GPIO3 is on while Coglet is listening.

All GPIOs are in `config.h`; each one was checked against the V3.0 PCB netlist.

## Board type

menuconfig: `Xiaozhi Assistant → Board Type → NMRobotics Coglet (CogNog V3.0 PCB)`
(`CONFIG_BOARD_TYPE_COGNOG_V3`). This is the default in `sdkconfig.defaults`.

The board reports itself as `cognog-v3` (OTA request, MCP server name,
User-Agent). Firmware up to 2.3.x used the generic xiaozhi board type
`bread-compact-wifi-s3cam`; with that name the xiaozhi OTA server could offer
a generic xiaozhi firmware, which the device would install automatically and
lose every Coglet feature. A board type of its own avoids that.

The old board type is still there (`bread-compact-wifi-s3cam`) so existing
local configurations keep building. Shared Coglet code checks
`CONFIG_COGLET_BOARD`, which is set for both.

## Build

Use ESP-IDF **v5.5.3**. The target (esp32s3) is already set in the committed
`sdkconfig`; do not run `idf.py set-target`, it regenerates `sdkconfig`
from the defaults and drops Coglet's configuration.

```bash
idf.py build flash
```

The editions (Christmas, Elf, Snowman) are overlays on top of `sdkconfig`;
see `docs/en/developer/build.md`.
