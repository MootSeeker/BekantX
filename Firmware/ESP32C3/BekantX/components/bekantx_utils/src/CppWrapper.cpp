#include "utils/CppWrapper.h"
#include "application/Application.hpp"

#include "esp_log.h"

namespace {
constexpr const char *TAG = "bkx_cpp";
}

extern "C" void CppWrapperStart(void)
{
    ESP_LOGI(TAG, "Crossing from C entry into C++ application runtime");

    static application::BekantXApplication application;
    application.Run();
}
