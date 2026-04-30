#include "mqtt/MqttCredentialStore.hpp"

extern "C" {
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"
}

namespace {
constexpr const char* TAG        = "bkx_mqtt_cred";
constexpr const char* NVS_NS     = CONFIG_MQTT_NVS_NAMESPACE;
constexpr const char* KEY_URI    = "mqtt_uri";
constexpr const char* KEY_USER   = "mqtt_user";
constexpr const char* KEY_PASS   = "mqtt_pass";
}

namespace mqtt {

bool MqttCredentialStore::Load(mqtt_credentials_t& out) {
    nvs_handle_t handle;
    if (nvs_open(NVS_NS, NVS_READONLY, &handle) != ESP_OK) {
        return false;
    }

    size_t uri_len  = sizeof(out.broker_uri);
    size_t user_len = sizeof(out.username);
    size_t pass_len = sizeof(out.password);

    /* URI is mandatory; username and password are optional */
    bool ok = (nvs_get_str(handle, KEY_URI, out.broker_uri, &uri_len) == ESP_OK) &&
              (out.broker_uri[0] != '\0');

    if (ok) {
        if (nvs_get_str(handle, KEY_USER, out.username, &user_len) != ESP_OK) {
            out.username[0] = '\0';
        }
        if (nvs_get_str(handle, KEY_PASS, out.password, &pass_len) != ESP_OK) {
            out.password[0] = '\0';
        }
    }

    nvs_close(handle);

    if (ok) {
        ESP_LOGI(TAG, "Loaded MQTT credentials for broker: '%s'", out.broker_uri);
    }
    return ok;
}

bool MqttCredentialStore::Save(const mqtt_credentials_t& creds) {
    nvs_handle_t handle;
    if (nvs_open(NVS_NS, NVS_READWRITE, &handle) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open NVS for write");
        return false;
    }

    bool ok = (nvs_set_str(handle, KEY_URI,  creds.broker_uri) == ESP_OK) &&
              (nvs_set_str(handle, KEY_USER, creds.username)    == ESP_OK) &&
              (nvs_set_str(handle, KEY_PASS, creds.password)    == ESP_OK) &&
              (nvs_commit(handle) == ESP_OK);

    nvs_close(handle);

    if (ok) {
        ESP_LOGI(TAG, "MQTT credentials saved for broker: '%s'", creds.broker_uri);
    } else {
        ESP_LOGE(TAG, "Failed to save MQTT credentials");
    }
    return ok;
}

void MqttCredentialStore::Clear() {
    nvs_handle_t handle;
    if (nvs_open(NVS_NS, NVS_READWRITE, &handle) != ESP_OK) {
        return;
    }
    nvs_erase_key(handle, KEY_URI);
    nvs_erase_key(handle, KEY_USER);
    nvs_erase_key(handle, KEY_PASS);
    nvs_commit(handle);
    nvs_close(handle);
    ESP_LOGI(TAG, "MQTT credentials cleared");
}

}  // namespace mqtt
