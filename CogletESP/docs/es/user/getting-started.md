# Primeros pasos

[Documentación](../README.md) · [English](../../en/user/getting-started.md) · [Deutsch](../../de/user/getting-started.md) · **Español** · [日本語](../../ja/user/getting-started.md)

Esta página lleva un Coglet ya montado desde la caja hasta su primera
conversación. Para el montaje, mira el [video de montaje](https://youtu.be/EdgYNhH70Qo)
y la [base de conocimiento de NMRobots](https://nmrobots.com/pages/coglet).

## Qué necesitas

- Una computadora con **Chrome o Edge** (Windows, macOS o Linux). Otros
  navegadores no pueden comunicarse con dispositivos USB.
- Un **cable USB-C de datos** (muchos cables solo cargan).
- Una **fuente de 5 V / 3 A** para los servos. Los cargadores rápidos de varios
  puertos a menudo no dan 3 A a 5 V; un cargador sencillo de 5 V / 3 A funciona
  mejor.
- Una red Wi-Fi de **2,4 GHz** (las redes de 5 GHz no son compatibles).

## 1. Actualiza Coglet con el Coglet Updater

1. Abre <https://will-cogley.github.io/Coglet/>.
2. Conecta Coglet por el **puerto USB-C superior (de programación)**. Deja el
   pequeño **interruptor de modo** blanco en **ESP** (deslizado a la derecha),
   como viene de fábrica.
3. Elige una edición (Estándar, Navidad, Duende o Muñeco de nieve; solo cambian
   los bailes y sonidos incluidos) y haz clic en **Conectar y actualizar**.
4. Elige Coglet en la lista de puertos y espera hasta que diga **Listo**.

Se conservan tu Wi-Fi, la vinculación, los recordatorios, los ajustes y las
canciones. Solo **Opciones avanzadas → Instalación limpia** lo borra todo.

**Comprobar mi Coglet** te dice si vale la pena actualizar, sin cambiar nada.

### Un paso extra en los Coglet antiguos

Si la página dice **«Un paso más»**, tu placa de servos (RP2040) necesita una
configuración única. Solo afecta a los Coglet fabricados antes de noviembre de
2026:

1. Desconecta Coglet, desliza el interruptor de modo a la izquierda (**RP2040**)
   y vuelve a conectarlo.
2. Haz clic en **Configurar placa de servos** y elige el RP2040 en la lista (a
   menudo «Board CDC» o «USB Serial Device»).
3. Cuando diga **Listo**, desconecta Coglet, desliza el interruptor de vuelta a
   la derecha (**ESP**), conéctalo y haz clic en **Comprobar Coglet**.

A partir de entonces, Coglet mantiene su placa de servos al día por sí solo
después de cada actualización.

## 2. Conecta Coglet al Wi-Fi

En el primer arranque (o cuando no encuentra su red), Coglet abre su propio
punto de acceso Wi-Fi:

1. Desde tu teléfono o computadora, conéctate a la red **Xiaozhi-XXXX**.
2. Se abre una página de configuración. Si no se abre, ve a <http://192.168.4.1>.
3. Elige tu red de 2,4 GHz, escribe la contraseña y pulsa **Connect**. Con un
   punto de acceso de iPhone, activa **Maximizar compatibilidad**.
4. Coglet se reinicia y se conecta a tu red.

Para cambiar Coglet a otra red: pulsa el botón **ESP BOOT** mientras Coglet
arranca y aún no está conectado; olvida la red anterior y vuelve a abrir el
punto de acceso.

## 3. Vincula Coglet con xiaozhi.me

Coglet habla a través del servicio xiaozhi.me. La primera vez que se conecta,
dice un **código de 6 dígitos**:

1. Inicia sesión en <https://xiaozhi.me> y abre la consola.
2. Añade un dispositivo e introduce el código.
3. Coglet está listo. Di **«Hello Coglet»**.

Ahí también puedes elegir la voz, el idioma y la personalidad.

La vinculación se conserva en las actualizaciones normales. Después de una
**Instalación limpia**, Coglet dice un código nuevo y hay que vincularlo de nuevo.

> Hay un backend sin conexión que funciona en tu propia computadora, en fase
> temprana de desarrollo: [NMWorkbench](https://github.com/will-cogley/NMWorkbench).

## Siguiente

- [Usar Coglet](using-coglet.md)
- [Ajustes y canciones](settings-and-songs.md)
- [Solución de problemas](troubleshooting.md)
