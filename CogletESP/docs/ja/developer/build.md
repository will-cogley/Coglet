# ファームウェアのビルド

[ドキュメント](../README.md) · [English](../../en/developer/build.md) · [Deutsch](../../de/developer/build.md) · [Español](../../es/developer/build.md) · **日本語**

## ESP-IDFのバージョン：v5.5.3

**ESP-IDF v5.5.3** を使ってください。これより古いものも新しいものも使いません。
リリースビルドは公式コンテナー `espressif/idf:v5.5.3` で実行され
（`.github/workflows/firmware.yml`）、`dependencies.lock` がこのバージョン用の
マネージドコンポーネントを固定しています。別のバージョンでもビルドできる場合は
ありますが、それはCogletで動いているものとは別物です。

### インストール

**Windows：** [ESP-IDF Windowsインストーラー](https://dl.espressif.com/dl/esp-idf/)を
実行し、**v5.5.3** を選びます。インストールされる *ESP-IDF 5.5 PowerShell*（または
CMD）からビルドします。

**Linux / macOS：**

```bash
git clone -b v5.5.3 --recursive https://github.com/espressif/esp-idf.git ~/esp/esp-idf-v5.5.3
cd ~/esp/esp-idf-v5.5.3
./install.sh esp32s3
. ./export.sh          # 新しいターミナルを開くたびに実行
```

確認：`idf.py --version` が `ESP-IDF v5.5.3` と表示します。

任意：libopus付きの **ffmpeg**。`Music/` フォルダーの曲にだけ必要です
（[ダンスと曲](dance.md#music-フォルダー)）。Windows：`winget install Gyan.FFmpeg`。

## ビルドと書き込み

```bash
cd CogletESP
idf.py build
idf.py -p <ポート> flash monitor
```

- ターゲット（esp32s3）、ボードタイプ、Cogletのすべてのオプションは、リポジトリの
  `sdkconfig` に入っています。**`idf.py set-target` は実行しないでください**。
  初期値から `sdkconfig` を作り直し、Cogletの設定が消えてしまいます。
- 上側のUSB-Cポート（書き込み用ポート）につなぎ、モード切替スイッチは **ESP** にします。
- `<ポート>` は、たとえばWindowsでは `COM5`、Linuxでは `/dev/ttyACM0` や
  `/dev/ttyUSB0`、macOSでは `/dev/cu.usbmodem…` です。
- `idf.py flash` では、Wi-Fi、ペアリング、リマインダー、Coglet Updaterで保存した
  設定と追加した曲は残ります。`idf.py erase-flash` ではすべて消えます。
- 初回のビルドではマネージドコンポーネントをダウンロードします。2回目以降は差分ビルドです。

ボードタイプ：**NMRobotics Coglet (CogNog V3.0 PCB)**
（`CONFIG_BOARD_TYPE_COGNOG_V3`）。ボードのファイルは
[`main/boards/cognog-v3/`](../../../main/boards/cognog-v3) にあります。`cognog-v3`
と名乗ります。2.3.xまでのファームウェアは汎用のボードタイプ
`bread-compact-wifi-s3cam` を使っていました。古いローカル設定のために、こちらも
残っています。

## エディション

スタンダード、クリスマス、エルフ、雪だるまの違いは、内蔵の3つのダンスと、初期の
起動音・リマインダー音だけです。それぞれ `sdkconfig` に重ねる設定で、専用のフォルダー
でビルドします：

```bash
idf.py -B build-christmas -D SDKCONFIG=build-christmas/sdkconfig \
       -D SDKCONFIG_DEFAULTS="sdkconfig;sdkconfig.christmas" build
idf.py -B build-christmas -p <ポート> flash
```

`sdkconfig.elf` / `build-elf`、`sdkconfig.snowman` / `build-snowman` も同じように
使います。menuconfigの *NMRobotics Coglet Dance → Firmware edition* で選ぶこともできます。

## menuconfig

`idf.py menuconfig`。Cogletのオプション：

| メニュー | オプション |
|---|---|
| Xiaozhi Assistant | ボードタイプ、ウェイクワード（初期値「hello coglet」）、デバイス側AEC（`USE_DEVICE_AEC`、`COGLET_AEC_DEFAULT_OFF`、`COGLET_AEC_REF_DELAY_MS`）、マイクレベルのログ（`COGLET_MIC_DIAG_LOG`） |
| NMRobotics Coglet Reminder | チャイムのあとにリマインダーを話すか、タイムゾーン（サーバーから自動、またはPOSIX TZ文字列） |
| NMRobotics Coglet RP2040 | RP2040のプログラムを自動で更新するか |
| NMRobotics Coglet Dance | 内蔵ダンス、ファームウェアのエディション、`Music/` の曲、曲ライブラリーのサイズ、ビートのタイミング補正 |
| NMRobotics Coglet Sounds | 初期の起動音とリマインダー音 |

Coglet Updaterで保存した値（ウェイクワード、起動しきい値、効果音、AEC）は、そこで
**初期値に戻す** で消すまで、menuconfigより優先されます。

## ファームウェアのバージョン

バージョンは `CogletESP/CMakeLists.txt` の `PROJECT_VER` です（リリースビルドでは
gitのタグから取ります）。`2.3.2` のような数字だけにしてください。`-接尾辞` は付けて
もかまいません。OTAのチェックが数字を1つずつ比べるためです。

## RP2040のプログラムを変更する

RP2040はMicroPythonで動き、プログラムは [`RP2040/`](../../../RP2040) にあります。
ESPのビルドのたびにこれらのファイルがファームウェアに詰め込まれ、起動後にESPが変更
されたファイルをRP2040へ送ります（[アーキテクチャ](architecture.md#rp2040の更新)）。
つまりRP2040を変更するふつうの方法は、ファイルを編集してESPに書き込むことです。

試しているあいだは、Thonny（モード切替スイッチは **RP2040**）でファイルを直接
アップロードすることもできます。その場合、ESPは次の起動時に別のバンドルだと判断し、
自分のコピーで書き戻します。ESPのファームウェアと `RP2040/` を同じコミットに揃えるか、
試しているあいだは *NMRobotics Coglet RP2040 → Update the RP2040 program
automatically* をオフにしてください。

注意：RP2040のファイルを変更すると、コメントだけの変更でも、次のアップデートで
すべてのCogletがそのファイルを送り直します。

## ログ

`idf.py monitor` でESPのログが見られます。Coglet Updaterの **デバイスログを表示** でも
同じものが見られます。RP2040は自分のUSBシリアルに出力します（モード切替スイッチは
RP2040）。便利なタグ：`CogletRp2040`（サーボボードの更新）、`CogletDance`、
`CogletReminder`、`CogletSettings`、`CogletMusic`、`CogletAutoAwake`。
