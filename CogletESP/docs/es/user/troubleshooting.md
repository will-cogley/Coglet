# Solución de problemas

[Documentación](../README.md) · [English](../../en/user/troubleshooting.md) · [Deutsch](../../de/user/troubleshooting.md) · **Español** · [日本語](../../ja/user/troubleshooting.md)

## Pedir ayuda

En la página [Coglet Updater](https://will-cogley.github.io/Coglet/), haz clic en
**Mostrar registro del dispositivo**, haz que ocurra el problema, luego haz clic
en **Copiar registro** y publícalo en la comunidad. El registro está en inglés a
propósito, para que todos puedan leerlo.

## Actualizar

**Coglet no aparece en la lista de puertos.**
Prueba otro cable USB (muchos solo cargan) y otro puerto USB sin hub. Usa el
puerto USB-C superior de Coglet con el interruptor de modo en **ESP**. En
Windows, el controlador se instala solo la primera vez; dale un minuto. Si aun
así no aparece, marca **Opciones avanzadas → Mostrar todos los puertos**.

**Hay varios puertos en la lista. ¿Cuál es Coglet?**
Desconecta Coglet y vuelve a conectar: la entrada que desapareció es Coglet.
Suele llamarse «USB Serial», «CH340/CH343», «CP210x» o «USB JTAG/serial».

**«Failed to connect» (no se pudo conectar).**
Cierra todo lo demás que use el puerto (Thonny, el IDE de Arduino, otra
pestaña con la página). Si sigue fallando: mantén pulsado **BOOT**, pulsa y
suelta **RESET**, suelta **BOOT** y haz clic en **Conectar y actualizar**. Una
velocidad más baja en **Opciones avanzadas** también puede ayudar.

**La actualización se detuvo a la mitad, o desconecté Coglet.**
Nada se rompe para siempre: vuelve a conectarlo y actualiza otra vez. Si se
estaba actualizando la placa de servos, Coglet lo termina o lo repite por sí
solo en el siguiente arranque.

**La página dice «Un paso más».**
Tu placa de servos necesita la configuración única: consulta
[Primeros pasos](getting-started.md#un-paso-extra-en-los-coglet-antiguos).

**La configuración de la placa de servos no logra conectarse.**
Comprueba que el interruptor de modo esté en **RP2040** y que ningún otro
programa tenga el puerto abierto. Si la placa nunca tuvo MicroPython instalado,
pide el firmware inicial en la comunidad.

**¿Tengo que abrir Coglet para llegar al interruptor de modo?**
Solo para la configuración única de la placa de servos, y solo en los Coglet
fabricados antes de noviembre de 2026. Si prefieres no abrirlo, puedes
actualizar igual: todo funciona excepto los movimientos nuevos de los servos.

**Compilo mi propio firmware. ¿La página lo sobrescribe?**
Sí, **Conectar y actualizar** instala el firmware oficial. Las canciones
añadidas en la página se conservan; las compiladas en tu propio firmware, no.

## Hablar

**Coglet no se despierta, o se despierta solo.**
En los ajustes, baja el umbral de activación (por ejemplo a 3) si no te oye, o
súbelo (por ejemplo a 10) si se despierta solo. Habla a una distancia normal,
de cara a Coglet. También puedes elegir otra palabra de activación.

**Coglet dice un código de 6 dígitos.**
Hay que vincularlo de nuevo con xiaozhi.me (pasa después de una Instalación
limpia): consulta [Primeros pasos](getting-started.md#3-vincula-coglet-con-xiaozhime).

**Coglet no se conecta a mi Wi-Fi.**
Solo funcionan las redes de 2,4 GHz. Con un punto de acceso de iPhone, activa
**Maximizar compatibilidad**. Para introducir la red de nuevo, pulsa
**ESP BOOT** mientras Coglet arranca.

## Movimiento

**Coglet se reinicia o los LED se atenúan cuando empieza a moverse.**
La fuente o el cable no dan suficiente corriente. Usa un cargador sencillo de
**5 V / 3 A** y un cable corto y grueso. Los cargadores rápidos de varios
puertos suelen fallar aquí.

**Un servo no se mueve.**
Comprueba en qué conector está enchufado: los números están impresos en la
placa (consulta [Hardware](../developer/hardware.md#conectores-de-servos)).
Comprueba cada servo con el interruptor de calibración y el botón de prueba de
servos.

**Los ojos no me siguen.**
Comprueba que el interruptor de **seguimiento de caras** esté activado. El
seguimiento de caras solo funciona mientras Coglet está despierto; en espera,
el párpado está cerrado.
