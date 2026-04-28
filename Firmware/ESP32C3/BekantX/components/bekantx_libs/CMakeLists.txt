idf_component_register(SRCS "src/library_registry.c"
                            "src/provisioning/captive_portal_http.c"
                            "src/provisioning/dns_hijack.c"
                       INCLUDE_DIRS "include"
                       EMBED_TXTFILES "assets/portal.html"
                       REQUIRES esp_common log esp_wifi esp_http_server lwip nvs_flash)
