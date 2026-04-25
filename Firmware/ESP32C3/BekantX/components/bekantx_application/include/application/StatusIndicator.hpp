#pragma once

#include <cstdint>

extern "C" {
#include "drivers/led_types.h"
}

namespace drivers {
class LedDriver;
class LedAnimator;
}

namespace application {

enum class DeviceStatus : uint8_t {
    kBooting,
    kReady,
    kConnecting,
    kConnected,
    kError,
    kOta,
    kSleep,
    kNone = 0xFF,  /* Sentinel — unset default, never passed to _apply_pattern */
};

class StatusIndicator {
public:
    StatusIndicator(drivers::LedDriver &driver, drivers::LedAnimator &animator);

    void SetStatus(DeviceStatus status);
    DeviceStatus GetStatus() const;
    void Tick(uint32_t now_ms);

private:
    void _apply_pattern(DeviceStatus status);

    drivers::LedDriver   &driver_;
    drivers::LedAnimator &animator_;
    DeviceStatus          current_ = DeviceStatus::kNone;
};

}  // namespace application
