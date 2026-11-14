# GATT Link

GATT Link integrates Nordic Thingy:52 and Thingy:53 devices and compatible
Bluetooth SIG Environmental Sensing devices with Home Assistant over Bluetooth.
It exposes sensor readings from supported GATT characteristics as Home
Assistant entities.

## Installation and setup

1. Install **GATT Link** from HACS as a custom integration and restart Home
   Assistant.
2. Ensure Bluetooth is available through a local adapter or a Home Assistant
   Bluetooth proxy, and bring a supported device nearby.
3. Open **Settings > Devices & services** and select the discovered GATT Link
   device. If needed, add the integration manually and select a nearby device
   from the list.

The setup flow asks you to select the Bluetooth device. It does not ask for a
password, token, or network address. To replace the selected device later, use
the integration's **Reconfigure** action.

## Supported devices and sensors

Supported devices are:

- Nordic Thingy:52 and Thingy:53 devices advertising the Thingy environment
  service.
- Connectable Bluetooth SIG Environmental Sensing devices that advertise
  service `0x181A` and expose characteristics supported by the BLE library.

Devices that do not advertise either supported service, are not connectable, or
do not expose supported characteristics are not set up. GATT Link currently
creates these entities when the corresponding characteristic is present:

| Entity | Unit / type | Default |
| --- | --- | --- |
| Temperature | °C | Enabled |
| Humidity | % | Enabled |
| Pressure | hPa | Enabled |
| eCO2 | ppm | Enabled |
| TVOC | ppb | Enabled |
| Battery | % | Enabled |
| Illuminance (raw) | Device clear-channel reading; not lux | Disabled |

The raw illuminance reading is a Thingy color-sensor clear-channel count, not a
calibrated lux value. It is disabled by default; enable it from the entity
registry if you need that raw measurement. Entities for characteristics absent
from the device are not created.

The `gatt-link-ble` dependency is an open-source package published on PyPI. It
handles BLE GATT connection and sensor parsing; this integration handles Home
Assistant discovery, config entries, and entities. See
[gatt-link-ble on GitHub](https://github.com/infoyouth/gatt-link-ble) and
[PyPI](https://pypi.org/project/gatt-link-ble/).

## Connection modes and data updates

The default **Push notifications** mode maintains a connection and updates
entities when the device sends notifications. Use it when prompt updates are
important and proxy connection slots are available.

**Poll and disconnect** connects for a read and then disconnects. Its default
interval is **300 seconds**. To change it, open the integration's **Options**,
choose the connection mode, and set the polling interval in whole seconds
(minimum 1 second). Polling reduces the time a device occupies a proxy slot,
but values update only on each poll.

Bluetooth proxies have a limited number of simultaneous connection slots;
ESP32 proxies commonly have three. If a device cannot connect, free a proxy
slot or switch it to **Poll and disconnect**. GATT Link raises a Repair issue
for a recognized ESP32 connection-slot exhaustion error and clears that issue
after a successful connection.

## Automation example

GATT Link does not provide custom Home Assistant actions, conditions, or
triggers. Use standard Home Assistant state triggers with its sensor entities.
For example, replace the entity ID below with the temperature entity created
for your device:

```yaml
automation:
  - alias: Notify when the GATT Link temperature is high
    triggers:
      - trigger: numeric_state
        entity_id: sensor.thingy_temperature
        above: 30
    actions:
      - action: persistent_notification.create
        data:
          title: GATT Link temperature
          message: The temperature is above 30 °C.
```

Typical uses include monitoring room conditions, tracking a Thingy environment
sensor during a project, and including local BLE readings in dashboards or
automations.

## Troubleshooting

- **The device is not offered for setup:** Check that it is connectable, nearby,
  and advertising the Thingy environment or Environmental Sensing service.
  Confirm Home Assistant can see it through its Bluetooth adapter or proxy.
- **Connection fails through an ESP32 proxy:** Another integration or device may
  be using its limited connection slots. Free a slot or set this device to
  **Poll and disconnect**. Check **Settings > System > Repairs** for the
  proxy-slot issue.
- **Values update less often than expected:** Check the selected connection
  mode. Push updates on notifications; polling updates at its configured
  interval.
- **Entities are unavailable:** Check that the device is powered, within
  Bluetooth range, and reachable through the selected adapter or proxy.
- **Need help diagnosing an issue:** Download diagnostics from the integration
  page and attach them to a report. Bluetooth addresses and config-entry unique
  IDs are redacted.

## Removing GATT Link

1. In **Settings > Devices & services**, open GATT Link and choose **Delete**
   for each configured device.
2. If installed through HACS, uninstall GATT Link there.
3. Restart Home Assistant to complete removal.
