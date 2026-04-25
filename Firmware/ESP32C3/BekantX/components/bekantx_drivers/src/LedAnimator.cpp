#include "drivers/LedAnimator.hpp"
#include "drivers/LedDriver.hpp"

extern "C" {
#include "esp_log.h"
}

namespace {
constexpr const char *TAG = "bkx_led_anim";
}

namespace drivers {

LedAnimator::LedAnimator(LedDriver &driver)
    : driver_(driver)
{
}

void LedAnimator::StartBlink(const LedBlinkConfig &config)
{
    blink_cfg_   = config;
    blink_count_ = config.repeat_count;
    phase_start_ = 0;
    state_       = State::kBlinkOn;

    driver_.SetBrightness(255);
    driver_.SetAll(config.color);
    driver_.Show();

    ESP_LOGD(TAG, "Blink started: on=%ums off=%ums count=%u",
             config.on_ms, config.off_ms, config.repeat_count);
}

void LedAnimator::StartFade(const LedFadeConfig &config)
{
    fade_cfg_    = config;
    phase_start_ = 0;
    state_       = State::kFade;

    ESP_LOGD(TAG, "Fade started: period=%ums mode=%d", config.period_ms, config.mode);
}

void LedAnimator::SetSolid(RgbColor color)
{
    state_ = State::kSolid;
    driver_.SetBrightness(255);
    driver_.SetAll(color);
    driver_.Show();
}

void LedAnimator::Stop()
{
    state_ = State::kIdle;
    driver_.Clear();
    driver_.Show();
}

bool LedAnimator::Tick(uint32_t now_ms)
{
    switch (state_) {
        case State::kIdle:
        case State::kSolid:
            return false;
        case State::kBlinkOn:
        case State::kBlinkOff:
            _tick_blink(now_ms);
            return true;
        case State::kFade:
            _tick_fade(now_ms);
            return true;
    }
    return false;
}

bool LedAnimator::IsAnimating() const
{
    return state_ != State::kIdle && state_ != State::kSolid;
}

void LedAnimator::_tick_blink(uint32_t now_ms)
{
    /* Lazy-init phase_start_ on first tick after StartBlink */
    if (phase_start_ == 0) {
        phase_start_ = now_ms;
        return;
    }

    uint32_t elapsed = now_ms - phase_start_;

    if (state_ == State::kBlinkOn) {
        if (elapsed >= blink_cfg_.on_ms) {
            driver_.Clear();
            driver_.Show();
            phase_start_ = now_ms;
            state_ = State::kBlinkOff;

            /* Decrement blink counter for finite repeats */
            if (blink_cfg_.repeat_count != 0) {
                if (blink_count_ > 0) {
                    --blink_count_;
                }
                if (blink_count_ == 0) {
                    state_ = State::kIdle;
                }
            }
        }
    } else { /* kBlinkOff */
        if (elapsed >= blink_cfg_.off_ms) {
            driver_.SetAll(blink_cfg_.color);
            driver_.Show();
            phase_start_ = now_ms;
            state_ = State::kBlinkOn;
        }
    }
}

void LedAnimator::_tick_fade(uint32_t now_ms)
{
    /* Lazy-init phase_start_ on first tick after StartFade */
    if (phase_start_ == 0) {
        phase_start_ = now_ms;
    }

    uint32_t elapsed = now_ms - phase_start_;
    uint8_t bright = _fade_brightness(elapsed);

    driver_.SetBrightness(bright);
    driver_.SetAll(fade_cfg_.color);
    driver_.Show();
}

uint8_t LedAnimator::_fade_brightness(uint32_t elapsed_ms) const
{
    if (fade_cfg_.period_ms == 0) {
        return fade_cfg_.max_bright;
    }

    uint32_t pos   = elapsed_ms % fade_cfg_.period_ms;
    uint32_t range = fade_cfg_.max_bright - fade_cfg_.min_bright;

    switch (fade_cfg_.mode) {
        case LED_FADE_IN:
            return static_cast<uint8_t>(fade_cfg_.min_bright + (range * pos) / fade_cfg_.period_ms);

        case LED_FADE_OUT:
            return static_cast<uint8_t>(fade_cfg_.max_bright - (range * pos) / fade_cfg_.period_ms);

        case LED_FADE_IN_OUT: {
            uint32_t half = fade_cfg_.period_ms / 2;
            if (half == 0) {
                return fade_cfg_.max_bright;
            }
            if (pos < half) {
                return static_cast<uint8_t>(fade_cfg_.min_bright + (range * pos) / half);
            } else {
                uint32_t down_pos = pos - half;
                return static_cast<uint8_t>(fade_cfg_.max_bright - (range * down_pos) / half);
            }
        }

        case LED_BREATH: {
            /* Split period into rising (first half) and falling (second half).
             * Map position to t ∈ [0, 255] in both halves:
             *   rising:  t goes  0 → 255
             *   falling: t goes 255 →   0
             * Apply cubic smooth-step  s(t) = 3t² − 2t³  (output [0, 255]).
             * The slope of s is zero at t=0 and t=255, so the rate of change
             * is near-zero at the darkest and brightest points.  This means
             * the jump at the period wrap (both sides: t=0, s=0) is invisible.
             */
            uint32_t half = (fade_cfg_.period_ms > 1u) ? (fade_cfg_.period_ms / 2u) : 1u;
            uint32_t t;
            if (pos < half) {
                t = (pos * 256u) / half;                     /* 0 → 255 */
            } else {
                t = 255u - ((pos - half) * 256u) / half;    /* 255 → 0 */
            }
            if (t > 255u) t = 255u;  /* guard rounding edge case */

            /* s(t) = 3t² − 2t³, all in integer, output ∈ [0, 255] */
            uint32_t smooth = (3u * t * t - 2u * t * t * t / 256u) / 256u;
            return static_cast<uint8_t>(
                fade_cfg_.min_bright + (range * smooth + 127u) / 255u);
        }
    }
    return fade_cfg_.min_bright;
}

}  // namespace drivers
