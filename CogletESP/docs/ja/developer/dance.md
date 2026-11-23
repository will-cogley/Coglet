# ダンスと曲

[ドキュメント](../README.md) · [English](../../en/developer/dance.md) · [Deutsch](../../de/developer/dance.md) · [Español](../../es/developer/dance.md) · **日本語**

ユーザーがCogletに踊ってと頼むと、MCPツール `self.coglet.dance(style)` が次のことを行います：

1. LLMに短い1行で返事をさせます（「Watch this!」）。
2. 会話を終えます。
3. 曲を再生し、そのあいだRP2040がすべてのサーボをビートに合わせて動かします。
4. そのあと合図 `（跳完舞了）` で自分から新しいセッションを開き、感想を聞きます。

| | 内蔵の曲 | 自分の曲 |
|---|---|---|
| 音楽 | エディションごとに、オリジナルまたはパブリックドメインを編曲した約30秒の曲を3つ | `Music/` フォルダー（ファームウェアに組み込み）、またはCoglet Updaterの *マイソング*（曲ライブラリー） |
| ダンス | 音楽と同じ楽譜から生成した、手書きの振り付け | 自動：ビートを事前に検出し、曲の再生中にRP2040へ送ります |
| RP2040のファイル | `music.py` ＋ `dance_data.py` / `dance_xmas.py` / `dance_elf.py` / `dance_snow.py` | `music.py` だけ |

## 内蔵の曲

| エディション | `style` | 音楽 | テンポ |
|---|---|---|---|
| スタンダード | `mecha` | 重厚なメカ系エレクトロ、ヘ短調 | 128 BPM |
| | `evil` | 暗いゴシック、ニ短調（和声的短音階） | 96 BPM |
| | `cat` | やさしいアニメ風の猫ポップ、ハ長調 | 120 BPM |
| クリスマス | `lyrical` | きよしこの夜 | 104 BPM、3/4 |
| | `classic` | ジングル・ベル | 136 BPM |
| | `grand` | もろびとこぞりて（Joy to the World） | 84 BPM、2/4 |
| エルフ | `workshop` | ひいらぎかざろう（Deck the Halls） | 132 BPM |
| | `mischief` | 世の人忘るな（God Rest Ye Merry Gentlemen） | 156 BPM |
| | `party` | おめでとうクリスマス（We Wish You a Merry Christmas） | 160 BPM、3/4 |
| 雪だるま | `lullaby` | ブラームス「子守歌」作品49-4 | 104 BPM、3/4 |
| | `stomp` | ウェンセスラスはよい王様（Good King Wenceslas） | 108 BPM |
| | `blizzard` | レオントーヴィチ「シチェドリク」（1914年。キャロル・オブ・ザ・ベル） | 150 BPM、3/4 |

`random` はそのエディションの3曲から1つを選びます。ファームウェアに入るのは1つの
エディションの曲だけです。RP2040はすべてのエディションの振り付けを知っていて、必要な
モジュールだけを読み込みます。どのダンスも音楽が終わる1.5秒前に最後の姿勢になるので、
次のセッションの前にCogletが落ち着きます。

## 自分の曲

入手先は2つあり、どちらも同じように踊ります：

