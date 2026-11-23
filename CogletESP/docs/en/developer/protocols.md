# Protocols: server and MCP tools

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/developer/protocols.md) · [Español](../../es/developer/protocols.md) · [日本語](../../ja/developer/protocols.md)

Coglet uses the protocols of the upstream
[xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) project unchanged. This
page is a summary for Coglet developers; the
[upstream docs](https://github.com/78/xiaozhi-esp32/tree/main/docs) and the
code (`main/protocols/`, `main/mcp_server.cc`) are the reference.

## Connection

1. At boot the device calls the **OTA URL** (`CONFIG_OTA_URL`, by default the
   xiaozhi.me API) with its board type (`cognog-v3`), firmware version and
   ids. The answer carries the server time and time zone, the transport
   settings (MQTT + UDP or WebSocket), an activation code if the device isn't
   paired yet, and possibly a newer firmware.
2. When a session starts (wake word, button, Auto-Awake), the device opens the
   audio channel and both sides exchange a `hello` message.
3. Audio is **Opus**, 60 ms frames: 16 kHz mono from the device, the server's
   sample rate (usually 24 kHz) back. Control messages are JSON.

### WebSocket

One WebSocket connection carries JSON text frames and binary Opus frames.
Handshake headers: `Authorization: Bearer <token>`, `Protocol-Version`,
`Device-Id` (MAC address), `Client-Id` (UUID, reset by an erase).

```json
{"type": "hello", "version": 1, "features": {"mcp": true}, "transport": "websocket",
 "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60}}
```

The server must answer with `"type": "hello"` and `"transport": "websocket"`
within 10 s, optionally with a `session_id`.

### MQTT + UDP

JSON messages go over MQTT (keepalive 240 s); audio goes over UDP. The server's
`hello` answer contains the UDP server, port, and the AES key and nonce. Each
UDP packet is

```
|type 1|flags 1|payload_len 2|ssrc 4|timestamp 4|sequence 4|payload (AES-CTR encrypted Opus)|
```

in network byte order. Packets with a sequence number lower than expected are
dropped. A session ends with `{"type": "goodbye"}`.

### JSON messages

Device → server:

| `type` | Fields | Meaning |
|---|---|---|
| `listen` | `state`: `start` / `stop` / `detect`, `mode`: `auto` / `manual` / `realtime`, `text` | Start or stop listening; `detect` reports the wake word (or a Coglet cue text) |
| `abort` | `reason` | Stop the current reply, e.g. on a wake word while speaking |
| `mcp` | `payload` | JSON-RPC 2.0 message, see below |

Server → device:

| `type` | Meaning |
|---|---|
| `stt` | Recognised user speech |
| `llm` | `emotion` of the reply, e.g. `happy`. **Coglet forwards it to the RP2040**, which plays the matching animation |
| `tts` | `state`: `start`, `sentence_start` (with `text`), `stop`. `start` puts Coglet in `speaking` |
| `mcp` | JSON-RPC 2.0 request |
| `system` | `command`: `reboot` |

## MCP

The server is the MCP client, the device the MCP server. Messages are
`{"type": "mcp", "payload": {...}}` with a JSON-RPC 2.0 payload:

1. `initialize`: the server may pass `capabilities.vision` (URL and token for
   photos). The device answers with `protocolVersion` `2024-11-05` and
   `serverInfo.name` = board name (`cognog-v3`).
2. `tools/list` (paged with `cursor` / `nextCursor`): the device lists its
   tools with a name, description and input schema.
3. `tools/call` with `name` and `arguments`: the device runs the tool and
   answers `{"content": [{"type": "text", "text": "..."}], "isError": false}`,
   or a JSON-RPC error.

The LLM reads the tool **descriptions** to decide when to call a tool, so they
are part of Coglet's behaviour.

### Coglet's tools

Registered in `main/boards/cognog-v3/cognog_v3_board.cc`:

| Tool | Arguments | Does |
|---|---|---|
| `self.coglet.shake_head` | — | `action:shake_head` |
| `self.coglet.blink` | — | `action:blink` |
| `self.coglet.move_left_ear` | — | `action:left_ear` |
| `self.coglet.move_right_ear` | — | `action:right_ear` |
| `self.coglet.move_ears` | — | `action:ears` |
| `self.coglet.reminder.get_time` | — | Device local time and time zone |
| `self.coglet.reminder.create` | `datetime` (local `YYYY-MM-DD HH:MM:SS`), `message` | Saves a reminder |
| `self.coglet.reminder.list` | — | Pending reminders |
| `self.coglet.reminder.cancel` | `id` | Cancels one |
| `self.coglet.reminder.last_due` | — | Text of the reminder that just fired |
| `self.coglet.dance` | `style` (default `random`) | Starts a dance or one of the user's songs |

Plus the common tools from `main/mcp_server.cc`, for example
`self.get_device_status`, `self.audio_speaker.set_volume` and, when the camera
works, `self.camera.take_photo`.

### Adding a tool

In `InitializeTools()` of the board:

```cpp
AddCogletTool(
    "self.coglet.nod",
    "Call when the user asks Coglet to nod. Nods three times.",
    PropertyList(),                      // or PropertyList({Property("times", kPropertyTypeInteger, 1, 1, 5)})
    [this](const PropertyList&) -> ReturnValue {
        SendCogletAction("nod");          // UART "action:nod"
        return true;                      // bool, int or std::string
    });
```

Then add `nod` to `start_mcp_action()` / `update_mcp_action()` in
`RP2040/animation.py`. Name tools `self.<area>.<action>`, and write the
description so the LLM knows exactly when to call it.
