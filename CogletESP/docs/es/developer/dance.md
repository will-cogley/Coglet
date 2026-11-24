# Bailes y canciones

[Documentación](../README.md) · [English](../../en/developer/dance.md) · [Deutsch](../../de/developer/dance.md) · **Español** · [日本語](../../ja/developer/dance.md)

Cuando el usuario le pide a Coglet que baile, la herramienta MCP
`self.coglet.dance(style)`:

1. deja que el LLM responda con una frase corta («Watch this!»);
2. termina la conversación;
3. reproduce la canción mientras el RP2040 mueve cada servo al ritmo;
4. abre por sí sola una sesión nueva con el aviso `（跳完舞了）` y pregunta al
   usuario qué le ha parecido.

| | Pistas incluidas | Canciones propias |
|---|---|---|
| Música | tres arreglos propios o de dominio público de unos 30 s por edición | carpeta `Music/` (compiladas en el firmware) o *Mis canciones* en el Coglet Updater (biblioteca de canciones) |
| Baile | coreografía escrita a mano, generada a partir de la misma partitura que la música | automático: los pulsos se detectan de antemano y se envían al RP2040 mientras suena la canción |
| Archivos del RP2040 | `music.py` + `dance_data.py` / `dance_xmas.py` / `dance_elf.py` / `dance_snow.py` | solo `music.py` |

## Pistas incluidas

| Edición | `style` | Música | Tempo |
|---|---|---|---|
| Estándar | `mecha` | electro mecha contundente, fa menor | 128 BPM |
| | `evil` | gótico sombrío, re menor armónica | 96 BPM |
| | `cat` | pop gatuno de anime suave, do mayor | 120 BPM |
| Navidad | `lyrical` | Noche de paz | 104 BPM, 3/4 |
| | `classic` | Jingle Bells | 136 BPM |
| | `grand` | Al mundo paz (Joy to the World) | 84 BPM, 2/4 |
| Duende | `workshop` | Deck the Halls | 132 BPM |
| | `mischief` | God Rest Ye Merry Gentlemen | 156 BPM |
| | `party` | We Wish You a Merry Christmas | 160 BPM, 3/4 |
| Muñeco de nieve | `lullaby` | Brahms, Canción de cuna op. 49/4 | 104 BPM, 3/4 |
| | `stomp` | Good King Wenceslas | 108 BPM |
| | `blizzard` | Leontóvich, Shchedryk (1914; Carol of the Bells) | 150 BPM, 3/4 |

`random` elige una de las tres de la edición. Solo caben en el firmware las
pistas de una edición; el RP2040 conoce las coreografías de todas e importa solo
el módulo que necesita. Cada baile llega a su pose final 1,5 s antes de que
termine la música, así que Coglet se asienta antes de la sesión siguiente.

## Canciones propias

Dos orígenes, que se bailan igual:

