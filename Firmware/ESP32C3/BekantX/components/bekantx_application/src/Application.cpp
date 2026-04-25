#include "application/Application.hpp"
#include "application/StatusIndicator.hpp"
#include "drivers/LedDriver.hpp"
#include "drivers/LedAnimator.hpp"

extern "C" {
#include "core/core_runtime.h"
#include "drivers/driver_registry.h"
#include "libs/library_registry.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
}

#include "esp_log.h"

namespace {
constexpr const char *TAG = "bkx_app";

constexpr int      LED_GPIO            = 18;
constexpr uint16_t LED_COUNT           = 1;
constexpr uint32_t LED_RMT_RESOLUTION  = 10000000;  /* 10 MHz */
constexpr uint32_t LED_TICK_INTERVAL   = 16;         /* ~60 Hz */
}

namespace application {

void BekantXApplication::Run()
{
    ESP_LOGI(TAG, "Starting BekantX application layer");

    LibraryInit();
    DriverInit();

    /* Initialize LED subsystem */
    static drivers::LedDriver led;
    LedTransportConfig led_cfg = {
        .gpio_num         = LED_GPIO,
        .num_leds         = LED_COUNT,
        .rmt_resolution_hz = LED_RMT_RESOLUTION,
    };
    esp_err_t ret = led.Init(led_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "LED driver init failed: %s", esp_err_to_name(ret));
    }

    static drivers::LedAnimator animator(led);
    static StatusIndicator status(led, animator);

    status.SetStatus(DeviceStatus::kBooting);

    CoreStart();

    /* LED animation loop — runs in the main task context */
    while (true) {
        uint32_t now = static_cast<uint32_t>(esp_timer_get_time() / 1000);
        status.Tick(now);
        vTaskDelay(pdMS_TO_TICKS(LED_TICK_INTERVAL));
    }
}

}  // namespace application
