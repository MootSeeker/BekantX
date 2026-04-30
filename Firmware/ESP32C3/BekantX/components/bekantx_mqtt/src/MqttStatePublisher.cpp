#include "mqtt/MqttStatePublisher.hpp"

#include <cstdio>

extern "C" {
#include "esp_log.h"
#include "cJSON.h"
#include "mqtt_client.h"
}

namespace {
constexpr const char* TAG = "bkx_mqtt_state";

const char* _movement_to_string(desk_movement_t m) {
    switch (m) {
        case DESK_MOVEMENT_IDLE:       return "idle";
        case DESK_MOVEMENT_MOVING_UP:  return "moving_up";
        case DESK_MOVEMENT_MOVING_DOWN: return "moving_down";
        case DESK_MOVEMENT_ERROR:      return "error";
        default:                       return "unknown";
    }
}
}

namespace mqtt {

void MqttStatePublisher::Init(esp_mqtt_client_handle_t client, const char* topic, int qos)
{
    client_ = client;
    topic_  = topic;
    qos_    = qos;
}

bool MqttStatePublisher::PublishState(const desk_state_t& state)
{
    if (!client_ || !topic_) {
        return false;
    }

    cJSON *root = cJSON_CreateObject();
    if (!root) {
        ESP_LOGE(TAG, "Failed to create JSON object");
        return false;
    }

    cJSON_AddStringToObject(root, "state", _movement_to_string(state.movement));
    cJSON_AddNumberToObject(root, "height_cm", state.height_cm);
    cJSON_AddNumberToObject(root, "position_pct", state.position_pct);
    cJSON_AddNumberToObject(root, "preset", state.preset);

    char *json_str = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);

    if (!json_str) {
        ESP_LOGE(TAG, "Failed to serialize state JSON");
        return false;
    }

    int msg_id = esp_mqtt_client_publish(client_, topic_, json_str, 0,
                                          qos_, 1 /* retain */);
    free(json_str);

    if (msg_id < 0) {
        ESP_LOGW(TAG, "Failed to publish state");
        return false;
    }

    ESP_LOGD(TAG, "State published (msg_id=%d)", msg_id);
    return true;
}

bool MqttStatePublisher::PublishDefaultState()
{
    desk_state_t idle = {};
    idle.movement     = DESK_MOVEMENT_IDLE;
    idle.height_cm    = 0.0f;
    idle.position_pct = 0;
    idle.preset       = 0;
    return PublishState(idle);
}

}  // namespace mqtt
