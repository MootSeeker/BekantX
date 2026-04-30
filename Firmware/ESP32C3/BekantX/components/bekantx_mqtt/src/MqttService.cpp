#include "mqtt/MqttService.hpp"

#include <cstring>
#include <cstdio>

extern "C" {
#include "esp_log.h"
#include "esp_event.h"
#include "esp_wifi.h"
#include "mqtt_client.h"
}

namespace {
constexpr const char* TAG = "bkx_mqtt";
}

namespace mqtt {

/* ------------------------------------------------------------------ */
/*  Static event handlers (post to service queue only)                  */
/* ------------------------------------------------------------------ */

void MqttService::_wifi_event_handler(void* arg, esp_event_base_t /*base*/,
                                       int32_t id, void* /*data*/)
{
    MqttService* self = static_cast<MqttService*>(arg);
    if (id == WIFI_EVENT_STA_DISCONNECTED) {
        SvcEventMsg msg = {};
        msg.type = SvcEvent::kWifiDisconnected;
        xQueueSend(self->svc_queue_, &msg, 0);
    }
}

void MqttService::_ip_event_handler(void* arg, esp_event_base_t /*base*/,
                                     int32_t /*id*/, void* /*data*/)
{
    MqttService* self = static_cast<MqttService*>(arg);
    SvcEventMsg msg = {};
    msg.type = SvcEvent::kGotIp;
    xQueueSend(self->svc_queue_, &msg, 0);
}

void MqttService::_mqtt_event_handler(void* arg, esp_event_base_t /*base*/,
                                       int32_t /*id*/, void* data)
{
    MqttService* self = static_cast<MqttService*>(arg);
    esp_mqtt_event_handle_t event = static_cast<esp_mqtt_event_handle_t>(data);

    SvcEventMsg msg = {};

    switch (event->event_id) {
    case MQTT_EVENT_CONNECTED:
        msg.type = SvcEvent::kMqttConnected;
        xQueueSend(self->svc_queue_, &msg, 0);
        break;

    case MQTT_EVENT_DISCONNECTED:
        msg.type = SvcEvent::kMqttDisconnected;
        xQueueSend(self->svc_queue_, &msg, 0);
        break;

    case MQTT_EVENT_DATA:
        /* Skip continuation fragments of multi-part messages */
        if (event->current_data_offset > 0) {
            break;
        }
        if (event->total_data_len > (int)(sizeof(msg.data) - 1)) {
            ESP_LOGW(TAG, "MQTT payload truncated (%d > %zu bytes)",
                     event->total_data_len, sizeof(msg.data) - 1);
        }
        msg.type = SvcEvent::kMqttData;
        /* Copy topic */
        if (event->topic && event->topic_len > 0) {
            size_t tlen = (size_t)event->topic_len;
            if (tlen >= sizeof(msg.topic)) tlen = sizeof(msg.topic) - 1;
            memcpy(msg.topic, event->topic, tlen);
            msg.topic[tlen] = '\0';
        }
        /* Copy payload */
        if (event->data && event->data_len > 0) {
            size_t dlen = (size_t)event->data_len;
            if (dlen >= sizeof(msg.data)) dlen = sizeof(msg.data) - 1;
            memcpy(msg.data, event->data, dlen);
            msg.data[dlen] = '\0';
            msg.data_len = (int)dlen;
        }
        xQueueSend(self->svc_queue_, &msg, 0);
        break;

    case MQTT_EVENT_ERROR:
        msg.type = SvcEvent::kMqttError;
        xQueueSend(self->svc_queue_, &msg, 0);
        break;

    default:
        break;
    }
}

/* ------------------------------------------------------------------ */
/*  Init / Start / Stop                                                 */
/* ------------------------------------------------------------------ */

void MqttService::Init(MqttCredentialStore& store)
{
    cred_store_ = &store;

    svc_queue_ = xQueueCreate(16, sizeof(SvcEventMsg));
    cmd_queue_ = xQueueCreate(CONFIG_MQTT_CMD_QUEUE_DEPTH, sizeof(desk_command_t));

    cmd_handler_.Init(cmd_queue_);

    /* Load credentials from NVS, fall back to Kconfig defaults */
    if (!cred_store_->Load(credentials_)) {
        ESP_LOGI(TAG, "No MQTT credentials in NVS, using Kconfig defaults");
        snprintf(credentials_.broker_uri, sizeof(credentials_.broker_uri),
                 "%s", CONFIG_MQTT_BROKER_URI_DEFAULT);
        credentials_.username[0] = '\0';
        credentials_.password[0] = '\0';
    }

    _build_topics();

    ESP_LOGD(TAG, "MqttService initialised (broker: %s)", credentials_.broker_uri);
    ESP_LOGI(TAG, "MqttService initialised");
}

void MqttService::Start()
{
    /* Register WiFi/IP event handlers — separate from WifiManager's handlers */
    esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_STA_DISCONNECTED,
                               &_wifi_event_handler, this);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                               &_ip_event_handler, this);

    xTaskCreate(_task_entry, "mqtt_svc", 4096, this, 4, &task_handle_);
}

