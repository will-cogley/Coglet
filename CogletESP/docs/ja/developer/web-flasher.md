# Coglet Updaterの仕組み

[ドキュメント](../README.md) · [English](../../en/developer/web-flasher.md) · [Deutsch](../../de/developer/web-flasher.md) · [Español](../../es/developer/web-flasher.md) · **日本語**

Coglet Updater（<https://will-cogley.github.io/Coglet/>）は、`tools/web_flasher/` にある
1枚の静的ページです：`index.html`、`coglet_i18n.js`（翻訳）、`coglet_songs.js`
（曲の変換）。[esptool-js](https://github.com/espressif/esptool-js) 0.6.1とWeb Serialを
使うので、HTTPSまたは `localhost` で、Chromium系のデスクトップブラウザーが必要です。
曲にはさらにWebCodecs（Chrome / Edge 94以降）が必要です。ユーザー向けの説明：
[はじめに](../user/getting-started.md)。

## アップデート

- ESP32-S3以外は書き込みを拒否します。各パーツは書き込みの前後に、マニフェストのMD5と
  照合します。フラッシュのモード、周波数、サイズはビルド時のままです。
- 書き込むのはブートローダー、パーティション表、OTAデータ、アプリ、assetsイメージです。
  NVS、設定セクター、曲ライブラリーには書き込みません。**クリーンインストール** では
  先にチップ全体を消去します。
- どのボタンも、何かをダウンロードする前にポートを尋ねます（ブラウザーはクリックの直後
  にしかポートの一覧を出さないため）。選んだポートはUSB IDで記憶します。一覧にはCogletが
  使うUSBシリアルチップだけが出ます。**すべてのポートを表示** ですべてを表示します。
- USB接続でデータが失われた場合は、1段階低い速度（921600 → 460800 → 115200）で書き直し、
  うまくいった速度を記憶します。
- 書き込みのあと、Cogletを再起動し、起動ログを表示して読み取ります：

| Cogletのログ | ページの表示 |
|---|---|
| `RP2040 did not answer` | 「あと1ステップ」：サーボボードのセットアップカード |
| `sending N of M files` | サーボボードを更新中。つないだままにする |
| `RP2040 running again` / `up to date` | すべて完了 |
| `RP2040 update failed` / `did not answer within` | 次の起動時に再試行。セットアップカードが代替手段 |

### Cogletの状態を確認

パーティション表（0x8000）、`otadata`（どのスロットから起動するか）、そのアプリスロットの
先頭1 KBを読み取ります。ESP-IDFのアプリ記述（バージョン）と、Coglet独自の記述
（`main/coglet_app_desc.h`：マジック `COGLET`、エディション、ビルドのコミット）から、
次のいずれかを表示します：アップデートあり、最新、より新しい（テストビルド）、ユーザー
自身のビルド（`local`）、同じバージョンの別ビルド、v2.3.0より前のファームウェア、
ファームウェアなし。さらにCoglet自身のエディションを選択し、Cogletを再起動して
サーボボードの状態を報告します。

### RP2040の初回セットアップ

自動更新より前にセットアップされたRP2040のためのものです。モード切替スイッチを
RP2040にした状態で、ページはMicroPythonのraw REPLから実行中のプログラムを止め、各ファイルを
`<name>.tmp` として書き込み、サイズを確認して名前を変え、バンドルIDを `coglet_bundle.txt` に
書き、ソフトリブートします。すべてのファイルを書き終えるまで、何も置き換えません。
RP2040にMicroPythonが入っている必要があります（キットはすべて入った状態で出荷されます）。

## 設定

曲ライブラリーの直前にある4 KBのセクター1つです（`main/coglet_settings.h`）：
`CGST`、バージョン、長さ、CRC-32（zlib）、続いて `key=value` の行：

| キー | 値 |
|---|---|
| `wake_word` | 英語のフレーズ。小文字a〜z、`'`、スペース |
| `threshold` | 1〜99 %（ページでは1〜50） |
| `startup`、`reminder` | `mecha`、`evil`、`cat`、`christmas`、`elf`、`snowman` |
| `aec` | `on` / `off` |

保存するのは、選んだエディションの初期値と違う値だけです。それ以外はファームウェアに
従います（`make_manifest.py` が初期値を `manifest.json` に公開します）。値がない、または
不正な場合は、`idf.py flash` のあとでもmenuconfigの値に戻ります。MultiNetモデルは
ウェイクワードを自分で音素に変換します。変換できない場合、Cogletは内蔵のウェイクワードの
ままにして、`Wake word "..." from settings can't be used` と記録します。

```
I (900) CogletSettings: settings: wake word "hey coglet", threshold 3, startup cat, reminder evil, aec on
```

## マイソング

ブラウザーが各ファイルをデコードし、`tools/coglet_music/build_music.py` と同じ解析で
ビートを見つけます（`coglet_songs.js` はその移植版で、同じビートになります）。リミッターで
−14 LUFSに整え、60秒でフェードアウトして切り、WebCodecsでOgg/Opus（モノラル、24 kHz、
60 msフレーム、32 kbps）にエンコードします。

**曲ライブラリー** は `assets` パーティションの最後の2 MB（0xE00000〜0x1000000）で、
assetsイメージはここまで届きません。`make_manifest.py` は、assetsが届いてしまうビルドを
拒否します。構造（`main/coglet_music.h`）：セクター0に `CGML` ヘッダーと最大32件の
エントリー（名前、プリセット、BPM、長さ、オフセット、CRC-32）があり、各曲のOggデータと
ビート表はそれぞれ専用の4 KBセクターから始まります。一覧は最後に書き込み、曲ごとに
CRCがあるので、保存が中断しても前の曲は残り、壊れた曲は飛ばされます。

```
I (5120) CogletMusic: song library: 3 songs at assets+0x600000
```

## 言語

英語、ドイツ語、スペイン語、日本語。ページはブラウザーの言語に従います（なければ英語）。
🌐 メニューで切り替えると記憶され、`?lang=de|es|ja|en` で強制できます。英語の文章は
`index.html`（`data-i18n="key"`）にあり、ほかの言語は `coglet_i18n.js` の辞書です。
スクリプトのメッセージは `t("key", {name: value})` を使い、複数形の規則と地域の数値形式に
対応します。デバイスログは英語のままです。

言語を追加するには：`LANGS` に加え、すべてのキーを含む辞書（同じ `{placeholders}` と
マークアップ）を作り、🌐 メニューに `<option>` を追加します。

## 見た目

- *表示*：ライト、ダーク、昼と夜（7:00〜19:00はライト）、またはブラウザーの設定。
- 12月1日〜1月6日：SVGとCSSで描いたクリスマスの見た目（ガーランド、ライト、落ちてくる
  星や雪の結晶）。ボタンでそのシーズンはオフにでき、`?season=christmas|plain` で強制
  できます。*視差効果を減らす* の設定では何も動きません。
- アクセシビリティ：キーボードだけで操作可能、ラベル付きの操作部、進行状況とエラーの
  読み上げ（エラーは「Error:」で始まります）、WCAG AAのコントラスト、200 %ズーム。

## ローカルでのテスト

`index.html`、`coglet_i18n.js`、`coglet_songs.js` を、自分のビルドから `make_manifest.py` で
作った `firmware/` フォルダー（初回セットアップ用には `rp2040/` も）と同じ場所に置き、
`localhost` で配信します。ほかのエディションは、そのビルドで `make_manifest.py --edition
christmas`（または `elf`、`snowman`）も実行してください。これがないと、ページに
エディションの選択肢が出ません。
