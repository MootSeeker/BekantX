#pragma once

#include <cstdint>

extern "C" {
#include "drivers/led_types.h"
}

/**
 * @brief The StatusIndicator class manages the device's status indication using an LED driver and animator.
 * @note This class is responsible for setting the device's status, applying the corresponding LED patterns
 *         based on the current status, and updating the LED state in the main application loop.
 */
namespace drivers 
{
    // Forward declarations to avoid circular dependencies
    class LedDriver;
    class LedAnimator;
}

namespace application 
{
    /**
     * @enum DeviceStatus 
     * @brief Represents the various statuses of the device, each corresponding to a specific LED pattern.
     * @note The kNone status is a sentinel value used to indicate an unset default status and should 
     *          never be passed to the _apply_pattern method.
     */
    enum class DeviceStatus : uint8_t {
        kBooting,
        kReady,
        kConnecting,
        kConnected,
        kWifiPortal,  /* SoftAP provisioning portal active — awaiting credentials */
        kError,
        kOta,
        kSleep,
        kNone = 0xFF,  /* Sentinel — unset default, never passed to _apply_pattern */
    };

/**
 * @class StatusIndicator
 * @brief Manages the device's status indication using an LED driver and animator.
 * @note This class is responsible for setting the device's status, applying the corresponding LED patterns
 *         based on the current status, and updating the LED state in the main application loop.
 */
class StatusIndicator 
{
    public:
        /**
         * @brief Constructs a StatusIndicator with the given LED driver and animator.
         * @param driver The LED driver used to control the LEDs.
         * @param animator The LED animator used to create LED patterns.
         */
        StatusIndicator(drivers::LedDriver &driver, drivers::LedAnimator &animator);

        /**
         * @brief Sets the current device status and applies the corresponding LED pattern.
         * @param status The new device status to set.
         */
        void SetStatus(DeviceStatus status);

        /**
         * @brief Gets the current device status.
         * @return The current device status.
         */
        DeviceStatus GetStatus() const;

        /**
         * @brief Updates the LED state based on the current status.
         * @param now_ms The current time in milliseconds.
         */
        void Tick(uint32_t now_ms);

    private:
        /**
         * @brief Applies the LED pattern corresponding to the given device status.
         * @param status The device status for which to apply the LED pattern.
         * @note The kNone status is a sentinel value used to indicate an unset default status and should 
         *          never be passed to this method.
         */
        void _apply_pattern(DeviceStatus status);

        // References to the LED driver and animator used to control the LEDs based on the device status.
        drivers::LedDriver   &driver_;
        drivers::LedAnimator &animator_;
        DeviceStatus          current_ = DeviceStatus::kNone;
};

}  // namespace application