void MqttService::Stop()
{
    _disconnect_mqtt();

    esp_event_handler_unregister(WIFI_EVENT, WIFI_EVENT_STA_DISCONNECTED,
                                 &_wifi_event_handler);
    esp_event_handler_unregister(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                 &_ip_event_handler);
}

MqttState MqttService::GetState() const
{
    return public_state_.load();
}

QueueHandle_t MqttService::GetCommandQueue() const
{
    return cmd_queue_;
}

/* ------------------------------------------------------------------ */
/*  Task                                                                */
/* ------------------------------------------------------------------ */

void MqttService::_task_entry(void* arg)
{
    static_cast<MqttService*>(arg)->_run_task();
}

void MqttService::_run_task()
{
    SvcEventMsg msg = {};

    while (true) {
        if (xQueueReceive(svc_queue_, &msg, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        switch (msg.type) {
        case SvcEvent::kGotIp:
            ESP_LOGI(TAG, "Got IP, starting MQTT client");
            _connect_mqtt();
            break;

        case SvcEvent::kWifiDisconnected:
            ESP_LOGW(TAG, "WiFi disconnected, stopping MQTT client");
            _disconnect_mqtt();
            break;

        case SvcEvent::kMqttConnected:
            _on_mqtt_connected();
            break;

        case SvcEvent::kMqttDisconnected:
            ESP_LOGW(TAG, "MQTT disconnected");
            public_state_.store(MqttState::kDisconnected);
            break;

        case SvcEvent::kMqttData:
            _on_mqtt_data(msg.topic, msg.data, msg.data_len);
            break;

        case SvcEvent::kMqttError:
            ESP_LOGE(TAG, "MQTT error event");
            public_state_.store(MqttState::kError);
            break;
        }
    }
}

/* ------------------------------------------------------------------ */
/*  MQTT client management                                              */
/* ------------------------------------------------------------------ */

void MqttService::_connect_mqtt()
{
    if (mqtt_started_) {
        /* Already running — reconnect will happen automatically */
        return;
    }

    if (credentials_.broker_uri[0] == '\0') {
        ESP_LOGW(TAG, "No broker URI configured, skipping MQTT");
        return;
    }

    esp_mqtt_client_config_t mqtt_cfg = {};
    mqtt_cfg.broker.address.uri = credentials_.broker_uri;
    mqtt_cfg.credentials.username = credentials_.username[0] ? credentials_.username : nullptr;
    mqtt_cfg.credentials.authentication.password = credentials_.password[0] ? credentials_.password : nullptr;
    mqtt_cfg.session.keepalive = CONFIG_MQTT_KEEPALIVE_SEC;

    /* LWT: availability topic → "offline" */
    mqtt_cfg.session.last_will.topic   = topic_available_;
    mqtt_cfg.session.last_will.msg     = "offline";
    mqtt_cfg.session.last_will.msg_len = 7;
    mqtt_cfg.session.last_will.qos     = CONFIG_MQTT_QOS;
    mqtt_cfg.session.last_will.retain  = 1;

    mqtt_client_ = esp_mqtt_client_init(&mqtt_cfg);
    if (!mqtt_client_) {
        ESP_LOGE(TAG, "Failed to init MQTT client");
        public_state_.store(MqttState::kError);
        return;
    }

    esp_mqtt_client_register_event(mqtt_client_,
                                    (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID,
                                    &_mqtt_event_handler, this);

    esp_err_t err = esp_mqtt_client_start(mqtt_client_);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start MQTT client: %s", esp_err_to_name(err));
        esp_mqtt_client_destroy(mqtt_client_);
        mqtt_client_ = nullptr;
        public_state_.store(MqttState::kError);
        return;
    }

    mqtt_started_ = true;
    public_state_.store(MqttState::kConnecting);
    ESP_LOGI(TAG, "MQTT client started, connecting to %s", credentials_.broker_uri);
}

void MqttService::_disconnect_mqtt()
{
    if (!mqtt_started_) {
        return;
    }
    /* Clear flag first to guard against re-entry from another context */
    mqtt_started_ = false;
    if (mqtt_client_) {
        esp_mqtt_client_stop(mqtt_client_);
        esp_mqtt_client_destroy(mqtt_client_);
        mqtt_client_ = nullptr;
    }
    public_state_.store(MqttState::kDisconnected);
}

void MqttService::_on_mqtt_connected()
{
    ESP_LOGI(TAG, "MQTT connected to broker");
    public_state_.store(MqttState::kConnected);

    /* Subscribe to command topic */
    int msg_id = esp_mqtt_client_subscribe(mqtt_client_, topic_command_, CONFIG_MQTT_QOS);
    ESP_LOGI(TAG, "Subscribed to '%s' (msg_id=%d)", topic_command_, msg_id);

    /* Publish "online" to availability topic (retained) */
    esp_mqtt_client_publish(mqtt_client_, topic_available_, "online", 0,
                             CONFIG_MQTT_QOS, 1);

    /* Initialise state publisher and publish default state */
    state_pub_.Init(mqtt_client_, topic_state_, CONFIG_MQTT_QOS);
    state_pub_.PublishDefaultState();

    /* Publish HA discovery if enabled */
#if CONFIG_MQTT_HA_DISCOVERY_ENABLED
    discovery_.PublishDiscoveryConfig(mqtt_client_,
                                      CONFIG_MQTT_DEVICE_ID,
                                      CONFIG_MQTT_TOPIC_PREFIX,
                                      CONFIG_MQTT_HA_DISCOVERY_PREFIX,
                                      CONFIG_MQTT_QOS);
#endif
}

void MqttService::_on_mqtt_data(const char* topic, const char* data, int data_len)
{
    /* Only handle messages on the command topic */
    if (topic && strcmp(topic, topic_command_) == 0) {
        cmd_handler_.HandleMessage(topic, data, data_len);
    }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                             */
/* ------------------------------------------------------------------ */

void MqttService::_build_topics()
{
    snprintf(topic_command_,   sizeof(topic_command_),
             "%s/%s/command",   CONFIG_MQTT_TOPIC_PREFIX, CONFIG_MQTT_DEVICE_ID);
    snprintf(topic_state_,     sizeof(topic_state_),
             "%s/%s/state",     CONFIG_MQTT_TOPIC_PREFIX, CONFIG_MQTT_DEVICE_ID);
    snprintf(topic_available_, sizeof(topic_available_),
             "%s/%s/available", CONFIG_MQTT_TOPIC_PREFIX, CONFIG_MQTT_DEVICE_ID);
}

}  // namespace mqtt
