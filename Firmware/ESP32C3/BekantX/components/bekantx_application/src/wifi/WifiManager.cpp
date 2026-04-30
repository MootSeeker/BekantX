#include "application/wifi/WifiManager.hpp"
#include "application/StatusIndicator.hpp"
#include "mqtt/MqttCredentialStore.hpp"

#include <cstring>
#include <cstdio>

extern "C" {
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_sleep.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "libs/provisioning/captive_portal_http.h"
#include "libs/provisioning/dns_hijack.h"
}

namespace {
constexpr const char *TAG = "bkx_wifi";

/* Exponential backoff table (ms) indexed by attempt index 0-4 */
constexpr uint32_t BACKOFF_MS[5] = { 1000, 2000, 4000, 8000, 16000 };
}

namespace application {

/* ------------------------------------------------------------------ */
/*  Static ESP-IDF event handlers                                       */
/* ------------------------------------------------------------------ */

void WifiManager::_wifi_event_handler(void *arg, esp_event_base_t /*base*/,
                                       int32_t id, void * /*data*/)
{
    WifiManager *self = static_cast<WifiManager *>(arg);
    wifi_mgr_event_t evt = {};

    if (id == WIFI_EVENT_STA_START) {
        evt.type = WIFI_MGR_EVT_STA_STARTED;
        xQueueSend(self->event_queue_, &evt, 0);
    } else if (id == WIFI_EVENT_STA_DISCONNECTED) {
        evt.type = WIFI_MGR_EVT_DISCONNECTED;
        xQueueSend(self->event_queue_, &evt, 0);
    }
}

void WifiManager::_ip_event_handler(void *arg, esp_event_base_t /*base*/,
                                     int32_t /*id*/, void * /*data*/)
{
    WifiManager *self = static_cast<WifiManager *>(arg);
    wifi_mgr_event_t evt = {};
    evt.type = WIFI_MGR_EVT_GOT_IP;
    xQueueSend(self->event_queue_, &evt, 0);
}

/* ------------------------------------------------------------------ */
/*  Init                                                                */
/* ------------------------------------------------------------------ */

void WifiManager::Init(StatusIndicator& status,
                       mqtt::MqttCredentialStore* mqtt_store)
{
    status_     = &status;
    mqtt_store_ = mqtt_store;
    event_queue_ = xQueueCreate(4, sizeof(wifi_mgr_event_t));

    /* NVS — erase on corruption (first boot or partition mismatch) */
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS partition corrupt, erasing");
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    /* Network interface + event loop (global singletons, safe to call once) */
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    sta_netif_ = esp_netif_create_default_wifi_sta();
    ap_netif_  = esp_netif_create_default_wifi_ap();

    /* Wi-Fi driver */
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    /* Register event handlers — they only post to queue, no state changes */
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                               &_wifi_event_handler, this));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                               &_ip_event_handler, this));

    ESP_LOGI(TAG, "WifiManager initialised");
}

/* ------------------------------------------------------------------ */
/*  Start                                                               */
/* ------------------------------------------------------------------ */

void WifiManager::Start()
{
    xTaskCreate(_task_entry, "wifi_mgr", 4096, this, 5, &task_handle_);
}

WifiState WifiManager::GetState() const
{
    return public_state_.load();
}

void WifiManager::ForceProvisioning()
{
    force_portal_ = true;
}

/* ------------------------------------------------------------------ */
/*  Task                                                                */
/* ------------------------------------------------------------------ */

void WifiManager::_task_entry(void *arg)
{
    static_cast<WifiManager *>(arg)->_run_task();
}

void WifiManager::_run_task()
{
    WifiCredentials creds = {};

    if (!force_portal_ && store_.Load(creds)) {
        creds_loaded_ = true;
        _enter_connecting(creds);
    } else {
        creds_loaded_ = false;
        force_portal_ = false;
        _enter_portal();
    }

    wifi_mgr_event_t evt = {};
    while (true) {
        /* Use a finite timeout while connecting so we can detect hangs */
        TickType_t wait = (state_ == State::kConnecting)
            ? pdMS_TO_TICKS(CONFIG_WIFI_MGR_CONNECT_TIMEOUT_MS)
            : portMAX_DELAY;

        if (xQueueReceive(event_queue_, &evt, wait) == pdFALSE) {
            /* Timeout while connecting counts as a failed attempt */
            if (state_ == State::kConnecting) {
                ESP_LOGW(TAG, "Connect timeout (attempt %d)", connect_attempts_ + 1);
                _on_connect_failure();
            }
        } else {
            _dispatch_event(evt);
        }
    }
}

