#include "mqtt/MqttDiscovery.hpp"

#include <cstdio>

extern "C" {
#include "esp_log.h"
#include "esp_app_desc.h"
#include "cJSON.h"
#include "mqtt_client.h"
}

namespace {
constexpr const char* TAG = "bkx_mqtt_disc";
}

namespace mqtt {

bool MqttDiscovery::PublishDiscoveryConfig(esp_mqtt_client_handle_t client,
                                            const char* device_id,
                                            const char* topic_prefix,
                                            const char* discovery_prefix,
                                            int qos)
{
    if (!client || !device_id || !topic_prefix || !discovery_prefix) {
        return false;
    }

    /* Build discovery topic: homeassistant/cover/{device_id}/config */
    char disc_topic[128];
    snprintf(disc_topic, sizeof(disc_topic), "%s/cover/%s/config",
             discovery_prefix, device_id);

    /* Build topic strings */
    char cmd_topic[96];
    char state_topic[96];
    char avail_topic[96];
    snprintf(cmd_topic,   sizeof(cmd_topic),   "%s/%s/command",   topic_prefix, device_id);
    snprintf(state_topic, sizeof(state_topic), "%s/%s/state",     topic_prefix, device_id);
    snprintf(avail_topic, sizeof(avail_topic), "%s/%s/available", topic_prefix, device_id);

    /* Build unique_id */
    char unique_id[64];
    snprintf(unique_id, sizeof(unique_id), "bekantx_%s", device_id);

    /* Software version from app descriptor */
    const esp_app_desc_t *app_desc = esp_app_get_description();
    const char *sw_version = app_desc ? app_desc->version : "0.0.0";

    /* Build JSON payload */
    cJSON *root = cJSON_CreateObject();
    if (!root) {
        ESP_LOGE(TAG, "Failed to create discovery JSON");
        return false;
    }

    cJSON_AddStringToObject(root, "name", "BekantX Desk");
    cJSON_AddStringToObject(root, "unique_id", unique_id);
    cJSON_AddStringToObject(root, "object_id", "bekantx_desk");
    cJSON_AddStringToObject(root, "device_class", "blind");

    /* Command topic + template: HA OPEN/CLOSE/STOP → JSON */
    cJSON_AddStringToObject(root, "command_topic", cmd_topic);
    cJSON_AddStringToObject(root, "command_template",
        "{\"action\": \""
        "{% if value == 'OPEN' %}move_up"
        "{% elif value == 'CLOSE' %}move_down"
        "{% elif value == 'STOP' %}stop"
        "{% endif %}\"}");

    /* Position set topic + template */
    cJSON_AddStringToObject(root, "set_position_topic", cmd_topic);
    cJSON_AddStringToObject(root, "set_position_template",
        "{\"action\": \"goto_position\", \"position\": {{ position }}}");

    /* State topic + value template */
    cJSON_AddStringToObject(root, "state_topic", state_topic);
    cJSON_AddStringToObject(root, "value_template",
        "{% if value_json.state == 'moving_up' %}opening"
        "{% elif value_json.state == 'moving_down' %}closing"
        "{% else %}stopped{% endif %}");

    /* Position feedback */
    cJSON_AddStringToObject(root, "position_topic", state_topic);
    cJSON_AddStringToObject(root, "position_template", "{{ value_json.position_pct }}");

    /* Availability */
    cJSON_AddStringToObject(root, "availability_topic", avail_topic);

    /* Device block */
    cJSON *device = cJSON_AddObjectToObject(root, "device");
    if (device) {
        cJSON *ids = cJSON_AddArrayToObject(device, "identifiers");
        if (ids) {
            cJSON_AddItemToArray(ids, cJSON_CreateString(unique_id));
        }
        cJSON_AddStringToObject(device, "name", "BekantX Standing Desk");
        cJSON_AddStringToObject(device, "manufacturer", "BekantX");
        cJSON_AddStringToObject(device, "model", "ESP32-C3 Coprocessor");
        cJSON_AddStringToObject(device, "sw_version", sw_version);
    }

    char *json_str = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);

    if (!json_str) {
        ESP_LOGE(TAG, "Failed to serialize discovery JSON");
        return false;
    }

    int msg_id = esp_mqtt_client_publish(client, disc_topic, json_str, 0,
                                          qos, 1 /* retain */);
    free(json_str);

    if (msg_id < 0) {
        ESP_LOGW(TAG, "Failed to publish discovery config");
        return false;
    }

    ESP_LOGI(TAG, "HA discovery published to '%s' (msg_id=%d)", disc_topic, msg_id);
    return true;
}

}  // namespace mqtt
