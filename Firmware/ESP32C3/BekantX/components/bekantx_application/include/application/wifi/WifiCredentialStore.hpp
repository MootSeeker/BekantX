#pragma once

#include <cstddef>

namespace application {

/**
 * @brief Stores SSID (max 32 chars) and password (max 64 chars), null-terminated.
 */
struct WifiCredentials {
    char ssid[33];
    char password[65];
};

/**
 * @brief NVS-backed store for Wi-Fi credentials.
 *
 * Credentials are kept in a dedicated NVS namespace and are never written
 * to any log output.
 */
class WifiCredentialStore {
public:
    /**
     * @brief Load stored credentials.
     * @param out  Populated on success.
     * @return true if valid credentials were found.
     */
    bool Load(WifiCredentials& out);

    /**
     * @brief Persist credentials to NVS.
     * @return true on success.
     */
    bool Save(const WifiCredentials& creds);

    /** @brief Erase stored credentials from NVS. */
    void Clear();
};

}  // namespace application
