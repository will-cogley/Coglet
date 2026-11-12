#include <esp_log.h>
#include <esp_system.h>
#include <esp_err.h>
#include <nvs.h>
#include <nvs_flash.h>
#include <driver/gpio.h>
#include <esp_event.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "application.h"
#include "system_info.h"
#include "uart_component.h"
#include "coglet_rp2040_sync.h"

#define TAG "main"

// Why did the ESP32-S3 (re)start? A brown-out here almost always means the
// 5 V supply or cable sagged (e.g. many servos starting at once).
static void LogResetReason()
{
    const esp_reset_reason_t reason = esp_reset_reason();
    const char* name = "unknown";
    switch (reason) {
    case ESP_RST_POWERON:   name = "power-on"; break;
    case ESP_RST_EXT:       name = "external pin"; break;
    case ESP_RST_SW:        name = "software restart"; break;
    case ESP_RST_PANIC:     name = "crash (panic)"; break;
    case ESP_RST_INT_WDT:   name = "interrupt watchdog"; break;
    case ESP_RST_TASK_WDT:  name = "task watchdog"; break;
    case ESP_RST_WDT:       name = "other watchdog"; break;
    case ESP_RST_DEEPSLEEP: name = "wake from deep sleep"; break;
    case ESP_RST_BROWNOUT:  name = "BROWN-OUT (supply voltage dropped)"; break;
    case ESP_RST_SDIO:      name = "SDIO"; break;
    case ESP_RST_USB:       name = "USB"; break;
    case ESP_RST_JTAG:      name = "JTAG"; break;
    default: break;
    }
    if (reason == ESP_RST_BROWNOUT) {
        ESP_LOGE(TAG, "Reset reason: %s -- check the 5 V / 3 A supply and cable", name);
    } else {
        ESP_LOGI(TAG, "Reset reason: %s (%d)", name, static_cast<int>(reason));
    }
}

extern "C" void app_main(void)
{
    LogResetReason();
    uart_init_component();
    // Initialize the default event loop
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Initialize NVS flash for WiFi configuration
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "Erasing NVS flash to fix corruption");
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Launch the application
    auto& app = Application::GetInstance();
    app.Start();

#if CONFIG_COGLET_RP2040_SYNC
    // Bring the RP2040's program up to date over the UART link.
    CogletRp2040::StartSyncTask();
#endif
}
