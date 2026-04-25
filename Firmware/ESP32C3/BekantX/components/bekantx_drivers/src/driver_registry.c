#include "drivers/driver_registry.h"

#include "esp_log.h"

static const char *TAG = "bkx_driver";

void DriverInit(void)
{
    ESP_LOGI(TAG, "Driver layer ready for hardware modules");
}
