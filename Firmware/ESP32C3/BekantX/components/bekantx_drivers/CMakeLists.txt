idf_component_register(SRCS "src/driver_registry.c"
                            "src/ws2812_transport.c"
                            "src/LedDriver.cpp"
                            "src/LedAnimator.cpp"
                       INCLUDE_DIRS "include"
                       REQUIRES esp_common esp_driver_rmt freertos log)
