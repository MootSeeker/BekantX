#include "libs/provisioning/dns_hijack.h"

#include <string.h>
#include <stdlib.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"

static const char *TAG = "bkx_dns";

#define DNS_PORT      53
#define DNS_BUF_SIZE  512
#define PORTAL_IP_A   192
#define PORTAL_IP_B   168
#define PORTAL_IP_C   4
#define PORTAL_IP_D   1

static TaskHandle_t     s_task_handle = NULL;
static volatile bool    s_running     = false;
static int              s_sock        = -1;

/* ------------------------------------------------------------------ */
/*  DNS response builder                                                */
/* ------------------------------------------------------------------ */

/**
 * @brief Build a DNS A-record response that always resolves to the portal IP.
 *
 * @param query      Raw DNS query bytes.
 * @param query_len  Length of the query.
 * @param resp       Output buffer (must be at least query_len + 16 bytes).
 * @param resp_size  Size of the output buffer.
 * @return Length of the response, or -1 on error.
 */
static int _build_dns_response(const uint8_t *query, int query_len,
                                uint8_t *resp, int resp_size)
{
    /* Reject too-short queries and ensure response fits (form avoids int overflow) */
    if (query_len < 12 || query_len > resp_size - 16) {
        return -1;
    }

    /* Copy the query as the base of the response (retains ID, QDCOUNT, question) */
    memcpy(resp, query, (size_t)query_len);

    /* Flags: QR=1 (response), Opcode=0, AA=1, TC=0, RD from query, RA=1, RCODE=0 */
    resp[2] = (uint8_t)((query[2] & 0x01u) | 0x84u);
    resp[3] = 0x80u;

    /* ANCOUNT = 1, NSCOUNT = 0, ARCOUNT = 0 */
    resp[6] = 0x00u; resp[7] = 0x01u;
    resp[8] = 0x00u; resp[9] = 0x00u;
    resp[10] = 0x00u; resp[11] = 0x00u;

    int pos = query_len;

    /* Answer: name pointer back to the question section (offset 12 = 0x0C) */
    resp[pos++] = 0xC0u;
    resp[pos++] = 0x0Cu;
    /* Type A */
    resp[pos++] = 0x00u; resp[pos++] = 0x01u;
    /* Class IN */
    resp[pos++] = 0x00u; resp[pos++] = 0x01u;
    /* TTL: 60 seconds */
    resp[pos++] = 0x00u; resp[pos++] = 0x00u;
    resp[pos++] = 0x00u; resp[pos++] = 0x3Cu;
    /* RDLENGTH: 4 */
    resp[pos++] = 0x00u; resp[pos++] = 0x04u;
    /* RDATA: portal IPv4 address */
    resp[pos++] = PORTAL_IP_A;
    resp[pos++] = PORTAL_IP_B;
    resp[pos++] = PORTAL_IP_C;
    resp[pos++] = PORTAL_IP_D;

    return pos;
}

/* ------------------------------------------------------------------ */
/*  Task                                                                */
/* ------------------------------------------------------------------ */

static void dns_task(void *arg)
{
    (void)arg;

    struct sockaddr_in server_addr = {
        .sin_family      = AF_INET,
        .sin_addr.s_addr = htonl(INADDR_ANY),
        .sin_port        = htons(DNS_PORT),
        .sin_len         = sizeof(struct sockaddr_in),
    };

    s_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (s_sock < 0) {
        ESP_LOGE(TAG, "Failed to create socket");
        vTaskDelete(NULL);
        return;
    }

    /* 1-second receive timeout so the task can check s_running */
    struct timeval tv = { .tv_sec = 1, .tv_usec = 0 };
    setsockopt(s_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    int yes = 1;
    setsockopt(s_sock, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));

    if (bind(s_sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        ESP_LOGE(TAG, "Failed to bind DNS socket");
        close(s_sock);
        s_sock = -1;
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(TAG, "DNS hijack listening on port %d", DNS_PORT);

    uint8_t buf[DNS_BUF_SIZE];
    uint8_t resp[DNS_BUF_SIZE];

    while (s_running) {
        struct sockaddr_in client_addr;
        socklen_t addr_len = sizeof(client_addr);

        int len = recvfrom(s_sock, buf, sizeof(buf), 0,
                           (struct sockaddr *)&client_addr, &addr_len);

        if (len < 0) {
            /* EAGAIN / timeout — normal, loop to check s_running */
            continue;
        }

        int resp_len = _build_dns_response(buf, len, resp, (int)sizeof(resp));
        if (resp_len > 0) {
            sendto(s_sock, resp, (size_t)resp_len, 0,
                   (struct sockaddr *)&client_addr, addr_len);
        }
    }

    close(s_sock);
    s_sock = -1;
    ESP_LOGI(TAG, "DNS hijack stopped");
    vTaskDelete(NULL);
}

/* ------------------------------------------------------------------ */
/*  Public API                                                          */
/* ------------------------------------------------------------------ */

esp_err_t dns_hijack_start(void)
{
    if (s_running) {
        return ESP_OK; /* already running */
    }
    s_running = true;
    BaseType_t ret = xTaskCreate(dns_task, "dns_hijack", 2048, NULL, 4, &s_task_handle);
    if (ret != pdPASS) {
        s_running = false;
        ESP_LOGE(TAG, "Failed to create DNS task");
        return ESP_FAIL;
    }
    return ESP_OK;
}

void dns_hijack_stop(void)
{
    s_running = false;
    /* Task will exit on its own after the next receive timeout (≤1 s) */
    s_task_handle = NULL;
}
