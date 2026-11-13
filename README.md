# GATT Link

GATT Link integrates supported Nordic Thingy devices and Bluetooth SIG
Environmental Sensing devices with Home Assistant over Bluetooth.

Add the repository to HACS as a custom integration, install **GATT Link**, and
restart Home Assistant. Nearby supported devices appear in **Settings >
Devices & services** for setup. Bluetooth discovery works with a local adapter
or a Bluetooth proxy.

The integration uses push notifications by default. You can choose polling and
disconnecting, with a configurable polling interval, in the integration's
options. Depending on the device, it creates temperature, humidity, pressure,
eCO2, TVOC, and battery sensors; only sensors supported by the device are added.
Downloaded diagnostics include device metadata and sensor data, with Bluetooth
addresses and config-entry unique IDs redacted.
