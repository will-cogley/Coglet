// NMRobotics Coglet - CogNog V3.0 PCB (ESP32-S3 side).
//
// Every pin below was checked against the V3.0 design files in PCB/
// (SCH_CogletESPV3.0_2026-09-10.pdf / CogletESPV3.0_0906 PCB netlist),
// U1 = ESP32-S3-WROOM-1-N16R8. Net names from the schematic are given
// in the comments.
//
// Not defined here because other modules own them:
//   GPIO17 / GPIO18  UART1 link to the RP2040 (main/uart_component.h)
//                    ESP TX GPIO17 -> RP2040 GPIO5, ESP RX GPIO18 <- RP2040 GPIO4
//   GPIO19 / GPIO20  native USB
//   GPIO43 / GPIO44  UART0 (CH343P programming / log port)
// Spare pads on the PCB, unused by the firmware:
//   GPIO1 (ESP_GPIO1), GPIO2 (EIO2), GPIO45 (EIO45), GPIO46 (EIO46)
#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 24000

// Microphone and amplifier use separate I2S ports (simplex).
#define AUDIO_I2S_MIC_GPIO_WS   GPIO_NUM_4   // MICWS
#define AUDIO_I2S_MIC_GPIO_SCK  GPIO_NUM_5   // MICSCK
#define AUDIO_I2S_MIC_GPIO_DIN  GPIO_NUM_6   // MICSD
#define AUDIO_I2S_SPK_GPIO_DOUT GPIO_NUM_7   // MAXDIN    (MAX98357A)
#define AUDIO_I2S_SPK_GPIO_BCLK GPIO_NUM_15  // MAXBCLK
#define AUDIO_I2S_SPK_GPIO_LRCK GPIO_NUM_16  // MAXLRCLK

// Red "listening" LED: GPIO3 -> Q4 (FDC6333C) gate, 100k pull-down (R6).
// Ordinary LED, active HIGH. Not a WS2812.
#define BUILTIN_LED_GPIO        GPIO_NUM_3   // ESP_GPIO3

#define BOOT_BUTTON_GPIO        GPIO_NUM_0   // ESP_GPIO0 (ESP BOOT button)

// GC0308 camera on FPC1. CAMD2..CAMD9 are the sensor's Y2..Y9 bus, so the
// DVP driver's D0..D7 inputs follow the CAMD order.
#define CAMERA_PIN_D0    GPIO_NUM_41  // CAMD2 / Y2
#define CAMERA_PIN_D1    GPIO_NUM_47  // CAMD3 / Y3
#define CAMERA_PIN_D2    GPIO_NUM_48  // CAMD4 / Y4
#define CAMERA_PIN_D3    GPIO_NUM_38  // CAMD5 / Y5
#define CAMERA_PIN_D4    GPIO_NUM_42  // CAMD6 / Y6
#define CAMERA_PIN_D5    GPIO_NUM_21  // CAMD7 / Y7
#define CAMERA_PIN_D6    GPIO_NUM_11  // CAMD8 / Y8
#define CAMERA_PIN_D7    GPIO_NUM_13  // CAMD9 / Y9
#define CAMERA_PIN_XCLK  GPIO_NUM_14  // CAMXCLK
#define CAMERA_PIN_PCLK  GPIO_NUM_9   // CAMPCLK
#define CAMERA_PIN_VSYNC GPIO_NUM_8   // CAMVSYNC
#define CAMERA_PIN_HREF  GPIO_NUM_40  // CAMHREF
#define CAMERA_PIN_SIOC  GPIO_NUM_10  // CAMSIOC (SCCB SCL)
#define CAMERA_PIN_SIOD  GPIO_NUM_12  // CAMSIOD (SCCB SDA)
#define CAMERA_PIN_PWDN  GPIO_NUM_NC  // CAMPWDN: tied to GND through R30, no ESP GPIO
#define CAMERA_PIN_RESET GPIO_NUM_39  // CAMRST
#define XCLK_FREQ_HZ     20000000

#endif // _BOARD_CONFIG_H_
