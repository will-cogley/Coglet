# アーキテクチャ

[ドキュメント](../README.md) · [English](../../en/developer/architecture.md) · [Deutsch](../../de/developer/architecture.md) · [Español](../../es/developer/architecture.md) · **日本語**

```
 xiaozhi.meサーバー ──Wi-Fi── ESP32-S3 ──UART1 115200── RP2040 ──I²C── PCA9685 ── サーボ9個
   （音声、LLM）              音声、ウェイクワード、      MicroPython  └─UART0 921600── Grove Vision AI V2
                              カメラ、MCPツール、
                              リマインダー、ダンス
```

ESP32-S3は、Coglet用の機能を加えた [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
ファームウェアを実行します。Cogletが **何を** するかを決め、短いテキスト行でRP2040に
伝えます。サーボが **どう** 動くかはRP2040が決めます。

## ESP32-S3のファームウェア

| 場所 | 内容 |
|---|---|
| `main/application.cc` | デバイスの状態、音声セッション、Cogletの起動時Auto-Awake、ダンスとリマインダーの流れ。状態が変わるたびにRP2040へ送ります |
| `main/boards/cognog-v3/` | ボード：ピン、カメラ、赤いLED、CogletのMCPツール |
| `main/uart_component.cc` | RP2040とのUART1接続 |
| `main/coglet_rp2040_sync.cc` | RP2040のプログラムを最新に保ちます |
| `main/coglet_reminder.cc` | リマインダー（NVS） |
| `main/coglet_settings.cc` | Coglet Updaterで保存した設定 |
| `main/coglet_music*.{h,cc}`、`main/coglet_sounds*` | 曲、内蔵ダンスの曲、起動音とリマインダー音 |
| `main/audio/` | 音声処理、ウェイクワード、ソフトウェアAECの参照信号 |

### デバイスの状態

`starting → wifi_configuring / activating → idle ⇄ connecting → listening ⇄ speaking → idle`

赤いLEDが点灯するのは `listening` のときだけです。`idle` では、RP2040が眠りの姿勢を
とり、サーボのトルクを解放します。

**起動時Auto-Awake：** 起動音の数秒後、Cogletは自分から聞き取りのセッションを1回
開きます。RP2040の更新中は（最大2分）待つので、転送が最初の会話と重なることは
ありません。起動ごとに1回だけで、失敗した場合はウェイクワードを待ちます。

**自発的なセッション：** ダンスのあとやリマインダーの時刻になったとき、Cogletは自分から
セッションを開き、ウェイクワードを検出したかのように短い合図のテキストを送ります：
`（跳完舞了）`（「踊り終わった」）や `（有提醒到点了）`（「リマインダーの時刻になった」）。
これをどう扱うかは、MCPツールの説明文がLLMに伝えます。これらはあえて中国語のままです。
LLMはどの言語でも理解でき、xiaozhi.meの制限で13文字以内にする必要があるためです。

## UARTプロトコル（ESP → RP2040）

1行に1コマンドで、末尾は `\r\n` です。各行は1回の呼び出しで書き込まれるので、
別のタスクの行が混ざることはありません。

| 行 | 意味 |
|---|---|
| `idle`、`listening`、`speaking`、`thinking`、`configuring` … | デバイスの状態 |
| `neutral`、`happy`、`sad`、`angry`、`surprised`、`sleepy`、`silly`、`confused`、`cool`、`loving` … | LLMが返答と一緒に送る感情 |
| `action:shake_head` / `blink` / `left_ear` / `right_ear` / `ears` | MCPツールからの1回きりの動き（3回） |
| `dance:<style>` | 内蔵ダンスを開始。例：`dance:mecha` |
| `dance:stop` | ダンスをすぐに止める |
| `prep:<style>` / `prep:groove-<preset>` | ダンスのために会話を閉じるところ：眠らずにサーボの電源を入れたまま、ダンスの開始姿勢へ移る（ダンス開始、`dance:stop`、または15秒で終了） |
| `groove:<energetic\|calm>:<bpm>` | 自分の曲でダンスを開始 |
| `gb:<s><e><b>` | 自分の曲の1拍：アクセント0〜9、セクションのエネルギー0〜9、小節の頭0/1 |
| `groove:end` | 自分の曲が終わった |
| `upd:…` | RP2040の更新プロトコル（後述） |

RP2040は `animation.state_map` で状態と感情をアニメーションに割り当てます。知らない
行は無視されます。感情では口は止まりません。話すアニメーションを終わらせるのは状態の行
（`idle`、`listening`、`thinking`、`neutral` など）だけです。

## RP2040のプログラム

| ファイル | 役割 |
|---|---|
| `main.py` | 小さな起動プログラム：中断された更新を完了させ、`app.py` を実行し、`app.py` が起動できなければ復旧モードに入ります |
| `app.py` | メインループ：UART、スイッチ、サーボの担当、トルクの解放 |
| `animation.py` | サーボ表、姿勢、状態ごとのアニメーション、まばたき、話すときの口、MCPアクション |
| `servoclass.py` | PCA9685ドライバーと、速度・加速度に上限のある `Servo` |
| `vision.py` | Grove Vision AIによる顔追跡（目と首のピッチ。目の可動限界では台座のヨーが引き継ぎます） |
| `music.py`、`dance_*.py` | ダンスの再生と、生成された振り付け |
| `coglet_updater.py` | ESPからの更新を受け取ります |

サーボを動かす担当（優先度の高い順）：

1. **キャリブレーションモード**（スイッチ）：すべてキャリブレーション姿勢。
   サーボテストボタンで±10°動きます。
2. **ダンス**
3. **MCPアクション**（`action:…`）
4. **状態のアニメーション**、まばたき、顔追跡（idle以外で、顔追跡スイッチが
   オンのときだけ）、話すときの口。

idleの姿勢が落ち着くと、RP2040は500 ms待ってからPCA9685のnOEをHighにし、すべての
トルクを解放します。ほかの状態になると、サーボを1つずつ順にオンに戻します
（[電源](power.md)）。

## RP2040の更新

`tools/rp2040_bundle/build_bundle.py` がビルドのたびに `RP2040/*.py` をESPの
ファームウェアに詰め込みます。バンドルIDは全ファイルのハッシュです。起動の約5秒後、
ESPはRP2040にバンドルIDを尋ねます。違っていれば、各ファイルのサイズとCRCを尋ね、
変更されたファイルだけを送ります：

```
ESP → upd:ver?                       RP → upd:ver:<id>|none
ESP → upd:crc?:<name>                RP → upd:crc:<name>:<size>:<crc32> | upd:crc:<name>:none
ESP → upd:begin:<id>:<files>         RP → upd:ready
ESP → upd:file:<name>:<size>:<crc>   RP → upd:ok:f
ESP → upd:d:<seq>:<base64>           RP → upd:ok:<seq>      （再送分にも再度応答）
ESP → upd:end                        RP → upd:ok:e | upd:err:<why>
ESP → upd:commit                     RP → upd:done のあと再起動
ESP → upd:abort                      準備中のファイルを削除
```

RP2040は `<name>.new` ファイルを書き込み、サイズとCRC-32を確認し、すべて届いてから
名前を変えます。名前を変えるファイルのリストを先に書き込むので、途中で電源が切れても
次の起動時に完了します。転送中はサーボが解放されます。全ファイルの転送は30秒ほど、
ふつうの更新は数秒です。

ESPのログ（タグ `CogletRp2040`）：`RP2040 up to date`、`RP2040 updated (bundle …)`、
`RP2040 did not answer: it needs the one-time setup from the web flasher`、
`RP2040 update failed … retried on the next boot`。

更新プログラムのない古いRP2040は、一度だけCoglet Updaterでセットアップが必要です
（[Coglet Updaterの仕組み](web-flasher.md#rp2040の初回セットアップ)）。

## リマインダー

1回きりのリマインダーを最大12件、各120バイトまで、UTC時刻でNVSに保存します。
そのため、タイムゾーンが変わっても保存済みのリマインダーはずれません。タイムゾーンは
サーバーの `timezone_offset`（OTAチェック）か、menuconfigのPOSIX TZ文字列から取ります。
時刻になってCogletがidleなら（ダンス中はダンスが先に終わります）、リマインダー音を
鳴らし、自発的なセッションを開きます。そこでLLMが `self.coglet.reminder.last_due` を
呼び、内容を1文で話します。

## 保存されるデータ

| データ | 場所 | アップデートで残るか |
|---|---|---|
| Wi-Fi、ペアリング、リマインダー | NVSパーティション | 残る |
| 設定（`CGST` セクター） | 曲ライブラリーの直前の4 KB、`assets` 内 | 残る（`idf.py flash` ではリセット） |
| 曲ライブラリー（`CGML`） | `assets` の最後の2 MB（0xE00000〜0x1000000） | 残る |
| アプリ、assetsイメージ | `ota_0` / `ota_1`、`assets` | 置き換わる |

パーティション表：`partitions/v2/16m.csv`。
