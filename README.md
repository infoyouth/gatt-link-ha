# GATT Link

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/infoyouth/gatt-link-ha)
[![GitHub release](https://img.shields.io/github/v/release/infoyouth/gatt-link-ha)](https://github.com/infoyouth/gatt-link-ha/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

GATT Link integrates Nordic Thingy devices and compatible Bluetooth SIG environmental sensors with Home Assistant over Bluetooth. It exposes live sensor readings such as temperature, humidity, pressure, eCO2, TVOC, and battery state as Home Assistant entities.

## Quick links

[![Open in Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=gatt_link)
[![Add Integration via HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=infoyouth/gatt-link-ha)

* **Source & issues:** [GitHub repository](https://github.com/infoyouth/gatt-link-ha) | [Report a bug](https://github.com/infoyouth/gatt-link-ha/issues)

## Installation

1. Install GATT Link from HACS.
2. Restart Home Assistant.
3. Ensure Bluetooth is available through a local adapter or a Home Assistant Bluetooth proxy.
4. Open the setup link above or go to Settings > Devices & services and add the integration.
5. Select a nearby supported Bluetooth device.

The setup flow does not require a password, token, or network address. To replace the selected device later, use the integration's **Reconfigure** action.

## Supported devices and sensors

Supported devices include:

- Nordic Thingy:52 and Thingy:53 devices advertising the Thingy environment service
- Connectable Bluetooth SIG Environmental Sensing devices that advertise service 0x181A and expose supported characteristics

Current entities include:

| Entity | Unit / type | Default |
| --- | --- | --- |
| Temperature | °C | Enabled |
| Humidity | % | Enabled |
| Pressure | hPa | Enabled |
| eCO2 | ppm | Enabled |
| TVOC | ppb | Enabled |
| Battery | % | Enabled |
| Illuminance (raw) | Device clear-channel reading; not lux | Disabled |

The raw illuminance value is a device reading and not a calibrated lux value. It is disabled by default; enable it from the entity registry if you need that data.

## Connection modes

The default mode is Push notifications. This keeps the device connected and updates entities when notifications arrive.

Poll and disconnect is also available for lower proxy load. It reads data on a configured interval and then disconnects. The default interval is 300 seconds; it can be changed in the integration's options (minimum 1 second). This is useful when a Bluetooth proxy has limited connection slots.

If an ESP32 proxy cannot connect because its connection slots may be in use, the integration raises a repair issue and suggests switching the device to Poll and disconnect or freeing a connection slot. The issue clears after a successful connection.

## Troubleshooting

- Device not offered for setup: confirm it is powered, nearby, connectable, and advertising a supported service.
- Connection fails through an ESP32 proxy: free a connection slot or switch the device to Poll and disconnect.
- Values update less often than expected: check the selected connection mode and polling interval.
- Entities are unavailable: confirm Bluetooth range, adapter availability, and proxy reachability.
- Need diagnostics: use the integration diagnostics export; addresses and IDs are automatically redacted.

## Contributor documentation

For implementation notes and integration architecture details, see [docs/README.md](docs/README.md).

## Removing GATT Link

1. Open Settings > Devices & services.
2. Remove the GATT Link entry for each configured device.
3. If installed through HACS, uninstall the integration there.
4. Restart Home Assistant to complete cleanup.
