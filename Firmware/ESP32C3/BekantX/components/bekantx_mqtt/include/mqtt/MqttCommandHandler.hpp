#pragma once

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

extern "C" {
#include "mqtt/mqtt_types.h"
}

namespace mqtt {

/**
 * @brief Parses incoming JSON command payloads and dispatches valid
 *        DeskCommands to a FreeRTOS queue.
 *
 * Includes a deduplication window: identical consecutive commands
 * received within a configurable time window are silently dropped.
 */
class MqttCommandHandler {
public:
    /**
     * @brief Initialise the command handler.
     * @param cmd_queue  Queue to push validated DeskCommand structs into.
     */
    void Init(QueueHandle_t cmd_queue);

    /**
     * @brief Handle an incoming MQTT message payload.
     * @param topic   MQTT topic (for logging).
     * @param payload Raw JSON payload bytes.
     * @param len     Payload length.
     */
    void HandleMessage(const char* topic, const char* payload, int len);

private:
    QueueHandle_t cmd_queue_        = nullptr;
    desk_command_t last_cmd_        = {};
    uint32_t       last_cmd_time_   = 0;
};

}  // namespace mqtt
