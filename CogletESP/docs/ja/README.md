# Cogletドキュメント

[English](../README.md) · [Deutsch](../de/README.md) · [Español](../es/README.md) · **日本語**

Cogletは、NMRoboticsのDIYデスクトップコンパニオンです。CogNogボードに、
ESP32-S3（音声、Wi-Fi、カメラ）とRP2040（9個のサーボ、顔追跡）を載せています。

## Cogletを使う・アップデートする

すべてブラウザーの **Coglet Updater** ページで行えます：
<https://will-cogley.github.io/Coglet/>。インストールは不要です。

- [はじめに](user/getting-started.md)：アップデート、Wi-Fi、ペアリング
- [Cogletの使い方](user/using-coglet.md)：会話、動き、ダンス、リマインダー、スイッチ
- [設定と曲](user/settings-and-songs.md)：ウェイクワード、効果音、「話の途中で割り込む」、自分の曲
- [トラブルシューティング](user/troubleshooting.md)

## ファームウェアをビルド・変更する

**ESP-IDF v5.5.3** が必要です（このバージョンちょうど。リリースビルドがこれを使っています）。

- [ファームウェアのビルド](developer/build.md)
- [ハードウェア：CogNog V3.0のピン](developer/hardware.md)
- [アーキテクチャ：ESP32-S3、RP2040、UART接続](developer/architecture.md)
- [プロトコル：サーバー、MCPツール](developer/protocols.md)
- [ダンスと曲](developer/dance.md)
- [デバイス側エコーキャンセル（AEC）](developer/audio-aec.md)
- [電源](developer/power.md)
- [Coglet Updaterの仕組み](developer/web-flasher.md)
- [リリースの公開](developer/releasing.md)

参考：[NMRobotsナレッジベース](https://nmrobots.com/pages/coglet)、および
このファームウェアの元になっている上流プロジェクト
[xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)。
