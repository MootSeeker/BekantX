#pragma once

#include "esp_err.h"
#include "esp_http_server.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Start the captive-portal HTTP server.
 *
 * Registers handlers for:
 *   GET  /            — provisioning page
 *   GET  /scan        — JSON list of visible APs
 *   POST /save        — receive credentials, post WIFI_MGR_EVT_SAVE_CREDS to @p event_queue
 *   GET  /generate_204, /hotspot-detect.html, /connecttest.txt, /ncsi.txt
 *                     — captive-portal detection probes (Android / iOS / Windows)
 *
 * @param[out] out_handle  Populated with the httpd handle on success.
 * @param[in]  event_queue FreeRTOS queue used to send SAVE_CREDS events to WifiManager.
 * @return ESP_OK on success.
 */
esp_err_t portal_http_start(httpd_handle_t *out_handle, QueueHandle_t event_queue);

/**
 * @brief Stop the captive-portal HTTP server.
 * @param handle  Handle returned by portal_http_start().
 * @return ESP_OK on success.
 */
esp_err_t portal_http_stop(httpd_handle_t handle);

#ifdef __cplusplus
}
#endif
