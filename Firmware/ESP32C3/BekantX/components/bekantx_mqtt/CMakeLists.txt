idf_component_register(SRCS
                       "src/MqttCredentialStore.cpp"
                       "src/MqttCommandHandler.cpp"
                       "src/MqttStatePublisher.cpp"
                       "src/MqttDiscovery.cpp"
                       "src/MqttService.cpp"
                       INCLUDE_DIRS "include"
                       REQUIRES esp_common log nvs_flash
                                esp_event esp_wifi
                                esp_timer esp_app_format)
