#include "application/Application.hpp"

extern "C" {
#include "core/core_runtime.h"
#include "drivers/driver_registry.h"
#include "libs/library_registry.h"
}

#include "esp_log.h"

namespace {
constexpr const char *TAG = "bkx_app";
}

namespace application {

void BekantXApplication::Run()
{
    ESP_LOGI(TAG, "Starting BekantX application layer");

    LibraryInit();
    DriverInit();
    CoreStart();
}

}  // namespace application
