#pragma once

#include <cstdint>

extern "C" {
#include "drivers/led_types.h"
}

namespace drivers {

class LedDriver;

class LedAnimator {
public:
    explicit LedAnimator(LedDriver &driver);

    void StartBlink(const LedBlinkConfig &config);
    void StartFade(const LedFadeConfig &config);
    void SetSolid(RgbColor color);
    void Stop();

    bool Tick(uint32_t now_ms);
    bool IsAnimating() const;

private:
    enum class State : uint8_t {
        kIdle,
        kSolid,
        kBlinkOn,
        kBlinkOff,
        kFade,
    };

    void    _tick_blink(uint32_t now_ms);
    void    _tick_fade(uint32_t now_ms);
    uint8_t _fade_brightness(uint32_t elapsed_ms) const;

    LedDriver &driver_;
    State      state_       = State::kIdle;
    uint32_t   phase_start_ = 0;
    uint16_t   blink_count_ = 0;

    LedBlinkConfig blink_cfg_ = {};
    LedFadeConfig  fade_cfg_  = {};
};

}  // namespace drivers
