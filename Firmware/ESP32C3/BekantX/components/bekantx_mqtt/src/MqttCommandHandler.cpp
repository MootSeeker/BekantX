#include "mqtt/MqttCommandHandler.hpp"

#include <cstring>

extern "C" {
#include "esp_log.h"
#include "esp_timer.h"
#include "cJSON.h"
}

namespace {
constexpr const char* TAG = "bkx_mqtt_cmd";
constexpr uint32_t DEDUP_WINDOW_MS = 500;
}

namespace mqtt {

void MqttCommandHandler::Init(QueueHandle_t cmd_queue)
{
    cmd_queue_ = cmd_queue;
    memset(&last_cmd_, 0, sizeof(last_cmd_));
    last_cmd_time_ = 0;
}

void MqttCommandHandler::HandleMessage(const char* topic, const char* payload, int len)
{
    if (!payload || len <= 0) {
        ESP_LOGW(TAG, "Empty payload on topic '%s'", topic ? topic : "?");
        return;
    }

    /* Parse JSON */
    cJSON *root = cJSON_ParseWithLength(payload, (size_t)len);
    if (!root) {
        ESP_LOGW(TAG, "Invalid JSON on topic '%s'", topic ? topic : "?");
        return;
    }

    /* Extract action string */
    cJSON *action_item = cJSON_GetObjectItemCaseSensitive(root, "action");
    if (!cJSON_IsString(action_item) || !action_item->valuestring) {
        ESP_LOGW(TAG, "Missing or invalid 'action' field");
        cJSON_Delete(root);
        return;
    }

    const char *action_str = action_item->valuestring;
    desk_command_t cmd = {};

    /* Map action string → enum */
    if (strcmp(action_str, "move_up") == 0) {
        cmd.action = DESK_ACTION_MOVE_UP;
    } else if (strcmp(action_str, "move_down") == 0) {
        cmd.action = DESK_ACTION_MOVE_DOWN;
    } else if (strcmp(action_str, "stop") == 0) {
        cmd.action = DESK_ACTION_STOP;
    } else if (strcmp(action_str, "goto_preset") == 0) {
        cmd.action = DESK_ACTION_GOTO_PRESET;
        cJSON *preset_item = cJSON_GetObjectItemCaseSensitive(root, "preset");
        if (!cJSON_IsNumber(preset_item) || preset_item->valueint < 1 || preset_item->valueint > 255) {
            ESP_LOGW(TAG, "goto_preset requires 'preset' field (1-255)");
            cJSON_Delete(root);
            return;
        }
        cmd.preset = (uint8_t)preset_item->valueint;
    } else if (strcmp(action_str, "goto_position") == 0) {
        cmd.action = DESK_ACTION_GOTO_POSITION;
        cJSON *pos_item = cJSON_GetObjectItemCaseSensitive(root, "position");
        if (!cJSON_IsNumber(pos_item) || pos_item->valueint < 0 || pos_item->valueint > 100) {
            ESP_LOGW(TAG, "goto_position requires 'position' field (0-100)");
            cJSON_Delete(root);
            return;
        }
        cmd.position = (uint8_t)pos_item->valueint;
    } else {
        ESP_LOGW(TAG, "Unknown action: '%s'", action_str);
        cJSON_Delete(root);
        return;
    }

    cJSON_Delete(root);

    /* Deduplication: drop identical commands within window */
    uint32_t now_ms = (uint32_t)(esp_timer_get_time() / 1000);
    if ((now_ms - last_cmd_time_) < DEDUP_WINDOW_MS &&
        memcmp(&cmd, &last_cmd_, sizeof(desk_command_t)) == 0) {
        ESP_LOGD(TAG, "Duplicate command dropped (dedup window)");
        return;
    }
    last_cmd_      = cmd;
    last_cmd_time_ = now_ms;

    /* Enqueue for SPI bridge (or logging stub) */
    if (cmd_queue_) {
        if (xQueueSend(cmd_queue_, &cmd, 0) != pdTRUE) {
            ESP_LOGW(TAG, "Command queue full, command dropped");
            return;
        }
    }

    ESP_LOGI(TAG, "Command dispatched: action=%d preset=%u pos=%u",
             (int)cmd.action, cmd.preset, cmd.position);
}

}  // namespace mqtt
