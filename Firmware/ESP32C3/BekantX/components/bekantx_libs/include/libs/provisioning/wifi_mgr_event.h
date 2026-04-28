#pragma once

/**
 * @file wifi_mgr_event.h
 * @brief Shared event type posted between the provisioning HTTP handler (C)
 *        and the WifiManager task (C++).
 *
 * Both components include this header.  FreeRTOS queue handles are used as
 * the transport so the types must remain plain C.
 */

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    WIFI_MGR_EVT_STA_STARTED  = 0, /**< WIFI_EVENT_STA_START received     */
    WIFI_MGR_EVT_GOT_IP       = 1, /**< IP_EVENT_STA_GOT_IP received      */
    WIFI_MGR_EVT_DISCONNECTED = 2, /**< WIFI_EVENT_STA_DISCONNECTED received */
    WIFI_MGR_EVT_SAVE_CREDS   = 3, /**< User submitted credentials via portal */
} wifi_mgr_event_type_t;

typedef struct {
    wifi_mgr_event_type_t type;
    char ssid[33];      /**< Populated only when type == WIFI_MGR_EVT_SAVE_CREDS */
    char password[65];  /**< Populated only when type == WIFI_MGR_EVT_SAVE_CREDS */
} wifi_mgr_event_t;

#ifdef __cplusplus
}
#endif
