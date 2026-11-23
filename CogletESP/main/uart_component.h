#pragma once
#include "driver/uart.h"

// UART1 link to the RP2040 (CogNog V3.0: ESP GPIO17 TX -> RP2040 GPIO5 RX,
// ESP GPIO18 RX <- RP2040 GPIO4 TX).
#define TXD_PIN 17
#define RXD_PIN 18
#define UART_PORT_NUM UART_NUM_1
#define BUF_SIZE 1024

void uart_init_component();
void uart_send_string(const char* str);
