"""Coordinate GATT Link BLE updates with Home Assistant."""

import logging
from datetime import timedelta
from typing import override

from bleak.backends.device import BLEDevice
from gatt_link_ble import ConnectionMode, GattDeviceState, GattLinkClient, GattLinkError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_ADDRESS,
    CONF_CONNECTION_MODE,
    CONF_SCAN_INTERVAL,
    DEFAULT_CONNECTION_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GattLinkCoordinator(DataUpdateCoordinator[GattDeviceState]):
    """Fetch sensor state and manage the push connection lifecycle."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator from a config entry."""
        address = config_entry.data.get(CONF_ADDRESS)
        if not isinstance(address, str):
            raise ConfigEntryError("The configured Bluetooth address is invalid")
        self.address = format_mac(address)
        self.device_name = config_entry.title

        try:
            self.connection_mode = ConnectionMode(
                config_entry.options.get(CONF_CONNECTION_MODE, DEFAULT_CONNECTION_MODE)
            )
        except ValueError as err:
            raise ConfigEntryError("The configured connection mode is invalid") from err

        self._scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        if type(self._scan_interval) is not int or self._scan_interval < 1:
            raise ConfigEntryError("The configured polling interval is invalid")

        self._client: GattLinkClient | None = None
        self._last_ble_device: BLEDevice | None = None
        self._push_started = False

        update_interval = (
            timedelta(seconds=self._scan_interval)
            if self.connection_mode is ConnectionMode.POLL_AND_DISCONNECT
            else None
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
            always_update=False,
        )

    @override
    async def _async_update_data(self) -> GattDeviceState:
        """Connect to the device and return its latest sensor state."""
        if self.connection_mode is ConnectionMode.POLL_AND_DISCONNECT:
            ble_device = self._get_live_ble_device()
            if ble_device is None:
                raise UpdateFailed("Bluetooth device is not currently available")

            client = GattLinkClient(
                ble_device,
                mode=ConnectionMode.POLL_AND_DISCONNECT,
                name=self.device_name,
            )
            try:
                return await client.poll()
            except GattLinkError as err:
                raise UpdateFailed(
                    "Unable to read data from the Bluetooth device"
                ) from err

        if self._client is None:
            ble_device = self._get_live_ble_device()
            if ble_device is None:
                raise UpdateFailed("Bluetooth device is not currently available")
            self._last_ble_device = ble_device

            client = GattLinkClient(
                self._get_ble_device_for_reconnect,
                mode=ConnectionMode.PUSH,
                name=self.device_name,
                state_callback=self._handle_state_update,
                disconnect_callback=self._handle_disconnect,
            )
            try:
                await client.start()
            except GattLinkError as err:
                raise UpdateFailed("Unable to connect to the Bluetooth device") from err
            self._client = client
            self._push_started = True

        return self._client.state

    @callback
    def _get_live_ble_device(self) -> BLEDevice | None:
        """Return Home Assistant's current BLE device for this address."""
        return bluetooth.async_ble_device_from_address(
            self.hass,
            self.address,
            connectable=True,
        )

    @callback
    def _get_ble_device_for_reconnect(self) -> BLEDevice:
        """Refresh the cached BLE device when Home Assistant has a newer one."""
        if (ble_device := self._get_live_ble_device()) is not None:
            self._last_ble_device = ble_device
        if self._last_ble_device is None:
            raise UpdateFailed("Bluetooth device is not currently available")
        return self._last_ble_device

    @callback
    def _handle_state_update(self, state: GattDeviceState) -> None:
        """Publish state updates after the initial connection has started."""
        if self._push_started:
            self.async_set_updated_data(state)

    @callback
    def _handle_disconnect(self) -> None:
        """Mark push entities unavailable while the client reconnects."""
        self.async_set_update_error(UpdateFailed("Bluetooth connection was lost"))

    async def async_shutdown(self) -> None:
        """Stop the BLE client and coordinator refresh tasks."""
        try:
            if self._client is not None:
                await self._client.stop()
        finally:
            await super().async_shutdown()


type GattLinkConfigEntry = ConfigEntry[GattLinkCoordinator]
