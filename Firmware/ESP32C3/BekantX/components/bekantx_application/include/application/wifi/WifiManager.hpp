#pragma once

#include <cstdint>
#include <atomic>

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "esp_netif.h"
#include "esp_http_server.h"

#include "application/wifi/WifiCredentialStore.hpp"
#include "libs/provisioning/wifi_mgr_event.h"

namespace mqtt { class MqttCredentialStore; }

namespace application {

class StatusIndicator;

/** @brief Publicly observable Wi-Fi manager states. */
enum class WifiState : uint8_t {
    kInit,
    kConnecting,
    kConnected,
    kPortal,
};

/**
 * @class WifiManager
 * @brief Manages Wi-Fi credentials, STA connection, and SoftAP provisioning portal.
 *
 * State machine:
 *   Boot → load NVS credentials
 *     ├─ found: kConnecting (up to MAX_ATTEMPTS, exponential backoff)
 *     │    ├─ success: kConnected (reconnects automatically on drop)
 *     │    └─ all attempts failed: kPortal
 *     └─ not found: kPortal
 *          └─ user saves credentials via web page: kConnecting
 *
 * All Wi-Fi and IP events are posted to an internal FreeRTOS queue;
 * the WifiManager task is the only consumer.
 * The provisioning HTTP handler also posts to the same queue.
 */
class WifiManager {
public:
    /**
     * @brief Initialise subsystems: NVS, netif, event loop, Wi-Fi driver.
     * @note  Must be called before Start().
     * @param status      Reference to the application StatusIndicator for LED updates.
     * @param mqtt_store  Optional reference to MqttCredentialStore.
     *                    When non-null, MQTT credentials from the portal are
     *                    saved here alongside Wi-Fi credentials.
     */
    void Init(StatusIndicator& status,
              mqtt::MqttCredentialStore* mqtt_store = nullptr);

    /** @brief Spawn the wifi_mgr_task and begin the state machine. */
    void Start();

    /** @brief Thread-safe read of the current Wi-Fi state. */
    WifiState GetState() const;

    /**
     * @brief Force a transition to portal mode on the next task loop iteration.
     *        Intended as a future hook for GPIO or SPI-triggered reset.
     */
    void ForceProvisioning();

private:
    /* Internal state labels (not the same as the public WifiState) */
    enum class State : uint8_t {
        kConnecting,
        kConnected,
        kPortal,
    };

    /* Task entry and main loop */
    static void _task_entry(void *arg);
    void        _run_task();

    /* State transitions */
    void _enter_connecting(const WifiCredentials& creds);
    void _enter_portal();
    void _stop_portal();
    void _on_connect_failure();
    void _enter_deep_sleep();

    /* Event dispatcher */
    void _dispatch_event(const wifi_mgr_event_t& evt);

    /* SoftAP configuration */
    void _configure_softap();

    /* Static ESP-IDF event handlers — post to queue only */
    static void _wifi_event_handler(void *arg, esp_event_base_t base,
                                    int32_t id, void *data);
    static void _ip_event_handler(void *arg, esp_event_base_t base,
                                  int32_t id, void *data);

    /* ---- members ---- */
    StatusIndicator *status_       = nullptr;
    mqtt::MqttCredentialStore *mqtt_store_ = nullptr;
    QueueHandle_t    event_queue_  = nullptr;
    TaskHandle_t     task_handle_  = nullptr;

    esp_netif_t     *sta_netif_    = nullptr;
    esp_netif_t     *ap_netif_     = nullptr;

    httpd_handle_t   httpd_        = nullptr;
    bool             dns_running_  = false;
    bool             wifi_started_ = false;

    State            state_             = State::kConnecting;
    int              connect_attempts_  = 0;
    std::atomic<bool> force_portal_{false};
    bool             creds_loaded_      = false; /**< true when NVS had credentials at boot */

    WifiCredentialStore store_;
    WifiCredentials     current_creds_  = {};

    std::atomic<WifiState> public_state_{ WifiState::kInit };
};

}  // namespace application
