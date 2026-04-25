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

/**
 * @brief Constructs a StatusIndicator with the given LED driver and animator.
 */
StatusIndicator::StatusIndicator(drivers::LedDriver &driver, drivers::LedAnimator &animator)
    : driver_(driver)
    , animator_(animator)
{
}

/**
 * @brief Sets the current device status and applies the corresponding LED pattern.
 */
void StatusIndicator::SetStatus(DeviceStatus status)
{
    if (status == current_) 
    {
        return;  /* Idempotent: avoid restarting animations */
    }

    ESP_LOGI(TAG, "Status change: %u -> %u", static_cast<unsigned>(current_), static_cast<unsigned>(status));

    current_ = status;
    _apply_pattern(status);
}

/**
 * @brief Gets the current device status.
 */
DeviceStatus StatusIndicator::GetStatus() const
{
    return current_;
}

/**
 * @brief Updates the LED state based on the current status.
 */
void StatusIndicator::Tick(uint32_t now_ms)
{
    animator_.Tick(now_ms);
}

/**
 * @brief Applies the LED pattern corresponding to the given device status.
 */
void StatusIndicator::_apply_pattern(DeviceStatus status)
{
    switch (status) 
    {
        // Patterns are designed to be visually distinct and convey the device's state at a glance.
        case DeviceStatus::kBooting: 
        {
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

        // A solid green light indicates that the device is ready for use.
        case DeviceStatus::kReady:
        {
            animator_.SetSolid(RGB_GREEN);
            break;
        }

        // A blinking blue light indicates that the device is attempting to connect.
        case DeviceStatus::kConnecting: 
        {
            LedBlinkConfig cfg = {
                .color        = RGB_BLUE,
                .on_ms        = 500,
                .off_ms       = 500,
                .repeat_count = 0,  /* infinite */
            };
            animator_.StartBlink(cfg);
            break;
        }

        // A solid blue light indicates that the device is connected.
        case DeviceStatus::kConnected:
            animator_.SetSolid(RGB_BLUE);
            break;

        // A blinking red light indicates that the device has encountered an error.
        case DeviceStatus::kError: 
        {
            LedBlinkConfig cfg = {
                .color        = RGB_RED,
                .on_ms        = 150,
                .off_ms       = 150,
                .repeat_count = 0,  /* infinite */
            };
            animator_.StartBlink(cfg);
            break;
        }

        // A slow fading magenta light indicates that the device is performing an OTA update.
        case DeviceStatus::kOta: 
        {
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

        // A solid off light indicates that the device is in sleep mode.
        case DeviceStatus::kSleep:
        {
            animator_.Stop();
            break;
        }

        // The kNone status is a sentinel value used to indicate an unset default status and should never be passed to this method.
        case DeviceStatus::kNone:
        default: 
            break; 
    }
}

}  // namespace application
