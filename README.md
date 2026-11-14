# GATT Link

GATT Link integrates Nordic Thingy:52 and Thingy:53 devices, as well as
compatible Bluetooth SIG Environmental Sensing devices, with Home Assistant
over Bluetooth. A SIG sensor must advertise the Environmental Sensing service
and expose characteristics supported by the integration.

## Installation

Add this repository to HACS as a custom integration, install **GATT Link**, and
restart Home Assistant. Keep the device near a Bluetooth adapter or Bluetooth
proxy. When a supported, connectable device is discovered, add it from
**Settings > Devices & services**. If it is already nearby, it can also be
selected through the integration's manual setup flow.

## Connection modes and Bluetooth proxies

The integration uses **Push notifications** by default. Push keeps a Bluetooth
connection open to receive sensor updates promptly. Bluetooth proxies have a
limited number of simultaneous connection slots; ESP32 proxies commonly have
three. If other integrations or devices use those slots, persistent push
connections may prevent a device from connecting.

For setups with several devices sharing a proxy, open the integration's options
and select **Poll and disconnect**. It connects only for each read, then
disconnects, reducing the time it occupies a proxy slot. The default polling
interval is 300 seconds and can be changed in the options. Polling means sensor
values update on that schedule rather than immediately.

## Sensors and diagnostics

Depending on the device's supported characteristics, GATT Link creates
temperature, humidity, pressure, eCO2, TVOC, and battery sensors. Unsupported
sensors are not added. Downloaded diagnostics include device metadata and
sensor data, with Bluetooth addresses and config-entry unique IDs redacted.
