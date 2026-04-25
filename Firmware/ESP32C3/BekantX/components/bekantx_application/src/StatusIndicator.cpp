#include "application/StatusIndicator.hpp"
#include "drivers/LedDriver.hpp"
#include "drivers/LedAnimator.hpp"

extern "C" {
#include "esp_log.h"
}

namespace {
constexpr const char *TAG = "bkx_status";
}

namespace application {

StatusIndicator::StatusIndicator(drivers::LedDriver &driver, drivers::LedAnimator &animator)
    : driver_(driver)
    , animator_(animator)
{
}

void StatusIndicator::SetStatus(DeviceStatus status)
{
    if (status == current_) {
        return;  /* Idempotent: avoid restarting animations */
    }

    ESP_LOGI(TAG, "Status change: %u -> %u",
             static_cast<unsigned>(current_), static_cast<unsigned>(status));

    current_ = status;
    _apply_pattern(status);
}

DeviceStatus StatusIndicator::GetStatus() const
{
    return current_;
}

void StatusIndicator::Tick(uint32_t now_ms)
{
    animator_.Tick(now_ms);
}

void StatusIndicator::_apply_pattern(DeviceStatus status)
{
    switch (status) {
        case DeviceStatus::kBooting: {
            LedFadeConfig cfg = {
                .color      = RGB_YELLOW,
                .mode       = LED_BREATH,
                .period_ms  = 2000,
                .min_bright = 0,
                .max_bright = 100,
            };
            animator_.StartFade(cfg);
            break;
        }
        case DeviceStatus::kReady:
            animator_.SetSolid(RGB_GREEN);
            break;

        case DeviceStatus::kConnecting: {
            LedBlinkConfig cfg = {
                .color        = RGB_BLUE,
                .on_ms        = 500,
                .off_ms       = 500,
                .repeat_count = 0,  /* infinite */
            };
            animator_.StartBlink(cfg);
            break;
        }
        case DeviceStatus::kConnected:
            animator_.SetSolid(RGB_BLUE);
            break;

        case DeviceStatus::kError: {
            LedBlinkConfig cfg = {
                .color        = RGB_RED,
                .on_ms        = 150,
                .off_ms       = 150,
                .repeat_count = 0,  /* infinite */
            };
            animator_.StartBlink(cfg);
            break;
        }
        case DeviceStatus::kOta: {
            LedFadeConfig cfg = {
                .color      = RGB_MAGENTA,
                .mode       = LED_FADE_IN_OUT,
                .period_ms  = 1200,
                .min_bright = 10,
                .max_bright = 200,
            };
            animator_.StartFade(cfg);
            break;
        }
        case DeviceStatus::kSleep:
            animator_.Stop();
            break;
        case DeviceStatus::kNone:
            break;
    }
}

}  // namespace application