- **Mis canciones** en el Coglet Updater: se convierten en el navegador, se
  guardan en la biblioteca de canciones fuera del firmware y se conservan al
  actualizar ([Funcionamiento interno del Coglet Updater](web-flasher.md#mis-canciones)).
- **La carpeta `Music/`**: se compilan en tu propio firmware (abajo).

### Presets

| Preset | Qué se mueve | Estilo |
|---|---|---|
| energetic (enérgico) | todos los servos | cabeceo en cada pulso (más hondo en los acentos), golpes de orejas, balanceo y giros de la base en cada compás, ojos al ritmo, parpadeos, boca en los golpes más fuertes; escala con el volumen de la canción |
| calm (tranquilo) | orejas, cabeza (cabeceo y alabeo) y base | cabeceo lento en el pulso que se siente, orejas a la deriva, balanceo ligero; **el párpado y los dos servos de los ojos quedan sin par** durante toda la canción |

Las canciones tranquilas siguen el pulso que se siente: una balada de 136 BPM
que se siente a 68 cabecea a 68.

### La carpeta `Music/`

1. Pon archivos de audio en `CogletESP/Music/`: mp3, wav, flac, m4a, aac, ogg,
   opus, wma, aiff o un video (mp4, mov, m4v, webm, mkv; se usa su audio).
2. `idf.py build`. `tools/coglet_music/build_music.py` convierte cada archivo a
   Ogg/Opus (mono, 24 kHz, tramas de 60 ms, volumen normalizado), lo corta a la
   duración máxima con un desvanecimiento, detecta el tempo, los pulsos, los
   acentos, las secciones y los inicios de compás, elige un preset y lo compila.
   Los resultados se guardan en caché en `build/coglet_music/cache/`.
3. Graba el firmware y di «baila *Night Rain*» o «baila una de mis canciones».
   El nombre de la canción es el nombre del archivo sin extensión ni etiquetas.

Fuerza el preset o el tempo con etiquetas antes de la extensión:

```
Night Rain.calm.mp3
Drop It.energetic.wav
Free Fall.calm.68bpm.m4a
```

Necesita ffmpeg con libopus; sin él, las canciones se omiten con un aviso y la
compilación sigue funcionando. `Music/.gitignore` mantiene tus canciones fuera
de git. **No publiques imágenes de firmware con música sobre la que no tengas
derechos.**

menuconfig, *NMRobotics Coglet Dance*:

| Opción | Por defecto | |
|---|---|---|
| Custom songs from the Music folder | activada | |
| ffmpeg executable | `ffmpeg` | nombre o ruta completa; en Windows con barras normales, p. ej. `C:/ffmpeg/bin/ffmpeg.exe` |
| Maximum length per song | 60 s | |
| Opus bitrate | 32 kbps | unos 240 KB por minuto |
| Flash budget for all custom songs | 400 KB | las canciones que no caben se omiten |
| Song library size | 2048 KB | espacio para canciones añadidas desde el Coglet Updater |
| Beat timing offset | 20 ms | movimientos tarde → bájalo, temprano → súbelo |

## Cómo funciona

ESP (`main/application.cc`):

```
self.coglet.dance(style)
  WaitAck   espera la respuesta de una línea (TTS terminado, audio en reposo; máx. 10–20 s)
  Starting  "prep:<style>" (el RP2040 deja los servos encendidos y va a la pose inicial),
            cierra el canal de audio → idle
  Playing   incluida: "dance:<style>", una tarea reproduce la pista
            propia:   "groove:<preset>:<bpm>", una tarea reproduce la canción, otra
                      envía "gb:<strength><energy><bar>" en cada pulso y luego "groove:end"
  FollowUp  1 s después de la música: sesión proactiva con "（跳完舞了）"
```

- Una palabra de activación o el botón detienen el baile al instante
  (`dance:stop`), y empieza la conversación del usuario en lugar de la pregunta
  posterior.
- Un recordatorio que vence durante un baile espera al final y sustituye a la
  pregunta posterior.
- `AudioService::PlaySound()` acepta un indicador de cancelación, así que las
  canciones se detienen en ~10 ms.

RP2040 (`RP2040/music.py`): un baile controla todos los servos (solo el modo de
calibración tiene más prioridad). Sincronización: `AUDIO_LATENCY_MS = 120` (del
comando al sonido) y `SERVO_LEAD_MS = 100` (los movimientos empiezan antes para
caer en el pulso). Si los pulsos dejan de llegar durante 4 s en una canción
propia, el baile termina solo. Después se restauran los límites de movimiento
predeterminados y se vuelve a aplicar el estado actual.

## Regenerar las pistas incluidas

`tools/coglet_dj/` (Python con numpy y scipy, más ffmpeg):

```bash
cd tools/coglet_dj
python3 render.py mecha evil cat                    # out/*.ogg, previsualizaciones, JSON de coreografía
python3 export_rp2040.py ../../RP2040/dance_data.py
```

Para cambiar solo la coreografía: edita `choreo.py`, ejecuta `choreo_only.py` y
luego `export_rp2040.py`. Las ediciones navideñas funcionan igual con
`xmas.py` / `choreo_xmas.py` / `export_xmas_rp2040.py` / `export_xmas_headers.py`
y sus equivalentes `elf` y `snow`. Los exportadores de cabeceras leen
`out/approved/`, así que solo llega a `main/coglet_sounds/` audio que alguien
ha escuchado. Los archivos `dance_*.py` generados no se editan a mano.
