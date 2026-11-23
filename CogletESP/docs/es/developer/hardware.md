# Hardware: CogNog V3.0

[Documentación](../README.md) · [English](../../en/developer/hardware.md) · [Deutsch](../../de/developer/hardware.md) · **Español** · [日本語](../../ja/developer/hardware.md)

Archivos de diseño: `PCB/SCH_CogletESPV3.0_2026-09-10.pdf` (esquema) y
`PCB/CogletESPV3.0_0906_2026-09-10.epro2` (EasyEDA Pro). Cada pin de abajo se
comprobó con la lista de conexiones de la V3.0. Más en la
[hoja de datos de CogNog](../../../../CogNogDatasheet.md).

## Resumen

| Componente | Función |
|---|---|
| ESP32-S3-WROOM-1-N16R8 (U1) | Wi-Fi, voz, palabra de activación, cámara, herramientas MCP. 16 MB de flash, 8 MB de PSRAM |
| RP2040 (U7) | Servos y seguimiento de caras, MicroPython |
| PCA9685 (U9) | Controlador PWM de servos de 16 canales, dirección I²C 0x40 |
| MAX98357A (U16) | Amplificador de altavoz I2S |
| CH343P (U14) | USB serie para programar; el interruptor de modo elige ESP o RP2040 |
| Cámara GC0308 (FPC1) | Fotos para la IA («¿qué ves?») |
| Grove Vision AI V2 | Seguimiento de caras, cámara en el ojo |
| Micrófono MEMS I2S | Entrada de voz |

Alimentación: **5 V / 3 A** en la entrada JST-XH; unos LDO generan 3,3 V para
ambos MCU, y los servos van con la línea de 5 V. Si solo se alimenta por el
puerto USB de programación, la lógica funciona pero los servos no reciben
corriente.

## ESP32-S3

| GPIO | Red | Uso |
|---|---|---|
| 0 | ESP_GPIO0 | Botón BOOT |
| 3 | ESP_GPIO3 | LED rojo de «escuchando» (puerta de Q4, activo en alto, pull-down de 100 kΩ) |
| 4 | MICWS | WS del micrófono |
| 5 | MICSCK | SCK del micrófono |
| 6 | MICSD | Datos del micrófono |
| 7 | MAXDIN | Datos del amplificador |
| 15 | MAXBCLK | BCLK del amplificador |
| 16 | MAXLRCLK | LRCLK del amplificador |
| 17 | ESP_GPIO17 | UART1 TX → GPIO5 del RP2040 |
| 18 | ESP_GPIO18 | UART1 RX ← GPIO4 del RP2040 |
| 19, 20 | USB D−/D+ | USB nativo |
| 43, 44 | ESP_TX / ESP_RX | UART0, programación y registro (CH343P) |
| 1, 2, 45, 46 | ESP_GPIO1, EIO2, EIO45, EIO46 | Libres |

Cámara (GC0308, DVP de 8 bits; CAMD2…CAMD9 son Y2…Y9 del sensor):

| Señal | GPIO | Señal | GPIO |
|---|---|---|---|
| D0 (CAMD2) | 41 | XCLK | 14 |
| D1 (CAMD3) | 47 | PCLK | 9 |
| D2 (CAMD4) | 48 | VSYNC | 8 |
| D3 (CAMD5) | 38 | HREF | 40 |
| D4 (CAMD6) | 42 | SIOC (SCCB SCL) | 10 |
| D5 (CAMD7) | 21 | SIOD (SCCB SDA) | 12 |
| D6 (CAMD8) | 11 | RESET | 39 |
| D7 (CAMD9) | 13 | PWDN | — (a GND mediante R30) |

Coglet usa un módulo GC0308 personalizado con la distribución de pines invertida.

En el código: [`main/boards/cognog-v3/config.h`](../../../main/boards/cognog-v3/config.h)
y [`main/uart_component.h`](../../../main/uart_component.h).

## RP2040

| GPIO | Uso |
|---|---|
| 0, 1 | UART0 TX / RX al Grove Vision AI V2, 921600 baudios |
| 4, 5 | UART1 TX / RX al ESP32-S3, 115200 baudios |
| 6, 7 | I²C SDA / SCL al PCA9685 |
| 8 | nOE del PCA9685 (alto = todas las salidas de servos apagadas) |
| 12 | Botón de prueba de servos (activo en bajo) |
| 20 | Interruptor de calibración (activo en bajo) |
| 21 | Interruptor de seguimiento de caras (activo en bajo) |
| 25 | LED frontal (serigrafía «RP25») |

En el código: `RP2040/app.py`, `RP2040/servoclass.py`, `RP2040/vision.py`.

## Conectores de servos

El número impreso junto a cada conector es su canal del PCA9685.

| Conector | Servo | Clave en el código | Rango (°) |
|---|---|---|---|
| 0 | Oreja derecha | `EAR` | 30–120 |
| 1 | Oreja izquierda | `EAL` | 60–150 |
| 2 | Párpado | `LID` | 30–160 |
| 3 | Boca | `MOU` | 5–150 |
| 4 | Ojo izquierdo | `EYL` | 50–140 |
| 5 | Ojo derecho | `EYR` | 50–140 |
| 8 | Cuello, cabeceo | `PIT` | 1–80 |
| 9 | Cuello, alabeo | `ROL` | 30–120 |
| 10 | Base, giro | `YAW` | 30–150 |
| 6, 7, 11 | Libres | | |

Los límites, velocidades y aceleraciones están en `RP2040/animation.py`
(`servos`), y la pose de calibración en `pose_calibrate`.
