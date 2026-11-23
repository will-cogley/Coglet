# デバイス側エコーキャンセル（AEC）

[ドキュメント](../README.md) · [English](../../en/developer/audio-aec.md) · [Deutsch](../../de/developer/audio-aec.md) · [Español](../../es/developer/audio-aec.md) · **日本語**

AECがあると、ユーザーはCogletの話の途中で割り込めます。Cogletは話しながらも聞き続け、
ウェイクワードなしで止められます。ユーザーはCoglet Updaterの **話の途中で割り込む** で
切り替えます。

## 仕組み

マイクとMAX98357Aアンプは別々のI2Sポートにつながっていて、スピーカー信号をハードウェアで
戻す経路がありません。そのため標準のデバイス側AECは使えません。Cogletはサーバー側AECを
使わず、ESP32-S3上のソフトウェアで参照信号を作ります：

1. スピーカーのI2S TX DMAが10 msのブロックを送り終えるたびに、コールバック `on_sent` が、
   実際にアンプへ送られたPCMを受け取ります。
2. マイクのI2S RX DMAが15 msのブロックを受け取るたびに、`on_recv` も同様に受け取ります。
3. 両方のコールバックに `esp_timer` でタイムスタンプを付けます。`SoftwareAecReference` は
   クロック追跡でタイムスタンプを平滑化し、マイクの各サンプルに同じ瞬間に再生された
   スピーカーのサンプルを対応させ、アンチエイリアス付きで24 kHzを16 kHzに変換します。
4. `Read()` はインターリーブした `[mic, ref]` を返します。esp-srのAFE AECが使う `MR` 形式です。
5. AECがオンのときは、起動時Auto-Awakeも含め、すべての起動経路が **realtime** の聞き取り
   モードを使います。

AECがオフのときは、これらは何も動きません。音声の経路はAECのないビルドと同じです。

## 設定

| オプション | 公開ファームウェア | |
|---|---|---|
| `CONFIG_USE_DEVICE_AEC` | オン | AECを組み込み |
| `CONFIG_COGLET_AEC_DEFAULT_OFF` | オン | ユーザーがオンにするまでオフ（設定キー `aec=on`） |
| `CONFIG_COGLET_AEC_REF_DELAY_MS` | 0 | 参照信号のずれ、−10〜20 ms |
| `CONFIG_USE_SERVER_AEC` | オフ | オフのままにします（両者は同時に使えません） |

設定は起動時に1回だけ読み込まれる（`CogletSettings::DeviceAec()`）ので、切り替えると
Cogletは再起動します。参照信号用のメモリーを確保できなかった場合、Cogletは
`Device AEC unavailable on this boot` と記録し、AECなしと同じように聞き取ります。

## 実機での確認

起動ログ：

```
NoAudioCodec: [AEC-REF] software loopback ENABLED: mic 16000 Hz (slot 0/2), speaker 24000 Hz ...
CogletAutoAwake: BOOT_LISTENING: mode=realtime
CogletSettings: Device AEC: on (from settings)
```

`AfeAudioProcessor` が `no reference channel` と出していないことを確認します。

*Coglet: log microphone levels every second*（`CONFIG_COGLET_MIC_DIAG_LOG`）をオンに
すると、1秒ごとに1行出ます：

```
[MIC] mode=aec-ref ... | [AEC-REF] refPeak=... offset=..us missing=.. late=.. micOvr=.. refOvr=.. resync=a/b torn=..
```

| 項目 | 正常な状態 |
|---|---|
| `refPeak` | Cogletが話しているときははっきり0より大きく、無音では0 |
| `offset` | 数ミリ秒以内で安定（値そのものより安定していることが大事） |
| `missing` / `late` | ほとんど増えない |
| `micOvr` | ウェイクワードと会話の切り替え時に増える：正常 |
| `resync` | 起動時にそれぞれ1、その後は安定 |
| `torn` | 常に0 |

聞き取りテスト：Cogletに長い返事をさせて割り込みます。止まって、こちらの言葉を理解
すれば正常です。こちらが黙っているあいだに、自分で自分の話を止めてはいけません。

## 参照信号の位置合わせ

1. menuconfigで *Enable Audio Debugger* をオンにし、パソコンの `IP:8000` を設定します。
2. パソコンで `python scripts/audio_debug_server.py` を実行します（初期値は16 kHz、2チャンネル）。
3. Cogletに話させ、できたWAVをAudacityで開きます。左がマイク、右が参照信号です。
4. マイクに入ったエコーは、参照信号より少し **あと**（0〜3 ms）に来るはずです。
   - エコーが参照信号より **前**：参照信号のずれをマイナスにします（−1、−2…）。
   - エコーが10 ms以上遅れる：タイムスタンプがずれています。録音を添えて報告してください。

## 既知の制限

- **サーボの音** はエコーではありません。口、耳、首が動くときのギアの音は消せず、
  Cogletの話が止まることがあります。
- **大きな音量**：小さなスピーカーとケースによる歪みは完全には消せません。AECは音量
  50%以下で最もよく動作します。
- AECのときはAFEのローカルVADがオフになり（上流のESP-Boxボードと同じ）、発話の始まりと
  終わりはサーバーが判断します。

## ファイル

- `main/audio/codecs/software_aec_reference.{h,cc}`：時間の位置合わせ（IDFに依存しない）
- `main/audio/codecs/no_audio_codec.{h,cc}`：DMAコールバック、`EnableSoftwareAecReference()`、`MR` 出力
- `main/boards/cognog-v3/cognog_v3_board.cc`：AECがオンのとき参照信号を開始
- `main/audio/processors/afe_audio_processor.cc`：参照チャンネルがないときの代替動作
- `main/application.cc`：AECのときのAuto-Awakeのrealtimeモード
