# Alimentación

[Documentación](../README.md) · [English](../../en/developer/power.md) · [Deutsch](../../de/developer/power.md) · **Español** · [日本語](../../ja/developer/power.md)

## Fuente

La CogNog V3.0 está pensada para una fuente sencilla de **5 V / 3 A** en la
entrada JST-XH. Los cargadores rápidos de varios puertos pueden no dar 3 A a
5 V y pueden cortar la corriente un momento cuando reparten la potencia entre
dispositivos. Los cables USB finos también pierden mucha tensión con carga. Si
solo se alimenta por el puerto USB de programación, los servos no reciben
corriente.

## Encendido escalonado de los servos

Encender los nueve servos a la vez hace que todos salten a su destino en el
mismo instante. Con una fuente débil, el pico de corriente puede bajar la línea
de 5 V lo suficiente como para reiniciar la placa, lo que parece un bucle de
arranque con los LED atenuándose.

Cada vez que se (re)activa la salida PWM (`RP2040/app.py`), se apaga del todo
cada canal del PCA9685, se habilita nOE y los servos se encienden de uno en
uno, primero los ejes pesados:

```
YAW → PIT → ROL → LID → MOU → EAL → EAR → EYL → EYR
```

| Cuándo | Intervalo | Total |
|---|---|---|
| Arranque | `POWER_UP_GAP_BOOT_MS` = 150 ms | ~1,2 s |
| Entrar en el modo de calibración desde la espera | 150 ms | ~1,2 s |
| Despertar de la espera (estado, acción MCP, baile) | `POWER_UP_GAP_WAKE_MS` = 60 ms | ~0,5 s |

La secuencia no bloquea el bucle principal. Si se libera el par antes de que
termine, se cancela. Una canción propia tranquila deja apagados LID, EYL y EYR.

Mientras un servo está apagado, su posición en el programa queda congelada.
Al encenderse de nuevo, parte de donde se detuvo físicamente y va a su nuevo
destino a su velocidad normal, en lugar de saltar hasta allí. Antes de un
baile los servos ni siquiera se apagan (`prep:`, consulta
[Arquitectura](architecture.md#protocolo-uart-esp--rp2040)).

Registro: `[POWER] staggered power-up (...)`, `[POWER] all servos on after ... ms`.

## Espera

Cuando la pose de idle se ha asentado, el RP2040 espera 500 ms y pone nOE a
nivel alto: se libera todo el par de los servos (la línea de 5 V sigue
encendida).

La inferencia del Grove Vision AI se pausa (`AT+BREAK`) mientras Coglet está
inactivo, en el modo de calibración y durante los bailes, y se reanuda al
despertar. Con el interruptor de seguimiento de caras desactivado, nunca
empieza. El módulo sigue alimentado; la placa no tiene un interruptor para él.

## Motivo del reinicio

- ESP32-S3: la primera línea del registro es `main: Reset reason: ...`; un
  brown-out se registra como error: `Reset reason: BROWN-OUT (supply voltage dropped)`.
- RP2040: `[BOOT] RP2040 reset cause: ...`. El RP2040 informa un brown-out como
  un reinicio por encendido; usa la línea del ESP para distinguirlos.