- Coglet Updaterの **マイソング**：ブラウザーで変換し、ファームウェアの外の曲ライブラリーに
  保存します。アップデートしても残ります（[Coglet Updaterの仕組み](web-flasher.md#マイソング)）。
- **`Music/` フォルダー**：自分のビルドに組み込みます（後述）。

### プリセット

| プリセット | 動く部分 | スタイル |
|---|---|---|
| energetic（エネルギッシュ） | すべてのサーボ | 毎拍うなずく（アクセントでは深く）、耳をぴくっと動かす、小節ごとに揺れと台座の回転、ビートに合わせた目、まばたき、いちばん強い音で口。曲の音量に合わせて大きさが変わります |
| calm（おだやか） | 耳、頭（ピッチとロール）、台座 | 体で感じる拍に合わせたゆっくりしたうなずき、ただよう耳、小さな揺れ。曲のあいだずっと **まぶたと両目のサーボはトルクを解放** します |

おだやかな曲は、体で感じる拍に合わせます。136 BPMでも68に感じるバラードなら、68で
うなずきます。

### `Music/` フォルダー

1. `CogletESP/Music/` に音声ファイルを入れます：mp3、wav、flac、m4a、aac、ogg、opus、
   wma、aiff、または動画（mp4、mov、m4v、webm、mkv。音声トラックを使います）。
2. `idf.py build`。`tools/coglet_music/build_music.py` が各ファイルをOgg/Opus
   （モノラル、24 kHz、60 msフレーム、音量を正規化）に変換し、最大の長さでフェード
   アウトして切り、テンポ、ビート、アクセント、セクション、小節の頭を検出し、
   プリセットを選んで組み込みます。結果は `build/coglet_music/cache/` にキャッシュされます。
3. 書き込んで、「*Night Rain* で踊って」や「自分の曲で踊って」と頼みます。曲名は、
   拡張子とタグを除いたファイル名です。

拡張子の前にタグを付けると、プリセットやテンポを指定できます：

```
Night Rain.calm.mp3
Drop It.energetic.wav
Free Fall.calm.68bpm.m4a
```

libopus付きのffmpegが必要です。ない場合、曲は警告付きでスキップされ、ビルドはそのまま
成功します。`Music/.gitignore` で曲はgitに入りません。**権利のない音楽を含む
ファームウェアイメージは公開しないでください。**

menuconfigの *NMRobotics Coglet Dance*：

| オプション | 初期値 | |
|---|---|---|
| Custom songs from the Music folder | オン | |
| ffmpeg executable | `ffmpeg` | 名前またはフルパス。Windowsではスラッシュで、例：`C:/ffmpeg/bin/ffmpeg.exe` |
| Maximum length per song | 60秒 | |
| Opus bitrate | 32 kbps | 1分あたり約240 KB |
| Flash budget for all custom songs | 400 KB | 入りきらない曲はスキップされます |
| Song library size | 2048 KB | Coglet Updaterで追加する曲の領域 |
| Beat timing offset | 20 ms | 動きが遅れる → 下げる、早い → 上げる |

## 仕組み

ESP（`main/application.cc`）：

```
self.coglet.dance(style)
  WaitAck   1行の返事を待つ（TTS終了、音声が無音。最大10〜20秒）
  Starting  音声チャンネルを閉じる → idle
  Playing   内蔵：  "dance:<style>"。タスクが曲を再生
            自分の曲："groove:<preset>:<bpm>"。タスクが曲を再生し、別のタスクが
                      毎拍 "gb:<strength><energy><bar>" を送り、最後に "groove:end"
  FollowUp  音楽の1秒後："（跳完舞了）" で自発的なセッション
```

- ウェイクワードやボタンでダンスはすぐに止まり（`dance:stop`）、感想の質問の代わりに
  ユーザー自身の会話が始まります。
- ダンス中に時刻になったリマインダーは、ダンスの終わりを待ち、感想の質問の代わりに
  話されます。
- `AudioService::PlaySound()` は中止フラグを受け取るので、曲は約10 msで止まります。

RP2040（`RP2040/music.py`）：ダンスはすべてのサーボを担当します（これより優先されるのは
キャリブレーションモードだけです）。同期：`AUDIO_LATENCY_MS = 120`（コマンドから音が
出るまで）、`SERVO_LEAD_MS = 100`（ビートに合うよう早めに動き始める）。自分の曲で
ビートが4秒届かないと、ダンスは自動で終わります。そのあと、初期の動きの上限を戻し、
現在の状態をもう一度適用します。

## 内蔵の曲を作り直す

`tools/coglet_dj/`（numpyとscipyの入ったPython、ほかにffmpeg）：

```bash
cd tools/coglet_dj
python3 render.py mecha evil cat                    # out/*.ogg、プレビュー、振り付けのJSON
python3 export_rp2040.py ../../RP2040/dance_data.py
```

振り付けだけを変えるには、`choreo.py` を編集し、`choreo_only.py`、続けて
`export_rp2040.py` を実行します。季節のエディションも、`xmas.py` / `choreo_xmas.py` /
`export_xmas_rp2040.py` / `export_xmas_headers.py` と、`elf`・`snow` の同等のもので
同じように扱います。ヘッダーの書き出しは `out/approved/` を読むので、
`main/coglet_sounds/` に入るのは誰かが聴いて確認した音声だけです。生成された
`dance_*.py` は手で編集しません。
