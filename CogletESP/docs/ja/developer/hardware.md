# ハードウェア：CogNog V3.0

[ドキュメント](../README.md) · [English](../../en/developer/hardware.md) · [Deutsch](../../de/developer/hardware.md) · [Español](../../es/developer/hardware.md) · **日本語**

設計ファイル：`PCB/SCH_CogletESPV3.0_2026-09-10.pdf`（回路図）、
`PCB/CogletESPV3.0_0906_2026-09-10.epro2`（EasyEDA Pro）。以下のピンはすべて
V3.0のネットリストで確認済みです。詳しくは
[CogNogデータシート](../../../../CogNogDatasheet.md)を参照してください。

## 概要

| 部品 | 役割 |
|---|---|
| ESP32-S3-WROOM-1-N16R8（U1） | Wi-Fi、音声、ウェイクワード、カメラ、MCPツール。16 MBフラッシュ、8 MB PSRAM |
| RP2040（U7） | サーボと顔追跡、MicroPython |
| PCA9685（U9） | 16チャンネルPWMサーボドライバー、I²Cアドレス0x40 |
| MAX98357A（U16） | I2Sスピーカーアンプ |
| CH343P（U14） | 書き込み用のUSBシリアル。モード切替スイッチでESPかRP2040を選びます |
| GC0308カメラ（FPC1） | AI用の写真（「何が見える？」） |
| Grove Vision AI V2 | 顔追跡、目の中のカメラ |
| I2S MEMSマイク | 音声入力 |

電源：JST-XH入力に **5 V / 3 A**。LDOで両方のMCU用の3.3 Vを作り、サーボは5 Vの
ラインで動きます。書き込み用USBポートだけで給電した場合、ロジックは動きますが
サーボには電源が届きません。

## ESP32-S3

| GPIO | ネット | 用途 |
|---|---|---|
| 0 | ESP_GPIO0 | BOOTボタン |
| 3 | ESP_GPIO3 | 赤い「聞き取り中」LED（Q4のゲート、アクティブHigh、100 kΩプルダウン） |
| 4 | MICWS | マイクWS |
| 5 | MICSCK | マイクSCK |
| 6 | MICSD | マイクのデータ |
| 7 | MAXDIN | アンプのデータ |
| 15 | MAXBCLK | アンプBCLK |
| 16 | MAXLRCLK | アンプLRCLK |
| 17 | ESP_GPIO17 | UART1 TX → RP2040 GPIO5 |
| 18 | ESP_GPIO18 | UART1 RX ← RP2040 GPIO4 |
| 19, 20 | USB D−/D+ | ネイティブUSB |
| 43, 44 | ESP_TX / ESP_RX | UART0、書き込みとログ（CH343P） |
| 1, 2, 45, 46 | ESP_GPIO1、EIO2、EIO45、EIO46 | 空き |

カメラ（GC0308、DVP 8ビット。CAMD2〜CAMD9はセンサーのY2〜Y9）：

| 信号 | GPIO | 信号 | GPIO |
|---|---|---|---|
| D0（CAMD2） | 41 | XCLK | 14 |
| D1（CAMD3） | 47 | PCLK | 9 |
| D2（CAMD4） | 48 | VSYNC | 8 |
| D3（CAMD5） | 38 | HREF | 40 |
| D4（CAMD6） | 42 | SIOC（SCCB SCL） | 10 |
| D5（CAMD7） | 21 | SIOD（SCCB SDA） | 12 |
| D6（CAMD8） | 11 | RESET | 39 |
| D7（CAMD9） | 13 | PWDN | —（R30経由でGND） |

Cogletは、ピン配置を反転させたカスタムのGC0308モジュールを使っています。

コード：[`main/boards/cognog-v3/config.h`](../../../main/boards/cognog-v3/config.h)、
[`main/uart_component.h`](../../../main/uart_component.h)。

## RP2040

| GPIO | 用途 |
|---|---|
| 0, 1 | UART0 TX / RX、Grove Vision AI V2へ、921600ボー |
| 4, 5 | UART1 TX / RX、ESP32-S3へ、115200ボー |
| 6, 7 | I²C SDA / SCL、PCA9685へ |
| 8 | PCA9685のnOE（High＝サーボ出力をすべてオフ） |
| 12 | サーボテストボタン（アクティブLow） |
| 20 | キャリブレーションスイッチ（アクティブLow） |
| 21 | 顔追跡スイッチ（アクティブLow） |
| 25 | 前面LED（シルク「RP25」） |

コード：`RP2040/app.py`、`RP2040/servoclass.py`、`RP2040/vision.py`。

## サーボソケット

各ソケットの横に印刷された番号が、そのPCA9685チャンネルです。

| ソケット | サーボ | コード上のキー | 範囲（°） |
|---|---|---|---|
| 0 | 右耳 | `EAR` | 30–120 |
| 1 | 左耳 | `EAL` | 60–150 |
| 2 | まぶた | `LID` | 30–160 |
| 3 | 口 | `MOU` | 5–150 |
| 4 | 左目 | `EYL` | 50–140 |
| 5 | 右目 | `EYR` | 50–140 |
| 8 | 首のピッチ | `PIT` | 1–80 |
| 9 | 首のロール | `ROL` | 30–120 |
| 10 | 台座のヨー | `YAW` | 30–150 |
| 6, 7, 11 | 空き | | |

上下限、速度、加速度は `RP2040/animation.py`（`servos`）に、キャリブレーション姿勢は
`pose_calibrate` にあります。
