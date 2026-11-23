# Protocolos: servidor y herramientas MCP

[Documentación](../README.md) · [English](../../en/developer/protocols.md) · [Deutsch](../../de/developer/protocols.md) · **Español** · [日本語](../../ja/developer/protocols.md)

Coglet usa sin cambios los protocolos del proyecto original
[xiaozhi-esp32](https://github.com/78/xiaozhi-esp32). Esta página es un resumen
para quienes desarrollan Coglet; la referencia son la
[documentación original](https://github.com/78/xiaozhi-esp32/tree/main/docs) y
el código (`main/protocols/`, `main/mcp_server.cc`).

## Conexión

1. Al arrancar, el dispositivo llama a la **URL OTA** (`CONFIG_OTA_URL`, por
   defecto la API de xiaozhi.me) con su tipo de placa (`cognog-v3`), la versión
   del firmware y sus identificadores. La respuesta trae la hora y la zona
   horaria del servidor, la configuración de transporte (MQTT + UDP o
   WebSocket), un código de activación si el dispositivo aún no está vinculado
   y, a veces, un firmware más nuevo.
2. Cuando empieza una sesión (palabra de activación, botón, Auto-Awake), el
   dispositivo abre el canal de audio y ambos lados intercambian un mensaje
   `hello`.
3. El audio es **Opus** en tramas de 60 ms: 16 kHz mono desde el dispositivo y,
   de vuelta, la frecuencia de muestreo del servidor (normalmente 24 kHz). Los
   mensajes de control son JSON.

### WebSocket

Una conexión WebSocket lleva tramas de texto JSON y tramas binarias Opus.
Cabeceras del handshake: `Authorization: Bearer <token>`, `Protocol-Version`,
`Device-Id` (dirección MAC), `Client-Id` (UUID; se reinicia al borrar la flash).

```json
{"type": "hello", "version": 1, "features": {"mcp": true}, "transport": "websocket",
 "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60}}
```

El servidor debe responder con `"type": "hello"` y `"transport": "websocket"` en
menos de 10 s, opcionalmente con un `session_id`.

### MQTT + UDP

Los mensajes JSON van por MQTT (keepalive de 240 s) y el audio por UDP. La
respuesta `hello` del servidor contiene el servidor UDP, el puerto y la clave y
el nonce AES. Cada paquete UDP es

```
|type 1|flags 1|payload_len 2|ssrc 4|timestamp 4|sequence 4|payload (Opus cifrado con AES-CTR)|
```

en orden de bytes de red. Se descartan los paquetes con un número de secuencia
menor del esperado. Una sesión termina con `{"type": "goodbye"}`.

### Mensajes JSON

Dispositivo → servidor:

| `type` | Campos | Significado |
|---|---|---|
| `listen` | `state`: `start` / `stop` / `detect`, `mode`: `auto` / `manual` / `realtime`, `text` | Empezar o dejar de escuchar; `detect` comunica la palabra de activación (o un texto de aviso de Coglet) |
| `abort` | `reason` | Detener la respuesta actual, p. ej. ante una palabra de activación mientras habla |
| `mcp` | `payload` | Mensaje JSON-RPC 2.0, ver abajo |

Servidor → dispositivo:

| `type` | Significado |
|---|---|
| `stt` | Voz del usuario reconocida |
| `llm` | `emotion` de la respuesta, p. ej. `happy`. **Coglet la reenvía al RP2040**, que reproduce la animación correspondiente |
| `tts` | `state`: `start`, `sentence_start` (con `text`), `stop`. `start` pone a Coglet en `speaking` |
| `mcp` | Petición JSON-RPC 2.0 |
| `system` | `command`: `reboot` |

## MCP

El servidor es el cliente MCP y el dispositivo, el servidor MCP. Los mensajes
son `{"type": "mcp", "payload": {...}}` con una carga JSON-RPC 2.0:

1. `initialize`: el servidor puede pasar `capabilities.vision` (URL y token para
   las fotos). El dispositivo responde con `protocolVersion` `2024-11-05` y
   `serverInfo.name` = nombre de la placa (`cognog-v3`).
2. `tools/list` (paginado con `cursor` / `nextCursor`): el dispositivo enumera
   sus herramientas con nombre, descripción y esquema de entrada.
3. `tools/call` con `name` y `arguments`: el dispositivo ejecuta la herramienta
   y responde `{"content": [{"type": "text", "text": "..."}], "isError": false}`
   o un error JSON-RPC.

El LLM lee las **descripciones** de las herramientas para decidir cuándo
llamarlas, así que forman parte del comportamiento de Coglet.

### Herramientas de Coglet

Registradas en `main/boards/cognog-v3/cognog_v3_board.cc`:

| Herramienta | Argumentos | Hace |
|---|---|---|
| `self.coglet.shake_head` | — | `action:shake_head` |
| `self.coglet.blink` | — | `action:blink` |
| `self.coglet.move_left_ear` | — | `action:left_ear` |
| `self.coglet.move_right_ear` | — | `action:right_ear` |
| `self.coglet.move_ears` | — | `action:ears` |
| `self.coglet.reminder.get_time` | — | Hora local y zona horaria del dispositivo |
| `self.coglet.reminder.create` | `datetime` (local `YYYY-MM-DD HH:MM:SS`), `message` | Guarda un recordatorio |
| `self.coglet.reminder.list` | — | Recordatorios pendientes |
| `self.coglet.reminder.cancel` | `id` | Cancela uno |
| `self.coglet.reminder.last_due` | — | Texto del recordatorio que acaba de vencer |
| `self.coglet.dance` | `style` (por defecto `random`) | Empieza un baile o una canción del usuario |

Además están las herramientas comunes de `main/mcp_server.cc`, por ejemplo
`self.get_device_status`, `self.audio_speaker.set_volume` y, si la cámara
funciona, `self.camera.take_photo`.

### Añadir una herramienta

En `InitializeTools()` de la placa:

```cpp
AddCogletTool(
    "self.coglet.nod",
    "Call when the user asks Coglet to nod. Nods three times.",
    PropertyList(),                      // o PropertyList({Property("times", kPropertyTypeInteger, 1, 1, 5)})
    [this](const PropertyList&) -> ReturnValue {
        SendCogletAction("nod");          // UART "action:nod"
        return true;                      // bool, int o std::string
    });
```

Luego añade `nod` a `start_mcp_action()` / `update_mcp_action()` en
`RP2040/animation.py`. Nombra las herramientas como `self.<área>.<acción>` y
escribe la descripción de forma que el LLM sepa exactamente cuándo llamarla.
