# Usar Coglet

[Documentación](../README.md) · [English](../../en/user/using-coglet.md) · [Deutsch](../../de/user/using-coglet.md) · **Español** · [日本語](../../ja/user/using-coglet.md)

## Hablar

Di **«Hello Coglet»** (o pulsa el botón ESP BOOT) y habla. El LED rojo se
enciende mientras Coglet escucha. Coglet mueve la cabeza, las orejas, los ojos
y la boca según lo que dice y cómo se siente, y cierra los ojos y se relaja
cuando vuelve al modo de espera.

Unos segundos después de arrancar, Coglet empieza a escuchar por sí solo una
vez, para que puedas hablarle enseguida.

Por defecto, Coglet deja de escuchar mientras habla. Para interrumpirlo a mitad
de una frase, activa **Interrumpir a Coglet** en los
[ajustes](settings-and-songs.md).

## Movimientos a petición

Pídelo con tus propias palabras, por ejemplo:

| Di | Coglet |
|---|---|
| «Niega con la cabeza» | niega con la cabeza tres veces |
| «Parpadea» | parpadea tres veces |
| «Mueve la oreja izquierda» / «la oreja derecha» | mueve esa oreja |
| «Mueve las orejas» | mueve las dos orejas |
| «Toma una foto» / «¿Qué ves?» | mira con su cámara |

## Bailar

Di **«Baila para mí»**. Coglet responde con una frase corta, termina la
conversación, pone una canción de unos 30 segundos y la baila, y luego te
pregunta qué te ha parecido.

Cada edición tiene tres bailes incluidos; pide uno por su nombre o deja que
Coglet elija:

| Edición | Bailes |
|---|---|
| Estándar | **mecha** (electro contundente), **evil** (gótico sombrío), **cat** (pop gatuno suave) |
| Navidad | **lyrical** (Noche de paz), **classic** (Jingle Bells), **grand** (Al mundo paz) |
| Duende | **workshop** (Deck the Halls), **mischief** (God Rest Ye Merry Gentlemen), **party** (We Wish You a Merry Christmas) |
| Muñeco de nieve | **lullaby** (Canción de cuna de Brahms), **stomp** (Good King Wenceslas), **blizzard** (Carol of the Bells) |

También puedes añadir tus propias canciones y decir «baila una de mis
canciones» o «baila *nombre de la canción*»: consulta
[Ajustes y canciones](settings-and-songs.md).

Decir «Hello Coglet» o pulsar el botón durante un baile lo detiene.

## Recordatorios

Pide, por ejemplo, «Recuérdame en 20 minutos sacar el pan» o «Recuérdame
mañana a las 8 llamar a Ana». A la hora indicada, Coglet toca un sonido y dice
el recordatorio, aunque no haya ninguna conversación abierta. También puedes
preguntar «¿Qué recordatorios tengo?» o «Cancela el recordatorio del pan».

- Hasta 12 recordatorios, cada uno de una sola vez (sin repeticiones).
- Los recordatorios se guardan en Coglet y se conservan tras reinicios y
  actualizaciones.
- Las horas siguen la zona horaria que xiaozhi.me indica para tu Coglet.

## Interruptores y botones

| Control | Qué hace |
|---|---|
| **Interruptor de modo** ESP / RP2040 (pequeño, blanco, junto al puerto USB-C de programación) | Con qué chip se comunica el puerto USB. Déjalo en **ESP** (derecha). |
| Interruptor de **calibración** | Lleva cada servo a su posición de calibración, para el montaje. |
| Botón de **prueba de servos** | Solo en el modo de calibración: mantenlo pulsado para mover cada servo ±10° alrededor de su posición de calibración. |
| Interruptor de **seguimiento de caras** (FACE-TRACK) | Activa o desactiva el seguimiento de caras (cámara Grove Vision AI en el ojo). Desactivarlo no detiene los demás movimientos. |
| Botón **ESP BOOT** | Empieza o termina una conversación. |
| Botones **RST** | Reinician el ESP32-S3 o el RP2040. |

## Alimentación y espera

En espera, Coglet cierra los ojos y apaga sus servos, para que estén en
silencio y no se calienten. Al despertar, los servos se encienden uno tras otro
para evitar un pico de corriente.

Usa una fuente de **5 V / 3 A**. Si Coglet se reinicia cuando empieza a
moverse, la fuente o el cable no dan suficiente corriente.
