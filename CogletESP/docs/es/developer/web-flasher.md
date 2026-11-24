# Funcionamiento interno del Coglet Updater

[Documentación](../README.md) · [English](../../en/developer/web-flasher.md) · [Deutsch](../../de/developer/web-flasher.md) · **Español** · [日本語](../../ja/developer/web-flasher.md)

El Coglet Updater (<https://will-cogley.github.io/Coglet/>) es una sola página
estática en `tools/web_flasher/`: `index.html`, `coglet_i18n.js` (traducciones)
y `coglet_songs.js` (conversión de canciones). Usa
[esptool-js](https://github.com/espressif/esptool-js) 0.6.1 y Web Serial, así
que necesita un navegador de escritorio basado en Chromium con HTTPS o
`localhost`; las canciones necesitan además WebCodecs (Chrome / Edge 94+).
Instrucciones para usuarios: [Primeros pasos](../user/getting-started.md).

## Actualizar

- La página rechaza todo lo que no sea un ESP32-S3. Cada parte se comprueba con
  el MD5 del manifiesto antes y después de escribirla; el modo, la frecuencia y
  el tamaño de la flash se mantienen como se compilaron.
- Escribe el bootloader, la tabla de particiones, los datos OTA, la aplicación y
  la imagen de assets, nunca NVS, el sector de ajustes ni la biblioteca de
  canciones. **Instalación limpia** borra antes todo el chip.
- Cada botón pide el puerto antes de descargar nada (los navegadores solo
  muestran la lista de puertos justo después de un clic). La elección del
  puerto se recuerda por el ID USB. La lista solo muestra los chips USB serie
  que usa Coglet; **Mostrar todos los puertos** lo muestra todo.
- Si el enlace USB pierde datos, vuelve a escribir a la siguiente velocidad más
  baja (921600 → 460800 → 115200) y recuerda la que funcionó.
- Después de escribir reinicia Coglet, muestra el registro de arranque y lo lee:

| El registro de Coglet dice | La página muestra |
|---|---|
| `RP2040 did not answer` | «Un paso más»: la tarjeta de configuración de la placa de servos |
| `sending N of M files` | actualizando la placa de servos, mantenlo conectado |
| `RP2040 running again` / `up to date` | todo listo |
| `RP2040 update failed` / `did not answer within` | se reintenta en el siguiente arranque; la tarjeta de configuración es la alternativa |

### Comprobar mi Coglet

Lee la tabla de particiones (0x8000), `otadata` (qué ranura arranca) y el primer
1 KB de esa ranura de aplicación. A partir de la descripción de aplicación de
ESP-IDF (versión) y la descripción propia de Coglet (`main/coglet_app_desc.h`:
magic `COGLET`, edición, commit de compilación) indica: actualización
disponible, al día, más nuevo (compilación de prueba), compilación propia del
usuario (`local`), otra compilación de la misma versión, firmware anterior a
v2.3.0 o sin firmware. También selecciona la edición del propio Coglet, luego lo
reinicia e informa del estado de la placa de servos.

### Configuración única del RP2040

Para los RP2040 configurados antes de las actualizaciones automáticas. Con el
interruptor de modo en RP2040, la página detiene el programa en marcha mediante
el REPL crudo de MicroPython, escribe cada archivo como `<name>.tmp`, comprueba
los tamaños, los renombra, escribe el identificador del paquete en
`coglet_bundle.txt` y hace un reinicio suave. No se reemplaza nada hasta que se
han escrito todos los archivos. Necesita MicroPython ya instalado en el RP2040
(todos los kits vienen así).

## Ajustes

Un sector de 4 KB justo antes de la biblioteca de canciones
(`main/coglet_settings.h`): `CGST`, versión, longitud, CRC-32 (zlib) y luego
líneas `key=value`:

| Clave | Valores |
|---|---|
| `wake_word` | frase en inglés, minúsculas a–z, `'` y espacios |
| `threshold` | 1–99 % (la página ofrece 1–50) |
| `startup`, `reminder` | `mecha`, `evil`, `cat`, `christmas`, `elf`, `snowman` |
| `aec` | `on` / `off` |

Solo se guardan los valores que difieren de los predeterminados de la edición
elegida; el resto sigue al firmware (`make_manifest.py` publica los valores
predeterminados en `manifest.json`). Los valores que faltan o no son válidos
vuelven a los de menuconfig. `idf.py flash` escribe aquí un sector en blanco
(`coglet_settings_reset.bin`, añadido por `main/CMakeLists.txt`) para que un
firmware propio empiece con su menuconfig; `make_manifest.py` omite esa parte,
así que la página y los zip de las versiones conservan los ajustes del usuario.
El modelo
MultiNet convierte por sí mismo la palabra de activación en fonemas; si no
puede, Coglet conserva su palabra de activación incorporada y registra
`Wake word "..." from settings can't be used`.

```
I (900) CogletSettings: settings: wake word "hey coglet", threshold 3, startup cat, reminder evil, aec on
```

## Mis canciones

El navegador decodifica cada archivo y encuentra los pulsos con el mismo
análisis que `tools/coglet_music/build_music.py` (`coglet_songs.js` es una
adaptación y da los mismos pulsos). Ajusta la canción a −14 LUFS con un
limitador, la corta a 60 s con un desvanecimiento y la codifica en Ogg/Opus
(mono, 24 kHz, tramas de 60 ms, 32 kbps) con WebCodecs.

La **biblioteca de canciones** son los últimos 2 MB de la partición `assets`
(0xE00000–0x1000000), adonde la imagen de assets nunca llega; `make_manifest.py`
rechaza una compilación cuyos assets llegarían. Estructura
(`main/coglet_music.h`): el sector 0 contiene la cabecera `CGML` y hasta 32
entradas (nombre, preset, BPM, duración, desplazamientos, CRC-32); los datos Ogg
y la tabla de pulsos de cada canción empiezan en su propio sector de 4 KB. La
lista se escribe al final y cada canción tiene su propio CRC, así que un
guardado interrumpido conserva las canciones anteriores y una canción dañada
se omite.

```
I (5120) CogletMusic: song library: 3 songs at assets+0x600000
```

## Idiomas

Inglés, alemán, español y japonés. La página sigue el idioma del navegador (si
no, inglés); el menú 🌐 lo cambia y lo recuerda; `?lang=de|es|ja|en` fuerza uno.
El texto en inglés está en `index.html` (`data-i18n="key"`) y los demás idiomas
son diccionarios en `coglet_i18n.js`; los mensajes de los scripts usan
`t("key", {name: value})` con reglas de plural y formatos numéricos locales. El
registro del dispositivo se queda en inglés.

Para añadir un idioma: añádelo a `LANGS`, crea un diccionario con todas las
claves (mismos `{placeholders}` y marcado) y añade una `<option>` al menú 🌐.

## Aspecto

- *Apariencia*: clara, oscura, día y noche (clara de 7:00 a 19:00) o la del
  navegador.
- Del 1 de diciembre al 6 de enero: un aspecto navideño dibujado con SVG y CSS
  (guirnalda, luces, estrellas o copos de nieve que caen). Un botón lo desactiva
  durante la temporada; `?season=christmas|plain` lo fuerza. Con *reducir
  movimiento* no se mueve nada.
- Accesibilidad: solo con teclado, controles etiquetados, progreso y errores
  anunciados (empiezan con «Error:»), contraste WCAG AA, zoom al 200 %.

## Probar en local

Sirve `index.html`, `coglet_i18n.js` y `coglet_songs.js` junto a una carpeta
`firmware/` generada con `make_manifest.py` a partir de tu compilación (y
`rp2040/` para la configuración única), en `localhost`. Para las demás ediciones,
ejecuta también `make_manifest.py --edition christmas` (o `elf`, `snowman`) sobre
su compilación; sin ellas, la página no muestra la elección de edición.
