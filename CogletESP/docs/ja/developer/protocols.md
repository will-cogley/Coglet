# プロトコル：サーバーとMCPツール

[ドキュメント](../README.md) · [English](../../en/developer/protocols.md) · [Deutsch](../../de/developer/protocols.md) · [Español](../../es/developer/protocols.md) · **日本語**

Cogletは、上流プロジェクト [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) の
プロトコルをそのまま使っています。このページはCoglet開発者向けの要約です。正式な
資料は[上流のドキュメント](https://github.com/78/xiaozhi-esp32/tree/main/docs)と
コード（`main/protocols/`、`main/mcp_server.cc`）です。

## 接続

1. 起動時、デバイスはボードタイプ（`cognog-v3`）、ファームウェアのバージョン、IDを
   付けて **OTA URL**（`CONFIG_OTA_URL`、初期値はxiaozhi.meのAPI）を呼び出します。
   応答には、サーバーの時刻とタイムゾーン、通信方式の設定（MQTT + UDPまたは
   WebSocket）、まだペアリングしていなければアクティベーションコード、場合によっては
   新しいファームウェアが含まれます。
2. セッションが始まると（ウェイクワード、ボタン、Auto-Awake）、デバイスは音声チャンネルを
   開き、双方が `hello` メッセージを交換します。
3. 音声は60 msフレームの **Opus** です。デバイスからは16 kHzモノラル、戻りはサーバーの
   サンプリングレート（ふつうは24 kHz）。制御メッセージはJSONです。

### WebSocket

1本のWebSocket接続で、JSONのテキストフレームとOpusのバイナリフレームを運びます。
ハンドシェイクのヘッダー：`Authorization: Bearer <token>`、`Protocol-Version`、
`Device-Id`（MACアドレス）、`Client-Id`（UUID。消去でリセットされます）。

```json
{"type": "hello", "version": 1, "features": {"mcp": true}, "transport": "websocket",
 "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60}}
```

サーバーは10秒以内に `"type": "hello"` と `"transport": "websocket"` で応答する必要が
あります。`session_id` を付けてもかまいません。

### MQTT + UDP

JSONメッセージはMQTT（キープアライブ240秒）、音声はUDPで送ります。サーバーの `hello`
応答には、UDPサーバー、ポート、AESの鍵とnonceが含まれます。UDPパケットの形式：

```
|type 1|flags 1|payload_len 2|ssrc 4|timestamp 4|sequence 4|payload（AES-CTRで暗号化したOpus）|
```

ネットワークバイトオーダーです。期待より小さいシーケンス番号のパケットは破棄されます。
セッションは `{"type": "goodbye"}` で終わります。

### JSONメッセージ

デバイス → サーバー：

| `type` | フィールド | 意味 |
|---|---|---|
| `listen` | `state`：`start` / `stop` / `detect`、`mode`：`auto` / `manual` / `realtime`、`text` | 聞き取りの開始・停止。`detect` はウェイクワード（またはCogletの合図テキスト）を伝えます |
| `abort` | `reason` | 今の返答を止める（例：話している最中のウェイクワード） |
| `mcp` | `payload` | JSON-RPC 2.0メッセージ（後述） |

サーバー → デバイス：

| `type` | 意味 |
|---|---|
| `stt` | 認識したユーザーの発話 |
| `llm` | 返答の `emotion`（例：`happy`）。**CogletはこれをRP2040へ転送し**、RP2040が対応するアニメーションを再生します |
| `tts` | `state`：`start`、`sentence_start`（`text` 付き）、`stop`。`start` でCogletは `speaking` になります |
| `mcp` | JSON-RPC 2.0のリクエスト |
| `system` | `command`：`reboot` |

## MCP

サーバーがMCPクライアント、デバイスがMCPサーバーです。メッセージは
`{"type": "mcp", "payload": {...}}` の形で、payloadはJSON-RPC 2.0です：

1. `initialize`：サーバーは `capabilities.vision`（写真用のURLとトークン）を渡せます。
   デバイスは `protocolVersion` `2024-11-05` と、`serverInfo.name`＝ボード名
   （`cognog-v3`）で応答します。
2. `tools/list`（`cursor` / `nextCursor` でページ分け）：デバイスは、名前、説明、
   入力スキーマ付きでツールを一覧にします。
3. `name` と `arguments` 付きの `tools/call`：デバイスはツールを実行し、
   `{"content": [{"type": "text", "text": "..."}], "isError": false}` または
   JSON-RPCのエラーで応答します。

LLMはツールの **説明文** を読んで、いつ呼ぶかを決めます。つまり説明文もCogletの
ふるまいの一部です。

### Cogletのツール

`main/boards/cognog-v3/cognog_v3_board.cc` で登録しています：

| ツール | 引数 | 動作 |
|---|---|---|
| `self.coglet.shake_head` | — | `action:shake_head` |
| `self.coglet.blink` | — | `action:blink` |
| `self.coglet.move_left_ear` | — | `action:left_ear` |
| `self.coglet.move_right_ear` | — | `action:right_ear` |
| `self.coglet.move_ears` | — | `action:ears` |
| `self.coglet.reminder.get_time` | — | デバイスの現地時刻とタイムゾーン |
| `self.coglet.reminder.create` | `datetime`（現地時刻 `YYYY-MM-DD HH:MM:SS`）、`message` | リマインダーを保存 |
| `self.coglet.reminder.list` | — | 未実行のリマインダー |
| `self.coglet.reminder.cancel` | `id` | 1件を取り消し |
| `self.coglet.reminder.last_due` | — | 時刻になったばかりのリマインダーの内容 |
| `self.coglet.dance` | `style`（初期値 `random`） | ダンスかユーザーの曲を開始 |

このほか `main/mcp_server.cc` の共通ツールがあります。たとえば
`self.get_device_status`、`self.audio_speaker.set_volume`、カメラが動いていれば
`self.camera.take_photo` です。

### ツールを追加する

ボードの `InitializeTools()` に追加します：

```cpp
AddCogletTool(
    "self.coglet.nod",
    "Call when the user asks Coglet to nod. Nods three times.",
    PropertyList(),                      // または PropertyList({Property("times", kPropertyTypeInteger, 1, 1, 5)})
    [this](const PropertyList&) -> ReturnValue {
        SendCogletAction("nod");          // UART "action:nod"
        return true;                      // bool、int、std::string のいずれか
    });
```

次に、`RP2040/animation.py` の `start_mcp_action()` / `update_mcp_action()` に `nod` を
追加します。ツール名は `self.<分野>.<動作>` の形にし、LLMがいつ呼ぶべきかを正確に
わかるよう説明文を書いてください。
