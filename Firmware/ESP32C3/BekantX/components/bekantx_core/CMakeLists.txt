idf_component_register(SRCS
                       "src/core_runtime.c"
                       "src/legacy_ftm_console.c"
                       INCLUDE_DIRS "include"
                       REQUIRES cmd_system console esp_common esp_event esp_hw_support esp_netif esp_wifi freertos log nvs_flash)
