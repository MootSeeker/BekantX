idf_component_register(SRCS
                       "src/Application.cpp"
                       "src/StatusIndicator.cpp"
                       INCLUDE_DIRS "include"
                       REQUIRES bekantx_drivers bekantx_libs esp_common esp_timer log)
