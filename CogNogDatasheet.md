# 1. Hardware

## 1.1 Description

A dual-MCU animatronics and AI processing platform combining an ESP32-S3 for machine learning/vision/audio and an RP2040 for real-time kinematics and servo control.

### 1.1.1 Key Features

- **Main Processor:** ESP32-S3 (Wi-Fi/BLE, AI acceleration, I/O)
- **Coprocessor:** RP2040 (Real-time I/O, motion profiling)
- **Motor Control:** PCA9685 16-channel PWM driver
- **Vision:** DVP Camera interface (supports GC0308)
- **Audio:** I2S Microphone input and I2S Speaker amplifier
- **Power:** Single USB-C power input for up to 12 servos

---

## 2. System Block Diagram

<img width="1379" height="869" alt="image" src="https://github.com/user-attachments/assets/f82f1e3e-d22e-44be-9555-b122088dfd8f" />


---

## 3. Pinout

<img width="1513" height="1492" alt="image" src="https://github.com/user-attachments/assets/3583c5b2-1953-4ada-817a-bcface599220" />


---

## 4. Components

### 4.1 On-Board Components

| Name | Function | Interface | Datasheet |
| --- | --- | --- | --- |
| ESP32-S3 | Wi-Fi/BLE, AI acceleration, I/O | - | https://documentation.espressif.com/esp32-s3_datasheet_en.pdf |
| RP2040 | Real-time I/O, motion profiling | - | https://pip-assets.raspberrypi.com/categories/814-rp2040/documents/RP-008371-DS-1-rp2040-datasheet.pdf |
| MAX98357A | Speaker amplifier | I2S | https://cdn-shop.adafruit.com/product-files/3006/MAX98357A-MAX98357B.pdf |
| PCA9685 | Servo driver | I2C | https://www.futurlec.com/Philips/PCA9685PW.shtml |
| CH343P | USB bus converter chip | UART | https://cdn-learn.adafruit.com/assets/assets/000/134/549/original/CH343DS1.PDF?1737477957 |

### 4.2 Recommended External Components

| Name | Function | Interface | Datasheet | Link | Notes |
| --- | --- | --- | --- | --- | --- |
| GC0308 Camera | In-depth vision processing | DVP | https://download.kamami.pl/p1197045-GC0308.pdf | - | **Coglet uses a customised camera with inverted pin layout!** |
| Grove Vision AI Module | Processes face tracking  | UART | https://wiki.seeedstudio.com/Grove-Vision-AI-Module/ | https://nmrobots.com/products/grove-vision-ai-module-v2-hd-camera-adaptor-15-pin-flex-cable |  |
| OV5647 Camera | Realtime face tracking | DVP | - | https://nmrobots.com/products/grove-vision-ai-module-v2-hd-camera-adaptor-15-pin-flex-cable |  |
| Speaker | Speaking responses out loud | Direct Voltage | - | - |  |
| Microphone | Recording audio, listening for responses | I2S | - | - |  |
| Servos | Driving the robot | PWM | - | https://nmrobots.com/products/tiankongrc-ts90md-micro-servo-motor-with-metal-gears |  |

## 5. Power Ratings

*Stresses beyond these limits may cause permanent damage to the board.* 

| Parameter | Symbol | Typical Voltage $V$ | Typical Current $A$ |
| --- | --- | --- | --- |
| **Main Input** | **$V_{IN}$** | **5.0** | **3.0** |
| ESP32 Logic Input  | $V_{LOGIC\_ESP}$ | 3.3 | 0.04 |
| RP2040Logic Input  | $V_{LOGIC\_RP}$ | 3.3 | 0.012 |
| Servo Output Voltage | $V_{IN\_SERVO}$ | 5.0 | 3.0 |

---

## 6. Dual-MCU Communication Protocol

ESP32-s3 sends commands to the RP2040 via UART in the form of simple strings which correspond to preset animations:

$ESP-RX_{GPIO18} : RP2040-TX1_{GPIO04}$

$ESP-TX_{GPIO17} : RP2040-RX1_{GPIO05}$

---

## 7. Power Architecture

Power is provided to the board via the connector in the bottom left corner using a JST-XH connector. This input powers both MCUs via 3V3 LDOs, and the servos via an isolated 5V line. 

It is recommended to use a 5V, 3A power supply (eg - fast charging mobile phone adaptor). If using the Coglet USB > JST XH adaptor, must use a USBA > USBC cable. 

The system can be powered via the programming port, but no power will be delivered to the servos (this approach can be helpful when debugging/developing on the ESP32)

---

## 8. Mechanical Specifications

- **Dimensions:** 72 mm x 81 mm
- **Mounting Holes:** 4 x 2.75mm (to suit M2.5 screws)
- **PCB Layers:** 4

<img width="2160" height="2160" alt="image" src="https://github.com/user-attachments/assets/e4854942-7df7-45c1-8816-f1c75c151878" />


---

## 9. Downloads

*Refer to GitHub root for open-source files such as schematic, layout, STEP, etc*

---

# 2. Software & Firmware

### 2.1 Overview

- Toolchain: ESP-IDF, C++, Python
- Key Libraries: XiaoZhi AI Open-Source Chatbot: https://github.com/78/xiaozhi-esp32

*FAQ: Is it essential to use XiaoZhi AI?  The system is a helpful starting point to get up and running quickly, but for developers it is not necessary. NMRobotics is also developing a locally-running alternative dashboard.* 

## 2.2 Guides

*This section is a stub ! Most recent tutorial overview can be found here:*

https://youtu.be/-7I-jFSNP2E?si=6lqtyZIJ3J-2O9Dj

### 2.2.1 Manually Uploading Code

1. It is recommended to follow this guide to setup ESP-IDF: https://github.com/will-cogley/Coglet/blob/main/Translated Docs for XiaoZhi AI/Setting up the ESP IDF 5.5.2 Development Environment on Windows and Compiling Xiaozhi - Feishu Docs.pdf
2. Clone the github repository 
3. Using ESP-IDF, build and flash 

### 2.2.2 Adding a customised wakeword

1. coming soon

---

# 3. Troubleshooting

| Issue | Recommended action |
| --- | --- |
| Images taken with camera are over/under exposed | Search in "main\boards\common\ esp32_camera. cc " for:
{0xd3, 0xb0}

Then change it to:
{0xd3, 0x70},
If you think the light is too dim, change "0x70" to "0x78".

Re-build and flash the code via ESP-IDF |
| No power to main board when using USBC > JST XH adaptor board | Use a power adaptor featuring a USBA > USBC cable |

---

# 4. Revision History

| Revision | Date | Description | Author |
| --- | --- | --- | --- |
| V1.0 | 2025-12-02 | Initial prototype  | Will Cogley |
| V1.1 | 2026-01-07 | Minor tweaks  | Will Cogley |
| V2.0 | 2026-06-01 | First Production Prototype | Spike |
| V2.1 | 2026-07-02 | Alternative Production Prototype | Petr Dvorak |
| V2.2 | 2026-08-01 | Minor tweaks from Petr’s design | Xiao Zou |
| V3.0 | 2026-09-06 | Finalised production design for batch 01 | Xiao Zou, Will Cogley |
