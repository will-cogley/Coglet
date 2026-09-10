#include "uart_component.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

void uart_init_component() {
    uart_config_t uart_config = {
        .baud_rate = 115200,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
    };
    uart_param_config(UART_PORT_NUM, &uart_config);
    uart_set_pin(UART_PORT_NUM, TXD_PIN, RXD_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    uart_driver_install(UART_PORT_NUM, BUF_SIZE, 0, 0, NULL, 0);
}

void uart_send_string(const char* str) {
    uart_write_bytes(UART_PORT_NUM, str, strlen(str));
    uart_write_bytes(UART_PORT_NUM, "\r\n", 2);}

void uart_signal_start() {
    uart_send_string("[SPEAK_START]\n");
}

void uart_signal_stop() {
    uart_send_string("[SPEAK_STOP]\n");
}
