#include "libs/library_registry.h"

#include "esp_log.h"

static const char *TAG = "bkx_libs";

void LibraryInit(void)
{
    ESP_LOGI(TAG, "Library layer ready for shared and third-party code");
}
