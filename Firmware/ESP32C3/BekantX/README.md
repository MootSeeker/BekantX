# BekantX ESP32-C3 firmware (secondary controller)

ESP-IDF C++ firmware of the optional network coprocessor of [BekantX](../../../README.md). It connects the desk
to Wi-Fi and Home Assistant. Desk motion and every safety rule stay on the STM32 primary controller; this
firmware only forwards requests, and the primary validates them (see [`Docs/architecture.md`](../../../Docs/architecture.md)).

## Features

- Wi-Fi manager: stored credentials, retries, captive-portal provisioning with DNS redirect as fallback
- MQTT client with command queue and state publishing
- Home Assistant MQTT discovery (retained config, switchable in Kconfig)
- Status LED (WS2812/SK6812) with animations
- Deep-sleep options

Planned: the SPI mailbox link to the STM32 ([`Docs/inter-controller-protocol.md`](../../../Docs/inter-controller-protocol.md)).
The development plan is in [`APPLICATION_PLAN.md`](APPLICATION_PLAN.md).

## Layout

```
main/main.c                       thin C entry point, starts the C++ application
components/bekantx_application    application, Wi-Fi manager, status indicator
components/bekantx_mqtt           MQTT service, discovery, command handler, state publisher
components/bekantx_drivers        LED driver and animator (WS2812 transport)
components/bekantx_libs           provisioning (captive portal, DNS hijack)
components/bekantx_utils          C/C++ bridge
```

## Build

Requires ESP-IDF (the dev container in `.devcontainer/` provides one).

```bash
idf.py set-target esp32c3     # the board target; development ran on an ESP32-S2-Saola so far
idf.py menuconfig             # "BekantX WiFi Manager", "BekantX MQTT Service", "BekantX Deep Sleep"
idf.py build flash monitor
```

Defaults live in `sdkconfig.defaults`. Never commit an `sdkconfig` with credentials: it is ignored on purpose,
and Wi-Fi and MQTT credentials are entered at runtime through the captive portal and stored in NVS.

> [!NOTE]
> On the controller board the status LED is on **GPIO8** (`LED_DIN`). `Application.cpp` still uses GPIO10 from
> the dev board, which is `FSPI_NCS` on the real board. This is an open point in the project notes.

## License

[GPL-3.0-or-later](../../../LICENSES/GPL-3.0-or-later.txt)
