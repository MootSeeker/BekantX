#pragma once

#include <cstddef>

#include "mqtt/mqtt_types.h"

namespace mqtt {

/**
 * @brief NVS-backed store for MQTT broker credentials.
 *
 * Follows the same pattern as WifiCredentialStore.
 * Namespace is set via CONFIG_MQTT_NVS_NAMESPACE.
 */
class MqttCredentialStore {
public:
    /** @brief Load credentials from NVS.  Returns true if a broker URI was found. */
    bool Load(mqtt_credentials_t& out);

    /** @brief Save credentials to NVS (atomic commit). */
    bool Save(const mqtt_credentials_t& creds);

    /** @brief Erase stored MQTT credentials. */
    void Clear();
};

}  // namespace mqtt
