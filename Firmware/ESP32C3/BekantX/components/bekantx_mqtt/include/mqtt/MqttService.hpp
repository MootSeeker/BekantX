#pragma once

#include <cstdint>
#include <atomic>

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
struct esp_mqtt_client;
typedef struct esp_mqtt_client *esp_mqtt_client_handle_t;

typedef const char *esp_event_base_t;

#include "mqtt/MqttCredentialStore.hpp"
#include "mqtt/MqttCommandHandler.hpp"
#include "mqtt/MqttStatePublisher.hpp"
#include "mqtt/MqttDiscovery.hpp"
#include "mqtt/mqtt_types.h"

namespace mqtt {

/** @brief Publicly observable MQTT connection states. */
enum class MqttState : uint8_t {
    kDisconnected,
    kConnecting,
    kConnected,
    kError,
};

/**
 * @class MqttService
 * @brief Manages the MQTT client lifecycle, subscribes to command topics,
 *        publishes state and HA discovery, and dispatches incoming commands.
 *
 * MQTT connection is triggered by IP_EVENT_STA_GOT_IP and torn down on
 * WIFI_EVENT_STA_DISCONNECTED.  The service runs its own FreeRTOS task
 * to process MQTT events from an internal queue.
 */
class MqttService {
public:
    /**
     * @brief Initialise the MQTT service.
     * @param store    Reference to MqttCredentialStore to load broker credentials.
     */
    void Init(MqttCredentialStore& store);

    /** @brief Register IP/WiFi event handlers.  Call after Init. */
    void Start();

    /** @brief Stop MQTT client and unregister events. */
    void Stop();

    /** @brief Thread-safe read of the current MQTT state. */
    MqttState GetState() const;

    /** @brief Queue of validated desk commands (for future SPI bridge consumer). */
    QueueHandle_t GetCommandQueue() const;

private:
    /* Internal event types posted to the service queue */
    enum class SvcEvent : uint8_t {
        kGotIp,
        kWifiDisconnected,
        kMqttConnected,
        kMqttDisconnected,
        kMqttData,
        kMqttError,
    };

    struct SvcEventMsg {
        SvcEvent type;
        char     topic[96];
        char     data[256];
        int      data_len;
    };

    /* Task entry and main loop */
    static void _task_entry(void* arg);
    void        _run_task();

    /* ESP-IDF event handlers */
    static void _wifi_event_handler(void* arg, esp_event_base_t base,
                                    int32_t id, void* data);
    static void _ip_event_handler(void* arg, esp_event_base_t base,
                                  int32_t id, void* data);
    static void _mqtt_event_handler(void* arg, esp_event_base_t base,
                                    int32_t id, void* data);

    /* Actions */
    void _connect_mqtt();
    void _disconnect_mqtt();
    void _on_mqtt_connected();
    void _on_mqtt_data(const char* topic, const char* data, int data_len);

    /* Build topic strings */
    void _build_topics();

    /* ---- members ---- */
    MqttCredentialStore*          cred_store_ = nullptr;

    esp_mqtt_client_handle_t  mqtt_client_   = nullptr;
    QueueHandle_t             svc_queue_     = nullptr;
    QueueHandle_t             cmd_queue_     = nullptr;
    TaskHandle_t              task_handle_   = nullptr;

    MqttCommandHandler  cmd_handler_;
    MqttStatePublisher  state_pub_;
    MqttDiscovery       discovery_;

    mqtt_credentials_t  credentials_ = {};
    bool                mqtt_started_ = false;

    /* Topic buffers */
    char topic_command_[96]   = {};
    char topic_state_[96]     = {};
    char topic_available_[96] = {};

    std::atomic<MqttState> public_state_{ MqttState::kDisconnected };
};

}  // namespace mqtt
