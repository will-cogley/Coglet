# Compilar el firmware

[Documentación](../README.md) · [English](../../en/developer/build.md) · [Deutsch](../../de/developer/build.md) · **Español** · [日本語](../../ja/developer/build.md)

## Versión de ESP-IDF: v5.5.3

Usa **ESP-IDF v5.5.3**, ni más antigua ni más nueva. Las compilaciones oficiales
se ejecutan en el contenedor oficial `espressif/idf:v5.5.3`
(`.github/workflows/firmware.yml`), y `dependencies.lock` fija los componentes
gestionados para esa versión. Otra versión puede compilar, pero no es lo que
ejecutan los Coglet.

### Instalación

**Windows:** ejecuta el [instalador de ESP-IDF para Windows](https://dl.espressif.com/dl/esp-idf/)
y elige **v5.5.3**. Compila desde la *ESP-IDF 5.5 PowerShell* (o CMD) que instala.

**Linux / macOS:**

```bash
git clone -b v5.5.3 --recursive https://github.com/espressif/esp-idf.git ~/esp/esp-idf-v5.5.3
cd ~/esp/esp-idf-v5.5.3
./install.sh esp32s3
. ./export.sh          # en cada terminal nueva
```

Comprobación: `idf.py --version` muestra `ESP-IDF v5.5.3`.

Opcional: **ffmpeg** con libopus, solo para las canciones de la carpeta `Music/`
([Bailes y canciones](dance.md#la-carpeta-music)). Windows: `winget install Gyan.FFmpeg`.

## Compilar y grabar

```bash
cd CogletESP
idf.py build
idf.py -p <puerto> flash monitor
```

- El destino (esp32s3), el tipo de placa y todas las opciones de Coglet están en
  el `sdkconfig` del repositorio. **No ejecutes `idf.py set-target`**: regenera
  `sdkconfig` a partir de los valores predeterminados y descarta la
  configuración de Coglet.
- Conecta el puerto USB-C superior (de programación), con el interruptor de
  modo en **ESP**.
- `<puerto>` es por ejemplo `COM5` en Windows, `/dev/ttyACM0` o `/dev/ttyUSB0`
  en Linux, `/dev/cu.usbmodem…` en macOS.
- `idf.py flash` conserva el Wi-Fi, la vinculación, los recordatorios y las
  canciones añadidas en el Coglet Updater, pero restablece los ajustes guardados
  allí (palabra de activación, umbral, sonidos, Interrumpir a Coglet), para que
  se aplique tu menuconfig. `idf.py app-flash` conserva esos ajustes.
  `idf.py erase-flash` lo borra todo.
- La primera compilación descarga los componentes gestionados; las siguientes
  son incrementales.

Tipo de placa: **NMRobotics Coglet (CogNog V3.0 PCB)**
(`CONFIG_BOARD_TYPE_COGNOG_V3`), archivos de la placa en
[`main/boards/cognog-v3/`](../../../main/boards/cognog-v3). Se identifica como
`cognog-v3` y es el único tipo de placa de este firmware (hasta la 2.3.x, Coglet
usaba el tipo genérico de xiaozhi `bread-compact-wifi-s3cam`). El modelo de la
palabra de activación (MultiNet), el procesamiento de audio y la imagen de
assets están fijados para Coglet y no aparecen en menuconfig.

## Ediciones

Estándar, Navidad, Duende y Muñeco de nieve solo se diferencian en los tres
bailes incluidos y en los sonidos de inicio y de recordatorio predeterminados.
Cada una es una capa sobre `sdkconfig` y se compila en su propia carpeta:

```bash
idf.py -B build-christmas -D SDKCONFIG=build-christmas/sdkconfig \
       -D SDKCONFIG_DEFAULTS="sdkconfig;sdkconfig.christmas" build
idf.py -B build-christmas -p <puerto> flash
```

Usa `sdkconfig.elf` / `build-elf` o `sdkconfig.snowman` / `build-snowman` de la
misma forma. O elígela en menuconfig: *NMRobotics Coglet Dance → Firmware edition*.

## menuconfig

`idf.py menuconfig`. Las opciones de Coglet:

| Menú | Opciones |
|---|---|
| Xiaozhi Assistant | Tipo de placa, palabra de activación (por defecto «hello coglet»), cancelación de eco en el dispositivo (`USE_DEVICE_AEC`, `COGLET_AEC_DEFAULT_OFF`, `COGLET_AEC_REF_DELAY_MS`), registro de nivel del micrófono (`COGLET_MIC_DIAG_LOG`) |
| NMRobotics Coglet Reminder | Decir el recordatorio después del sonido; zona horaria (automática desde el servidor o una cadena TZ POSIX) |
| NMRobotics Coglet RP2040 | Actualizar el programa del RP2040 automáticamente |
| NMRobotics Coglet Dance | Bailes incluidos, edición del firmware, canciones de `Music/`, tamaño de la biblioteca de canciones, desfase del ritmo |
| NMRobotics Coglet Sounds | Sonidos de inicio y de recordatorio predeterminados |

Los valores guardados desde el Coglet Updater (palabra de activación, umbral,
sonidos, AEC) tienen prioridad sobre menuconfig. `idf.py flash` los borra, así
que después de grabar tu propio firmware se aplica su menuconfig hasta que se
vuelvan a guardar ajustes en la página. Actualizar con el Coglet Updater los
conserva.

## Versión del firmware

La versión es `PROJECT_VER` en `CogletESP/CMakeLists.txt` (las compilaciones
oficiales la toman de la etiqueta de git). Usa solo números como `2.3.2`,
opcionalmente con un `-sufijo`: la comprobación OTA los compara número a número.

## Cambiar el programa del RP2040

El RP2040 ejecuta MicroPython; su programa está en [`RP2040/`](../../../RP2040).
Cada compilación del ESP empaqueta estos archivos en el firmware, y el ESP envía
al RP2040 cualquier archivo cambiado después de arrancar
([Arquitectura](architecture.md#actualizaciones-del-rp2040)). Así que la forma
normal de cambiar el RP2040 es editar los archivos y grabar el ESP.

Con Thonny (interruptor de modo en **RP2040**) puedes subir archivos
directamente mientras experimentas. El ESP verá entonces un paquete distinto en
su siguiente arranque y volverá a poner su propia copia, así que mantén el
firmware del ESP y `RP2040/` en el mismo commit, o desactiva *NMRobotics Coglet
RP2040 → Update the RP2040 program automatically* mientras experimentas.

Nota: cualquier cambio en un archivo del RP2040, incluso en un comentario, hace
que cada Coglet vuelva a enviar ese archivo en su siguiente actualización.

## Registros

`idf.py monitor` muestra el registro del ESP; **Mostrar registro del
dispositivo** en el Coglet Updater muestra lo mismo. El RP2040 escribe en su
propio puerto serie USB (interruptor de modo en RP2040). Etiquetas útiles:
`CogletRp2040` (actualizaciones de la placa de servos), `CogletDance`,
`CogletReminder`, `CogletSettings`, `CogletMusic`, `CogletAutoAwake`.
