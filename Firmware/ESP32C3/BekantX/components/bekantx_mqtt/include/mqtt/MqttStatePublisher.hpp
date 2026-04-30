#pragma once

struct esp_mqtt_client;
typedef struct esp_mqtt_client *esp_mqtt_client_handle_t;

extern "C" {
#include "mqtt/mqtt_types.h"
}

namespace mqtt {

/**
 * @brief Serialises DeskState to JSON and publishes to the state topic.
 */
class MqttStatePublisher {
public:
    /**
     * @brief Initialise with MQTT client and topic.
     * @param client   Active esp_mqtt_client handle.
     * @param topic    Full state topic string (must outlive this object).
     * @param qos      QoS level for publishes.
     */
    void Init(esp_mqtt_client_handle_t client, const char* topic, int qos);

    /**
     * @brief Publish current desk state as retained JSON message.
     * @return true on success.
     */
    bool PublishState(const desk_state_t& state);

    /** @brief Publish a default idle state (used on initial connect). */
    bool PublishDefaultState();

private:
    esp_mqtt_client_handle_t client_ = nullptr;
    const char*              topic_  = nullptr;
    int                      qos_    = 1;
};

}  // namespace mqtt
