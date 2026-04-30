#pragma once

struct esp_mqtt_client;
typedef struct esp_mqtt_client *esp_mqtt_client_handle_t;

namespace mqtt {

/**
 * @brief Publishes Home Assistant MQTT Discovery payload for a Cover entity.
 *
 * The discovery message registers the desk as a Cover with device_class "blind"
 * so that HA supports open/close/stop/position controls.  Jinja2 templates in
 * the payload translate HA's native OPEN/CLOSE/STOP into the JSON API.
 */
class MqttDiscovery {
public:
    /**
     * @brief Publish the HA auto-discovery config message (retained).
     * @param client       Active MQTT client handle.
     * @param device_id    Unique device identifier (used in topics and unique_id).
     * @param topic_prefix Prefix for command/state/availability topics.
     * @param discovery_prefix  HA discovery prefix (default "homeassistant").
     * @param qos          QoS level.
     * @return true on success.
     */
    bool PublishDiscoveryConfig(esp_mqtt_client_handle_t client,
                                const char* device_id,
                                const char* topic_prefix,
                                const char* discovery_prefix,
                                int qos);
};

}  // namespace mqtt
