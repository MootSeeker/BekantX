#include "drivers/ws2812_transport.h"

#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "driver/rmt_tx.h"
#include "driver/rmt_encoder.h"
#include "esp_log.h"

static const char *TAG = "bkx_ws2812";

#define WS2812_RMT_DEFAULT_RESOLUTION_HZ 10000000  /* 10 MHz → 100 ns/tick */

/* WS2812 timing at 10 MHz:
 *   T0H = 3 ticks (300 ns), T0L = 9 ticks (900 ns)
 *   T1H = 9 ticks (900 ns), T1L = 3 ticks (300 ns)
 */
#define WS2812_T0H_TICKS 3
#define WS2812_T0L_TICKS 9
#define WS2812_T1H_TICKS 9
#define WS2812_T1L_TICKS 3

#define WS2812_TX_TIMEOUT_MS 200

struct ws2812_transport {
    rmt_channel_handle_t tx_channel;
    rmt_encoder_handle_t encoder;
    uint16_t             num_leds;
};

esp_err_t Ws2812TransportInit(const LedTransportConfig *config,
                              ws2812_transport_handle_t *out_handle)
{
    if (!config || !out_handle) {
        return ESP_ERR_INVALID_ARG;
    }
    if (config->num_leds == 0 || config->num_leds > 256) {
        ESP_LOGE(TAG, "num_leds must be 1..256, got %u", config->num_leds);
        return ESP_ERR_INVALID_ARG;
    }

    struct ws2812_transport *handle = calloc(1, sizeof(*handle));
    if (!handle) {
        return ESP_ERR_NO_MEM;
    }
    handle->num_leds = config->num_leds;

    uint32_t resolution = config->rmt_resolution_hz;
    if (resolution == 0) {
        resolution = WS2812_RMT_DEFAULT_RESOLUTION_HZ;
    }

    rmt_tx_channel_config_t tx_cfg = {
        .gpio_num           = config->gpio_num,
        .clk_src            = RMT_CLK_SRC_DEFAULT,
        .resolution_hz      = resolution,
        .mem_block_symbols  = 64,
        .trans_queue_depth  = 4,
        .flags = {
            .invert_out = 0,
            .with_dma   = 0,
        },
    };

    esp_err_t ret = rmt_new_tx_channel(&tx_cfg, &handle->tx_channel);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create RMT TX channel: %s", esp_err_to_name(ret));
        free(handle);
        return ret;
    }

    rmt_bytes_encoder_config_t enc_cfg = {
        .bit0 = {
            .duration0 = WS2812_T0H_TICKS,
            .level0    = 1,
            .duration1 = WS2812_T0L_TICKS,
            .level1    = 0,
        },
        .bit1 = {
            .duration0 = WS2812_T1H_TICKS,
            .level0    = 1,
            .duration1 = WS2812_T1L_TICKS,
            .level1    = 0,
        },
        .flags.msb_first = true,
    };

    ret = rmt_new_bytes_encoder(&enc_cfg, &handle->encoder);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create bytes encoder: %s", esp_err_to_name(ret));
        rmt_del_channel(handle->tx_channel);
        free(handle);
        return ret;
    }

    ret = rmt_enable(handle->tx_channel);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to enable RMT channel: %s", esp_err_to_name(ret));
        handle->encoder->del(handle->encoder);
        rmt_del_channel(handle->tx_channel);
        free(handle);
        return ret;
    }

    ESP_LOGI(TAG, "WS2812 transport ready on GPIO%d for %u LED(s)", config->gpio_num, config->num_leds);
    *out_handle = handle;
    return ESP_OK;
}

esp_err_t Ws2812TransportDeinit(ws2812_transport_handle_t handle)
{
    if (!handle) {
        return ESP_ERR_INVALID_ARG;
    }

    rmt_disable(handle->tx_channel);
    handle->encoder->del(handle->encoder);
    rmt_del_channel(handle->tx_channel);
    free(handle);
    return ESP_OK;
}

esp_err_t Ws2812TransportSend(ws2812_transport_handle_t handle,
                              const uint8_t *grb_data,
                              uint16_t num_leds)
{
    if (!handle || !grb_data) {
        return ESP_ERR_INVALID_ARG;
    }

    rmt_transmit_config_t tx_config = {
        .loop_count = 0,
    };

    esp_err_t ret = rmt_transmit(handle->tx_channel, handle->encoder,
                                 grb_data, (size_t)num_leds * 3, &tx_config);
    if (ret != ESP_OK) {
        return ret;
    }

    return rmt_tx_wait_all_done(handle->tx_channel, pdMS_TO_TICKS(WS2812_TX_TIMEOUT_MS));
}
