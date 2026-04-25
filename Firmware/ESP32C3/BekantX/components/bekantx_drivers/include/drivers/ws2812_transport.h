#pragma once

#include "drivers/led_types.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ws2812_transport *ws2812_transport_handle_t;

esp_err_t Ws2812TransportInit(const LedTransportConfig *config,
                              ws2812_transport_handle_t *out_handle);

esp_err_t Ws2812TransportDeinit(ws2812_transport_handle_t handle);

/**
 * @brief Transmit pixel data to the WS2812 LED strip.
 *
 * @param handle     Transport handle obtained from Ws2812TransportInit.
 * @param grb_data   Pixel data in GRB wire order, (num_leds * 3) bytes.
 * @param num_leds   Number of LEDs to transmit.
 * @return ESP_OK on success.
 */
esp_err_t Ws2812TransportSend(ws2812_transport_handle_t handle,
                              const uint8_t *grb_data,
                              uint16_t num_leds);

#ifdef __cplusplus
}
#endif
