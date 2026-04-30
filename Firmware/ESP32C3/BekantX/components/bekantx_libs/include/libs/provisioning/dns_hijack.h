#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Start the DNS hijack server.
 *
 * Opens a UDP socket on port 53 and responds to every A-record query with
 * 192.168.4.1.  This redirects all DNS lookups to the captive portal while
 * the device is in provisioning mode.
 *
 * @return ESP_OK on success.
 */
esp_err_t dns_hijack_start(void);

/**
 * @brief Stop the DNS hijack server and free its task.
 */
void dns_hijack_stop(void);

#ifdef __cplusplus
}
#endif
