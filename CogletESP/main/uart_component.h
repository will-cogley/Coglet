#pragma once
#include "driver/uart.h"

#define TXD_PIN 17
#define RXD_PIN 18
#define UART_PORT_NUM UART_NUM_1
#define BUF_SIZE 1024

void uart_init_component();
void uart_send_string(const char* str);
void uart_signal_start();
void uart_signal_stop();
