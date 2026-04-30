#pragma once

/**
 * @file mqtt_types.h
 * @brief Shared types for desk commands, state, and MQTT credentials.
 *
 * Plain C for cross-boundary use (C portal handler, C++ MQTT service).
 */

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* ------------------------------------------------------------------ */
/*  Desk command types                                                  */
/* ------------------------------------------------------------------ */

typedef enum {
    DESK_ACTION_MOVE_UP       = 0,
    DESK_ACTION_MOVE_DOWN     = 1,
    DESK_ACTION_STOP          = 2,
    DESK_ACTION_GOTO_PRESET   = 3,
    DESK_ACTION_GOTO_POSITION = 4,
} desk_action_t;

typedef struct {
    desk_action_t action;
    uint8_t       preset;    /**< Valid when action == DESK_ACTION_GOTO_PRESET (1-based) */
    uint8_t       position;  /**< Valid when action == DESK_ACTION_GOTO_POSITION (0-100%) */
} desk_command_t;

/* ------------------------------------------------------------------ */
/*  Desk state                                                          */
/* ------------------------------------------------------------------ */

typedef enum {
    DESK_MOVEMENT_IDLE      = 0,
    DESK_MOVEMENT_MOVING_UP = 1,
    DESK_MOVEMENT_MOVING_DOWN = 2,
    DESK_MOVEMENT_ERROR     = 3,
} desk_movement_t;

typedef struct {
    desk_movement_t movement;
    float           height_cm;    /**< Current desk height in cm (0 if unknown) */
    uint8_t         position_pct; /**< 0-100% mapped position */
    uint8_t         preset;       /**< Active preset number (0 = none) */
} desk_state_t;

/* ------------------------------------------------------------------ */
/*  MQTT credentials                                                    */
/* ------------------------------------------------------------------ */

typedef struct {
    char broker_uri[128];  /**< e.g. "mqtt://192.168.1.100" */
    char username[65];
    char password[65];
} mqtt_credentials_t;

#ifdef __cplusplus
}
#endif
