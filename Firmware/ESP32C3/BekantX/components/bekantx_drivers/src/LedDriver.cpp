#include "drivers/LedDriver.hpp"

#include <cstdlib>
#include <cstring>

extern "C" {
#include "esp_log.h"
}

namespace {
constexpr const char *TAG = "bkx_led_drv";
constexpr uint16_t MAX_LEDS = 256;
}

namespace drivers {

esp_err_t LedDriver::Init(const LedTransportConfig &config)
{
    if (transport_ != nullptr) {
        ESP_LOGE(TAG, "Already initialized");
        return ESP_ERR_INVALID_STATE;
    }
    if (config.num_leds == 0 || config.num_leds > MAX_LEDS) {
        ESP_LOGE(TAG, "num_leds must be 1..%u", MAX_LEDS);
        return ESP_ERR_INVALID_ARG;
    }

    pixels_ = static_cast<RgbColor *>(calloc(config.num_leds, sizeof(RgbColor)));
    grb_buf_ = static_cast<uint8_t *>(calloc(config.num_leds * 3, 1));
    if (!pixels_ || !grb_buf_) {
        free(pixels_);
        free(grb_buf_);
        pixels_ = nullptr;
        grb_buf_ = nullptr;
        return ESP_ERR_NO_MEM;
    }

    esp_err_t ret = Ws2812TransportInit(&config, &transport_);
    if (ret != ESP_OK) {
        free(pixels_);
        free(grb_buf_);
        pixels_ = nullptr;
        grb_buf_ = nullptr;
        return ret;
    }

    num_leds_ = config.num_leds;
    brightness_ = 255;

    ESP_LOGI(TAG, "LedDriver ready with %u LED(s)", num_leds_);
    return ESP_OK;
}

void LedDriver::Deinit()
{
    if (transport_) {
        Ws2812TransportDeinit(transport_);
        transport_ = nullptr;
    }
    free(pixels_);
    free(grb_buf_);
    pixels_ = nullptr;
    grb_buf_ = nullptr;
    num_leds_ = 0;
}

void LedDriver::SetPixel(uint16_t index, RgbColor color)
{
    if (index < num_leds_) {
        pixels_[index] = color;
    }
}

void LedDriver::SetAll(RgbColor color)
{
    for (uint16_t i = 0; i < num_leds_; ++i) {
        pixels_[i] = color;
    }
}

void LedDriver::Clear()
{
    SetAll(RGB_OFF);
}

void LedDriver::SetBrightness(uint8_t brightness)
{
    brightness_ = brightness;
}

uint8_t LedDriver::GetBrightness() const
{
    return brightness_;
}

esp_err_t LedDriver::Show()
{
    if (!transport_) {
        return ESP_ERR_INVALID_STATE;
    }
    _apply_brightness_and_reorder();
    return Ws2812TransportSend(transport_, grb_buf_, num_leds_);
}

uint16_t LedDriver::GetNumLeds() const
{
    return num_leds_;
}

RgbColor LedDriver::GetPixel(uint16_t index) const
{
    if (index < num_leds_) {
        return pixels_[index];
    }
    return RGB_OFF;
}

void LedDriver::_apply_brightness_and_reorder()
{
    for (uint16_t i = 0; i < num_leds_; ++i) {
        /* WS2812 expects GRB wire order */
        grb_buf_[i * 3 + 0] = static_cast<uint8_t>((pixels_[i].g * brightness_ + 127) / 255);
        grb_buf_[i * 3 + 1] = static_cast<uint8_t>((pixels_[i].r * brightness_ + 127) / 255);
        grb_buf_[i * 3 + 2] = static_cast<uint8_t>((pixels_[i].b * brightness_ + 127) / 255);
    }
}

}  // namespace drivers