/* ------------------------------------------------------------------ */
/*  Event dispatcher                                                    */
/* ------------------------------------------------------------------ */

void WifiManager::_dispatch_event(const wifi_mgr_event_t& evt)
{
    switch (state_) {

    case State::kConnecting:
        if (evt.type == WIFI_MGR_EVT_STA_STARTED) {
            /* Fresh wifi_start — now safe to connect */
            ESP_LOGI(TAG, "STA started, connecting to '%s'", current_creds_.ssid);
            esp_wifi_connect();

        } else if (evt.type == WIFI_MGR_EVT_GOT_IP) {
            ESP_LOGI(TAG, "Connected to '%s'", current_creds_.ssid);
            connect_attempts_ = 0;
            state_ = State::kConnected;
            public_state_.store(WifiState::kConnected);
            if (status_) { status_->SetStatus(DeviceStatus::kConnected); }

        } else if (evt.type == WIFI_MGR_EVT_DISCONNECTED) {
            _on_connect_failure();
        }
        break;

    case State::kConnected:
        if (evt.type == WIFI_MGR_EVT_DISCONNECTED) {
            ESP_LOGW(TAG, "Disconnected, reconnecting");
            connect_attempts_ = 0;
            state_ = State::kConnecting;
            public_state_.store(WifiState::kConnecting);
            if (status_) { status_->SetStatus(DeviceStatus::kConnecting); }
            /* WiFi is already started in STA mode — reconnect directly */
            esp_wifi_connect();
        }
        break;

    case State::kPortal:
        if (evt.type == WIFI_MGR_EVT_SAVE_CREDS) {
            WifiCredentials new_creds = {};
            snprintf(new_creds.ssid,     sizeof(new_creds.ssid),     "%s", evt.ssid);
            snprintf(new_creds.password, sizeof(new_creds.password), "%s", evt.password);

            store_.Save(new_creds);

            /* Save MQTT credentials if provided */
            if (mqtt_store_ && evt.mqtt_uri[0] != '\0') {
                mqtt_credentials_t mqtt_creds = {};
                snprintf(mqtt_creds.broker_uri, sizeof(mqtt_creds.broker_uri), "%s", evt.mqtt_uri);
                snprintf(mqtt_creds.username,   sizeof(mqtt_creds.username),   "%s", evt.mqtt_user);
                snprintf(mqtt_creds.password,   sizeof(mqtt_creds.password),   "%s", evt.mqtt_pass);
                mqtt_store_->Save(mqtt_creds);
            }

            creds_loaded_ = true;
            _stop_portal();
            _enter_connecting(new_creds);
        }
        /* All other events ignored while in portal mode */
        break;

    default:
        break;
    }
}

/* ------------------------------------------------------------------ */
/*  State transitions                                                   */
/* ------------------------------------------------------------------ */

void WifiManager::_enter_connecting(const WifiCredentials& creds)
{
    memcpy(&current_creds_, &creds, sizeof(WifiCredentials));
    state_ = State::kConnecting;
    public_state_.store(WifiState::kConnecting);
    if (status_) { status_->SetStatus(DeviceStatus::kConnecting); }

    /* Always do a clean start when switching to STA mode */
    if (wifi_started_) {
        esp_wifi_stop();
        wifi_started_ = false;
    }

    wifi_config_t sta_cfg = {};
    /*
     * wifi_sta_config_t fields are fixed-size uint8_t arrays (32 / 64 bytes).
     * Null-termination is not required by ESP-IDF — strncpy fills the
     * remainder with zeros which is the expected format.
     */
    strncpy(reinterpret_cast<char *>(sta_cfg.sta.ssid),
            creds.ssid, sizeof(sta_cfg.sta.ssid));
    strncpy(reinterpret_cast<char *>(sta_cfg.sta.password),
            creds.password, sizeof(sta_cfg.sta.password));

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta_cfg));
    ESP_ERROR_CHECK(esp_wifi_start());
    wifi_started_ = true;
    /* WIFI_EVENT_STA_START → _dispatch_event → esp_wifi_connect() */
}

void WifiManager::_enter_portal()
{
    state_ = State::kPortal;
    public_state_.store(WifiState::kPortal);
    if (status_) { status_->SetStatus(DeviceStatus::kWifiPortal); }

    /* Mode must be set before esp_wifi_set_config(WIFI_IF_AP, ...) */
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_APSTA));

    _configure_softap();

    if (!wifi_started_) {
        ESP_ERROR_CHECK(esp_wifi_start());
        wifi_started_ = true;
    }

    if (dns_hijack_start() != ESP_OK) {
        ESP_LOGE(TAG, "DNS hijack start failed");
    } else {
        dns_running_ = true;
    }

    if (portal_http_start(&httpd_, event_queue_) != ESP_OK) {
        ESP_LOGE(TAG, "HTTP portal start failed");
        httpd_ = nullptr;
    }

    ESP_LOGI(TAG, "Provisioning portal active");
}

