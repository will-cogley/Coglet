# Arquitectura

[Documentación](../README.md) · [English](../../en/developer/architecture.md) · [Deutsch](../../de/developer/architecture.md) · **Español** · [日本語](../../ja/developer/architecture.md)

```
 servidor xiaozhi.me ──Wi-Fi── ESP32-S3 ──UART1 115200── RP2040 ──I²C── PCA9685 ── 9 servos
   (voz, LLM)                  voz, palabra de activación, MicroPython └─UART0 921600── Grove Vision AI V2
                               cámara, herramientas MCP,
                               recordatorios, bailes
```

El ESP32-S3 ejecuta el firmware [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
con añadidos de Coglet. Decide **qué** hace Coglet y se lo indica al RP2040 con
líneas de texto cortas. El RP2040 decide **cómo** se mueven los servos.

## Firmware del ESP32-S3

| Dónde | Qué |
|---|---|
| `main/application.cc` | Estados del dispositivo, sesiones de voz, Auto-Awake de arranque de Coglet, flujos de baile y recordatorio; envía cada cambio de estado al RP2040 |
| `main/boards/cognog-v3/` | Placa: pines, cámara, LED rojo, herramientas MCP de Coglet |
| `main/uart_component.cc` | Enlace UART1 con el RP2040 |
| `main/coglet_rp2040_sync.cc` | Mantiene al día el programa del RP2040 |
| `main/coglet_reminder.cc` | Recordatorios (NVS) |
| `main/coglet_settings.cc` | Ajustes guardados desde el Coglet Updater |
| `main/coglet_music*.{h,cc}`, `main/coglet_sounds*` | Canciones, pistas de baile incluidas, sonidos de inicio y de recordatorio |
| `main/audio/` | Cadena de audio, palabra de activación, referencia de AEC por software |

### Estados del dispositivo

`starting → wifi_configuring / activating → idle ⇄ connecting → listening ⇄ speaking → idle`

El LED rojo solo se enciende en `listening`. En `idle`, el RP2040 adopta su
pose de reposo y libera el par de los servos.

**Auto-Awake de arranque:** unos segundos después del sonido de inicio, Coglet
abre por sí solo una sesión de escucha. Mientras se actualiza el RP2040, espera
(como máximo 2 minutos), para que una transferencia nunca coincida con la
primera conversación. Ocurre una vez por arranque; si falla, Coglet se queda
esperando la palabra de activación.

**Sesiones proactivas:** después de un baile y cuando vence un recordatorio,
Coglet abre una sesión por sí solo y envía un texto breve como si fuera una
palabra de activación detectada: `（跳完舞了）` («terminé de bailar») o
`（有提醒到点了）` («vence un recordatorio»). Las descripciones de las
herramientas MCP le dicen al LLM qué hacer con ellos. Se quedan en chino a
propósito: el LLM los entiende en cualquier idioma, y deben tener como máximo
13 caracteres para xiaozhi.me.

## Protocolo UART (ESP → RP2040)

Un comando por línea, terminada en `\r\n`. Cada línea se escribe en una sola
llamada, así que las líneas de distintas tareas nunca se mezclan.

| Línea | Significado |
|---|---|
| `idle`, `listening`, `speaking`, `thinking`, `configuring` … | Estado del dispositivo |
| `neutral`, `happy`, `sad`, `angry`, `surprised`, `sleepy`, `silly`, `confused`, `cool`, `loving`, … | Emoción que envía el LLM con su respuesta |
| `action:shake_head` / `blink` / `left_ear` / `right_ear` / `ears` | Movimiento único desde una herramienta MCP (tres ciclos) |
| `dance:<style>` | Empezar un baile incluido, p. ej. `dance:mecha` |
| `dance:stop` | Detener cualquier baile ya |
| `prep:<style>` / `prep:groove-<preset>` | La conversación se cierra para bailar: mantener los servos encendidos e ir a la pose inicial del baile en lugar de dormir (termina al empezar el baile, con `dance:stop` o a los 15 s) |
| `groove:<energetic\|calm>:<bpm>` | Empezar a bailar una canción propia |
| `gb:<s><e><b>` | Un pulso de una canción propia: acento 0–9, energía de la sección 0–9, inicio de compás 0/1 |
| `groove:end` | Fin de la canción propia |
| `upd:…` | Protocolo de actualización del RP2040 (abajo) |

El RP2040 asigna estados y emociones a animaciones en `animation.state_map`;
las líneas desconocidas se ignoran. Las emociones no detienen la boca: solo las
líneas de estado (`idle`, `listening`, `thinking`, `neutral`, …) terminan la
animación de hablar.

## Programa del RP2040

| Archivo | Función |
|---|---|
| `main.py` | Lanzador mínimo: termina una actualización interrumpida, ejecuta `app.py` y pasa al modo de recuperación si `app.py` no arranca |
| `app.py` | Bucle principal: UART, interruptores, control de los servos, liberación del par |
| `animation.py` | Tabla de servos, poses, animaciones de estado, parpadeo, boca al hablar, acciones MCP |
| `servoclass.py` | Controlador del PCA9685 y `Servo` con límites de velocidad y aceleración |
| `vision.py` | Seguimiento de caras con Grove Vision AI (ojos y cabeceo; en los límites de los ojos toma el relevo el giro de la base) |
| `music.py`, `dance_*.py` | Reproductor de bailes y coreografías generadas |
| `coglet_updater.py` | Recibe las actualizaciones del ESP |

Quién controla los servos, de mayor a menor prioridad:

1. **Modo de calibración** (interruptor): todo en la pose de calibración; el
   botón de prueba de servos mueve ±10°.
2. **Baile**
3. **Acción MCP** (`action:…`)
4. **Animación de estado**, parpadeo, seguimiento de caras (solo fuera de idle
   y con el interruptor de seguimiento de caras activado), boca al hablar.

Cuando la pose de idle se ha asentado, el RP2040 espera 500 ms y pone a nivel
alto el nOE del PCA9685, lo que libera todo el par. Cualquier otro estado
vuelve a encender los servos uno a uno ([Alimentación](power.md)).

## Actualizaciones del RP2040

`tools/rp2040_bundle/build_bundle.py` empaqueta `RP2040/*.py` en el firmware del
ESP en cada compilación; el identificador del paquete es un hash de todos los
archivos. Unos 5 s después del arranque, el ESP pide el identificador del
paquete del RP2040. Si es distinto, pide el tamaño y el CRC de cada archivo y
envía solo los que han cambiado:

```
ESP → upd:ver?                       RP → upd:ver:<id>|none
ESP → upd:crc?:<name>                RP → upd:crc:<name>:<size>:<crc32> | upd:crc:<name>:none
ESP → upd:begin:<id>:<files>         RP → upd:ready
ESP → upd:file:<name>:<size>:<crc>   RP → upd:ok:f
ESP → upd:d:<seq>:<base64>           RP → upd:ok:<seq>      (las repeticiones se confirman de nuevo)
ESP → upd:end                        RP → upd:ok:e | upd:err:<why>
ESP → upd:commit                     RP → upd:done, y se reinicia
ESP → upd:abort                      se borran los archivos preparados
```

El RP2040 escribe archivos `<name>.new`, comprueba el tamaño y el CRC-32, y solo
los renombra cuando han llegado todos. La lista de archivos que se van a
renombrar se escribe primero, así que un corte de corriente a mitad se completa
en el siguiente arranque. Durante una transferencia, los servos están
liberados. Una transferencia completa tarda alrededor de medio minuto; una
habitual, unos segundos.

Registro del ESP (etiqueta `CogletRp2040`): `RP2040 up to date`,
`RP2040 updated (bundle …)`,
`RP2040 did not answer: it needs the one-time setup from the web flasher`,
`RP2040 update failed … retried on the next boot`.

Los RP2040 antiguos sin el actualizador necesitan una vez la configuración del
Coglet Updater ([Funcionamiento interno del Coglet Updater](web-flasher.md#configuración-única-del-rp2040)).

## Recordatorios

Hasta 12 recordatorios de una sola vez de un máximo de 120 bytes cada uno,
guardados en NVS como horas UTC, para que un cambio de zona horaria nunca mueva
un recordatorio guardado. La zona horaria viene del `timezone_offset` del
servidor (comprobación OTA) o de una cadena TZ POSIX en menuconfig. Cuando vence
un recordatorio y Coglet está inactivo (un baile termina primero), Coglet toca
el sonido de recordatorio y luego abre una sesión proactiva en la que el LLM
llama a `self.coglet.reminder.last_due` y lo dice en una frase.

## Datos guardados

| Datos | Dónde | Se conservan al actualizar |
|---|---|---|
| Wi-Fi, vinculación, recordatorios | partición NVS | sí |
| Ajustes (sector `CGST`) | 4 KB antes de la biblioteca de canciones, en `assets` | sí (`idf.py flash` los restablece) |
| Biblioteca de canciones (`CGML`) | últimos 2 MB de `assets` (0xE00000–0x1000000) | sí |
| Aplicación, imagen de assets | `ota_0` / `ota_1`, `assets` | se reemplazan |

Tabla de particiones: `partitions/v2/16m.csv`.
