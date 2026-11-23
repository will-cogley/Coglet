# Protokolle: Server und MCP-Tools

[Dokumentation](../README.md) · [English](../../en/developer/protocols.md) · **Deutsch** · [Español](../../es/developer/protocols.md) · [日本語](../../ja/developer/protocols.md)

Coglet verwendet die Protokolle des Upstream-Projekts
[xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) unverändert. Diese Seite
ist eine Zusammenfassung für Coglet-Entwickler; maßgeblich sind die
[Upstream-Dokumente](https://github.com/78/xiaozhi-esp32/tree/main/docs) und der
Code (`main/protocols/`, `main/mcp_server.cc`).

## Verbindung

1. Beim Start ruft das Gerät die **OTA-URL** (`CONFIG_OTA_URL`, standardmäßig
   die xiaozhi.me-API) mit seinem Platinentyp (`cognog-v3`), seiner
   Firmware-Version und seinen IDs auf. Die Antwort enthält Serverzeit und
   Zeitzone, die Transporteinstellungen (MQTT + UDP oder WebSocket), einen
   Aktivierungscode, falls das Gerät noch nicht gekoppelt ist, und
   gegebenenfalls eine neuere Firmware.
2. Beginnt eine Sitzung (Aktivierungswort, Taste, Auto-Awake), öffnet das Gerät
   den Audiokanal, und beide Seiten tauschen eine `hello`-Nachricht aus.
3. Audio ist **Opus** mit 60-ms-Frames: 16 kHz mono vom Gerät, zurück mit der
   Abtastrate des Servers (meist 24 kHz). Steuernachrichten sind JSON.

### WebSocket

Eine WebSocket-Verbindung trägt JSON-Textframes und binäre Opus-Frames.
Handshake-Header: `Authorization: Bearer <token>`, `Protocol-Version`,
`Device-Id` (MAC-Adresse), `Client-Id` (UUID, wird durch Löschen zurückgesetzt).

```json
{"type": "hello", "version": 1, "features": {"mcp": true}, "transport": "websocket",
 "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60}}
```

Der Server muss innerhalb von 10 s mit `"type": "hello"` und
`"transport": "websocket"` antworten, optional mit einer `session_id`.

### MQTT + UDP

JSON-Nachrichten laufen über MQTT (Keepalive 240 s), Audio über UDP. Die
`hello`-Antwort des Servers enthält UDP-Server, Port sowie AES-Schlüssel und
Nonce. Jedes UDP-Paket ist

```
|type 1|flags 1|payload_len 2|ssrc 4|timestamp 4|sequence 4|payload (AES-CTR-verschlüsseltes Opus)|
```

in Netzwerk-Bytereihenfolge. Pakete mit einer kleineren Sequenznummer als
erwartet werden verworfen. Eine Sitzung endet mit `{"type": "goodbye"}`.

### JSON-Nachrichten

Gerät → Server:

| `type` | Felder | Bedeutung |
|---|---|---|
| `listen` | `state`: `start` / `stop` / `detect`, `mode`: `auto` / `manual` / `realtime`, `text` | Zuhören starten oder beenden; `detect` meldet das Aktivierungswort (oder einen Coglet-Hinweistext) |
| `abort` | `reason` | Aktuelle Antwort abbrechen, z. B. bei einem Aktivierungswort während des Sprechens |
| `mcp` | `payload` | JSON-RPC-2.0-Nachricht, siehe unten |

Server → Gerät:

| `type` | Bedeutung |
|---|---|
| `stt` | Erkannte Sprache des Nutzers |
| `llm` | `emotion` der Antwort, z. B. `happy`. **Coglet leitet sie an den RP2040 weiter**, der die passende Animation abspielt |
| `tts` | `state`: `start`, `sentence_start` (mit `text`), `stop`. `start` versetzt Coglet in `speaking` |
| `mcp` | JSON-RPC-2.0-Anfrage |
| `system` | `command`: `reboot` |

## MCP

Der Server ist der MCP-Client, das Gerät der MCP-Server. Nachrichten haben die
Form `{"type": "mcp", "payload": {...}}` mit einer JSON-RPC-2.0-Nutzlast:

1. `initialize`: Der Server kann `capabilities.vision` übergeben (URL und Token
   für Fotos). Das Gerät antwortet mit `protocolVersion` `2024-11-05` und
   `serverInfo.name` = Platinenname (`cognog-v3`).
2. `tools/list` (seitenweise mit `cursor` / `nextCursor`): Das Gerät listet
   seine Tools mit Name, Beschreibung und Eingabeschema auf.
3. `tools/call` mit `name` und `arguments`: Das Gerät führt das Tool aus und
   antwortet `{"content": [{"type": "text", "text": "..."}], "isError": false}`
   oder mit einem JSON-RPC-Fehler.

Das LLM liest die **Beschreibungen** der Tools, um zu entscheiden, wann es ein
Tool aufruft. Sie gehören also zu Coglets Verhalten.

### Coglets Tools

Registriert in `main/boards/cognog-v3/cognog_v3_board.cc`:

| Tool | Argumente | Wirkung |
|---|---|---|
| `self.coglet.shake_head` | — | `action:shake_head` |
| `self.coglet.blink` | — | `action:blink` |
| `self.coglet.move_left_ear` | — | `action:left_ear` |
| `self.coglet.move_right_ear` | — | `action:right_ear` |
| `self.coglet.move_ears` | — | `action:ears` |
| `self.coglet.reminder.get_time` | — | Lokale Zeit und Zeitzone des Geräts |
| `self.coglet.reminder.create` | `datetime` (lokal `YYYY-MM-DD HH:MM:SS`), `message` | Speichert eine Erinnerung |
| `self.coglet.reminder.list` | — | Ausstehende Erinnerungen |
| `self.coglet.reminder.cancel` | `id` | Löscht eine davon |
| `self.coglet.reminder.last_due` | — | Text der gerade fälligen Erinnerung |
| `self.coglet.dance` | `style` (Standard `random`) | Startet einen Tanz oder einen Song des Nutzers |

Dazu kommen die allgemeinen Tools aus `main/mcp_server.cc`, zum Beispiel
`self.get_device_status`, `self.audio_speaker.set_volume` und, wenn die Kamera
funktioniert, `self.camera.take_photo`.

### Ein Tool hinzufügen

In `InitializeTools()` der Platine:

```cpp
AddCogletTool(
    "self.coglet.nod",
    "Call when the user asks Coglet to nod. Nods three times.",
    PropertyList(),                      // oder PropertyList({Property("times", kPropertyTypeInteger, 1, 1, 5)})
    [this](const PropertyList&) -> ReturnValue {
        SendCogletAction("nod");          // UART "action:nod"
        return true;                      // bool, int oder std::string
    });
```

Fügen Sie dann `nod` zu `start_mcp_action()` / `update_mcp_action()` in
`RP2040/animation.py` hinzu. Benennen Sie Tools nach dem Muster
`self.<bereich>.<aktion>` und schreiben Sie die Beschreibung so, dass das LLM
genau weiß, wann es das Tool aufrufen soll.