void WifiManager::_stop_portal()
{
    if (httpd_) {
        portal_http_stop(httpd_);
        httpd_ = nullptr;
    }
    if (dns_running_) {
        dns_hijack_stop();
        dns_running_ = false;
    }
    ESP_LOGI(TAG, "Portal stopped");
}

void WifiManager::_on_connect_failure()
{
    connect_attempts_++;
    ESP_LOGW(TAG, "Connect failed (%d/%d)",
             connect_attempts_, CONFIG_WIFI_MGR_MAX_CONNECT_ATTEMPTS);

    if (connect_attempts_ >= CONFIG_WIFI_MGR_MAX_CONNECT_ATTEMPTS) {
        if (wifi_started_) {
            esp_wifi_stop();
            wifi_started_ = false;
        }
        connect_attempts_ = 0;

#if CONFIG_BEKANTX_SLEEP_ENABLED
        if (creds_loaded_) {
            ESP_LOGE(TAG, "Max attempts reached with stored credentials, entering deep sleep");
            _enter_deep_sleep();
            /* Does not return */
        }
#endif
        ESP_LOGE(TAG, "Max attempts reached, switching to provisioning portal");
        _enter_portal();
    } else {
        /* Exponential backoff: 1 s, 2 s, 4 s, 8 s, 16 s */
        int idx = (connect_attempts_ - 1 < 5) ? (connect_attempts_ - 1) : 4;
        uint32_t delay_ms = BACKOFF_MS[idx];
        ESP_LOGI(TAG, "Retrying in %" PRIu32 " ms", delay_ms);
        vTaskDelay(pdMS_TO_TICKS(delay_ms));
        esp_wifi_connect();
    }
}

void WifiManager::_configure_softap()
{
    uint8_t mac[6] = {};
    /* MAC may not be readable before wifi_init — fall back to zeros if needed */
    esp_wifi_get_mac(WIFI_IF_AP, mac);

    wifi_config_t ap_cfg = {};
    snprintf(reinterpret_cast<char *>(ap_cfg.ap.ssid),
             sizeof(ap_cfg.ap.ssid),
             "%s%02X%02X",
             CONFIG_WIFI_MGR_AP_SSID_PREFIX, mac[4], mac[5]);
    ap_cfg.ap.ssid_len     = static_cast<uint8_t>(
        strlen(reinterpret_cast<char *>(ap_cfg.ap.ssid)));
    ap_cfg.ap.channel      = CONFIG_WIFI_MGR_AP_CHANNEL;
    ap_cfg.ap.authmode     = WIFI_AUTH_OPEN;
    ap_cfg.ap.max_connection = CONFIG_WIFI_MGR_AP_MAX_CONN;

    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_cfg));
    ESP_LOGI(TAG, "SoftAP SSID: '%s'", ap_cfg.ap.ssid);
}

void WifiManager::_enter_deep_sleep()
{
#if CONFIG_BEKANTX_SLEEP_ENABLED
    if (status_) { status_->SetStatus(DeviceStatus::kSleep); }
    /* Brief delay so LED state change is visible before power-down */
    vTaskDelay(pdMS_TO_TICKS(500));

    const int wake_gpio  = CONFIG_BEKANTX_SLEEP_WAKE_GPIO;
    const int wake_level = CONFIG_BEKANTX_SLEEP_WAKE_LEVEL;

    ESP_LOGI(TAG, "Configuring GPIO %d (level %d) as deep-sleep wake source",
             wake_gpio, wake_level);

#if CONFIG_IDF_TARGET_ESP32C3 || CONFIG_IDF_TARGET_ESP32C6 || CONFIG_IDF_TARGET_ESP32H2
    /* C3/C6/H2: GPIO wakeup */
    const uint64_t pin_mask = (1ULL << wake_gpio);
    esp_deep_sleep_enable_gpio_wakeup(pin_mask,
        wake_level ? ESP_GPIO_WAKEUP_GPIO_HIGH : ESP_GPIO_WAKEUP_GPIO_LOW);
#else
    /* ESP32/S2/S3: EXT0 wakeup */
    esp_sleep_enable_ext0_wakeup((gpio_num_t)wake_gpio, wake_level);
#endif

    ESP_LOGI(TAG, "Entering deep sleep — press button to wake");
    esp_deep_sleep_start();
    /* Does not return.  On wake the ESP reboots through app_main. */
#endif
}

}  // namespace application
