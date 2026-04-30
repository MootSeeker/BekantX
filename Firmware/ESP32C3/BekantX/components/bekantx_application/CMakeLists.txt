idf_component_register(SRCS
                       "src/Application.cpp"
                       "src/StatusIndicator.cpp"
                       "src/wifi/WifiCredentialStore.cpp"
                       "src/wifi/WifiManager.cpp"
                       INCLUDE_DIRS "include"
                       REQUIRES bekantx_drivers bekantx_libs bekantx_mqtt
                                esp_common esp_timer log
                                nvs_flash esp_wifi esp_netif esp_event
                                esp_http_server lwip)
