#pragma once

#include <cstdint>

extern "C" {
#include "drivers/led_types.h"
#include "drivers/ws2812_transport.h"
}

namespace drivers {

class LedDriver {
public:
    esp_err_t Init(const LedTransportConfig &config);
    void      Deinit();

    void SetPixel(uint16_t index, RgbColor color);
    void SetAll(RgbColor color);
    void Clear();

    void    SetBrightness(uint8_t brightness);
    uint8_t GetBrightness() const;

    esp_err_t Show();

    uint16_t GetNumLeds() const;
    RgbColor GetPixel(uint16_t index) const;

private:
    void _apply_brightness_and_reorder();

    ws2812_transport_handle_t transport_   = nullptr;
    RgbColor *pixels_    = nullptr;
    uint8_t  *grb_buf_   = nullptr;
    uint16_t  num_leds_  = 0;
    uint8_t   brightness_ = 255;
};

}  // namespace drivers
