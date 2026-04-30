#include "application/wifi/WifiCredentialStore.hpp"

extern "C" {
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"
}

namespace {
constexpr const char* TAG       = "bkx_cred";
constexpr const char* NVS_NS    = CONFIG_WIFI_MGR_NVS_NAMESPACE;
constexpr const char* KEY_SSID  = "ssid";
constexpr const char* KEY_PASS  = "pass";
}

namespace application {

bool WifiCredentialStore::Load(WifiCredentials& out) {
    nvs_handle_t handle;
    if (nvs_open(NVS_NS, NVS_READONLY, &handle) != ESP_OK) {
        return false;
    }

    size_t ssid_len = sizeof(out.ssid);
    size_t pass_len = sizeof(out.password);

    bool ok = (nvs_get_str(handle, KEY_SSID, out.ssid, &ssid_len) == ESP_OK) &&
              (nvs_get_str(handle, KEY_PASS, out.password, &pass_len) == ESP_OK) &&
              (out.ssid[0] != '\0');

    nvs_close(handle);

    if (ok) {
        ESP_LOGI(TAG, "Loaded credentials for SSID: '%s'", out.ssid);
    }
    return ok;
}

bool WifiCredentialStore::Save(const WifiCredentials& creds) {
    nvs_handle_t handle;
    if (nvs_open(NVS_NS, NVS_READWRITE, &handle) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open NVS for write");
        return false;
    }

    bool ok = (nvs_set_str(handle, KEY_SSID, creds.ssid) == ESP_OK) &&
              (nvs_set_str(handle, KEY_PASS, creds.password) == ESP_OK) &&
              (nvs_commit(handle) == ESP_OK);

    nvs_close(handle);

    if (ok) {
        ESP_LOGI(TAG, "Credentials saved for SSID: '%s'", creds.ssid);
    } else {
        ESP_LOGE(TAG, "Failed to save credentials");
    }
    return ok;
}

void WifiCredentialStore::Clear() {
    nvs_handle_t handle;
    if (nvs_open(NVS_NS, NVS_READWRITE, &handle) != ESP_OK) {
        return;
    }
    nvs_erase_key(handle, KEY_SSID);
    nvs_erase_key(handle, KEY_PASS);
    nvs_commit(handle);
    nvs_close(handle);
    ESP_LOGI(TAG, "Credentials cleared");
}

}  // namespace application
