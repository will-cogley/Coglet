# Cancelación de eco en el dispositivo (AEC)

[Documentación](../README.md) · [English](../../en/developer/audio-aec.md) · [Deutsch](../../de/developer/audio-aec.md) · **Español** · [日本語](../../ja/developer/audio-aec.md)

Con AEC, el usuario puede interrumpir a Coglet: sigue escuchando mientras habla
y se puede cortar sin la palabra de activación. Los usuarios lo cambian con
**Interrumpir a Coglet** en el Coglet Updater.

## Cómo funciona

El micrófono y el amplificador MAX98357A están en dos puertos I2S separados, y
no hay un retorno por hardware de la señal del altavoz, así que la AEC de serie
del dispositivo no puede funcionar. Coglet genera la referencia por software en
el ESP32-S3, sin AEC en el servidor:

1. Cada vez que el DMA I2S TX del altavoz ha enviado un bloque de 10 ms, su
   callback `on_sent` ve el PCM que realmente fue al amplificador.
2. Cada vez que el DMA I2S RX del micrófono ha recibido un bloque de 15 ms,
   `on_recv` también lo ve.
3. Ambos callbacks llevan marca de tiempo con `esp_timer`. `SoftwareAecReference`
   suaviza las marcas con un seguidor de reloj, empareja cada muestra del
   micrófono con la muestra del altavoz reproducida en el mismo instante y
   remuestrea de 24 kHz a 16 kHz con antialiasing.
4. `Read()` devuelve `[mic, ref]` intercalados, el formato `MR` de la AEC del AFE
   de esp-sr.
5. Con AEC, todas las formas de despertar usan el modo de escucha **realtime**,
   incluido el Auto-Awake de arranque.

Con AEC desactivada no se ejecuta nada de esto: la cadena de audio es la misma
que en un firmware sin AEC.

## Configuración

| Opción | Firmware publicado | |
|---|---|---|
| `CONFIG_USE_DEVICE_AEC` | activada | AEC compilada |
| `CONFIG_COGLET_AEC_DEFAULT_OFF` | activada | desactivada hasta que el usuario la activa (ajuste `aec=on`) |
| `CONFIG_COGLET_AEC_REF_DELAY_MS` | 0 | desfase de la referencia, −10…20 ms |

El ajuste se lee una vez al arrancar (`CogletSettings::DeviceAec()`), así que
cambiarlo reinicia Coglet. Si no se puede reservar la referencia, Coglet
registra `Device AEC unavailable on this boot` y escucha como sin AEC.

## Comprobarlo en el dispositivo

Registro de arranque:

```
NoAudioCodec: [AEC-REF] software loopback ENABLED: mic 16000 Hz (slot 0/2), speaker 24000 Hz ...
CogletAutoAwake: BOOT_LISTENING: mode=realtime
CogletSettings: Device AEC: on (from settings)
```

`AfeAudioProcessor` no debe decir `no reference channel`.

Con *Coglet: log microphone levels every second* (`CONFIG_COGLET_MIC_DIAG_LOG`)
aparece una línea por segundo:

```
[MIC] mode=aec-ref ... | [AEC-REF] refPeak=... offset=..us missing=.. late=.. micOvr=.. refOvr=.. resync=a/b torn=..
```

| Campo | Correcto |
|---|---|
| `refPeak` | claramente por encima de 0 mientras Coglet habla, 0 en silencio |
| `offset` | estable dentro de unos milisegundos (importa más la estabilidad que el valor) |
| `missing` / `late` | apenas crecen |
| `micOvr` | crece al pasar entre palabra de activación y conversación: normal |
| `resync` | 1 cada uno al arrancar, luego estable |
| `torn` | siempre 0 |

Prueba de escucha: deja que Coglet dé una respuesta larga e interrúmpelo; debe
parar y entenderte. Mientras tú estés en silencio, no debe interrumpirse a sí
mismo.

## Alinear la referencia

1. Activa *Enable Audio Debugger* en menuconfig y pon `IP:8000` de tu
   computadora.
2. Ejecuta `python scripts/audio_debug_server.py` en la computadora (16 kHz y
   2 canales por defecto).
3. Haz que Coglet hable y abre el WAV en Audacity: la izquierda es el micrófono
   y la derecha, la referencia.
4. El eco en el micrófono debe llegar un poco **después** de la referencia
   (0–3 ms).
   - Eco **antes** de la referencia: pon el desfase de la referencia en negativo
     (−1, −2, …).
   - Eco más de 10 ms tarde: las marcas de tiempo están mal; infórmalo con la
     grabación.

## Límites conocidos

- **El ruido de los servos** no es eco: el ruido de los engranajes mientras se
  mueven la boca, las orejas y el cuello no se puede cancelar y puede
  interrumpir a Coglet.
- **Volumen alto**: la distorsión del pequeño altavoz y de la carcasa no se
  cancela del todo. La AEC funciona mejor con el volumen al 50 % o menos.
- Con AEC, la VAD local del AFE está desactivada (como en las placas ESP-Box
  originales); el servidor decide dónde empieza y termina la voz.

## Archivos

- `main/audio/codecs/software_aec_reference.{h,cc}`: alineación temporal, sin IDF
- `main/audio/codecs/no_audio_codec.{h,cc}`: callbacks de DMA, `EnableSoftwareAecReference()`, salida `MR`
- `main/boards/cognog-v3/cognog_v3_board.cc`: inicia la referencia cuando la AEC está activada
- `main/audio/processors/afe_audio_processor.cc`: alternativa sin canal de referencia
- `main/application.cc`: modo realtime para Auto-Awake con AEC
