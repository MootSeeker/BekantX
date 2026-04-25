#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint8_t r;
    uint8_t g;
    uint8_t b;
} RgbColor;

#define RGB_OFF      ((RgbColor){  0,   0,   0})
#define RGB_RED      ((RgbColor){255,   0,   0})
#define RGB_GREEN    ((RgbColor){  0, 255,   0})
#define RGB_BLUE     ((RgbColor){  0,   0, 255})
#define RGB_WHITE    ((RgbColor){255, 255, 255})
#define RGB_YELLOW   ((RgbColor){255, 255,   0})
#define RGB_CYAN     ((RgbColor){  0, 255, 255})
#define RGB_MAGENTA  ((RgbColor){255,   0, 255})
#define RGB_ORANGE   ((RgbColor){255, 128,   0})

typedef struct {
    int      gpio_num;
    uint16_t num_leds;
    uint32_t rmt_resolution_hz;
} LedTransportConfig;

typedef struct {
    RgbColor color;
    uint16_t on_ms;
    uint16_t off_ms;
    uint16_t repeat_count;  /* 0 = infinite */
} LedBlinkConfig;

typedef enum {
    LED_FADE_IN,
    LED_FADE_OUT,
    LED_FADE_IN_OUT,
    LED_BREATH,   /* Smooth 0→max→0 using cubic ease; no flicker at wrap */
} LedFadeMode;

typedef struct {
    RgbColor    color;
    LedFadeMode mode;
    uint16_t    period_ms;
    uint8_t     min_bright;
    uint8_t     max_bright;
} LedFadeConfig;

#ifdef __cplusplus
}
#endif
