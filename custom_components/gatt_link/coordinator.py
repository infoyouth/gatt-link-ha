"""Coordinate GATT Link BLE updates with Home Assistant."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import override

from bleak.backends.device import BLEDevice
from gatt_link_ble import (
    ConnectionMode,
    GattConnectionError,
    GattDeviceState,
    GattLinkClient,
    GattLinkError,
)
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ADDRESS,
    CONF_CONNECTION_MODE,
    CONF_SCAN_INTERVAL,
    DEFAULT_CONNECTION_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .repairs import (
    async_delete_proxy_slots_issue,
    async_handle_connection_error,
)

_LOGGER = logging.getLogger(__name__)


class GattLinkCoordinator(TimestampDataUpdateCoordinator[GattDeviceState]):
    """Fetch sensor state and manage the push connection lifecycle."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator from a config entry."""
        self._config_entry = config_entry
        address = config_entry.data.get(CONF_ADDRESS)
        if not isinstance(address, str):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_address",
            )
        self.address = format_mac(address)
        self.device_name = config_entry.title

        try:
            self.connection_mode = ConnectionMode(
                config_entry.options.get(CONF_CONNECTION_MODE, DEFAULT_CONNECTION_MODE)
            )
        except ValueError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_connection_mode",
            ) from err

        self._scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        if type(self._scan_interval) is not int or self._scan_interval < 1:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_scan_interval",
            )

        self._client: GattLinkClient | None = None
        self._last_ble_device: BLEDevice | None = None
        self._push_started = False
        self._unavailable_logged = False
        self._unsub_freshness_check: Callable[[], None] | None = None

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
            always_update=(self.connection_mode is ConnectionMode.POLL_AND_DISCONNECT),
        )

    def start_freshness_check(self) -> None:
        """Track freshness after the first successful coordinator refresh."""
        if self.connection_mode is ConnectionMode.POLL_AND_DISCONNECT:
            self._unsub_freshness_check = async_track_time_interval(
                self.hass,
                self._async_check_data_freshness,
                timedelta(seconds=self._scan_interval),
            )

    @property
    def data_is_fresh(self) -> bool:
        """Return whether the latest polled state is within its freshness window."""
        if self.connection_mode is not ConnectionMode.POLL_AND_DISCONNECT:
            return True
        if self.last_update_success_time is None:
            return False
        return dt_util.utcnow() - self.last_update_success_time <= timedelta(
            seconds=self._scan_interval * 2
        )

    @callback
    def _async_check_data_freshness(self, _now: datetime) -> None:
        """Refresh entity availability when polled data becomes stale."""
        if not self.data_is_fresh:
            self.async_update_listeners()

    @override
    async def _async_update_data(self) -> GattDeviceState:
        """Connect to the device and return its latest sensor state."""
        if self.connection_mode is ConnectionMode.POLL_AND_DISCONNECT:
            ble_device = self._get_live_ble_device()
            if ble_device is None:
                self._log_unavailable()
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="bluetooth_device_unavailable",
                )

            client = GattLinkClient(
                ble_device,
                mode=ConnectionMode.POLL_AND_DISCONNECT,
                name=self.device_name,
            )
            try:
                state = await client.poll()
            except GattLinkError as err:
                if isinstance(err, GattConnectionError):
                    self._log_unavailable()
                async_handle_connection_error(self.hass, self._config_entry, err)
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="read_failed",
                ) from err
            self._log_recovered()
            async_delete_proxy_slots_issue(self.hass, self._config_entry)
            return state

        if self._client is None:
            ble_device = self._get_live_ble_device()
            if ble_device is None:
                self._log_unavailable()
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="bluetooth_device_unavailable",
                )
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
                if isinstance(err, GattConnectionError):
                    self._log_unavailable()
                async_handle_connection_error(self.hass, self._config_entry, err)
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="connection_failed",
                ) from err
            self._client = client
            self._push_started = True
            self._log_recovered()
            async_delete_proxy_slots_issue(self.hass, self._config_entry)

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
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="bluetooth_device_unavailable",
            )
        return self._last_ble_device

    @callback
    def _log_unavailable(self) -> None:
        """Log an offline transition once."""
        if not self._unavailable_logged:
            _LOGGER.warning("Device %s went offline", self.device_name)
            self._unavailable_logged = True

    @callback
    def _log_recovered(self) -> None:
        """Log a recovery transition once."""
        if self._unavailable_logged:
            _LOGGER.info("Device %s reconnected", self.device_name)
            self._unavailable_logged = False

    @callback
    def _handle_state_update(self, state: GattDeviceState) -> None:
        """Publish state updates after the initial connection has started."""
        if self._push_started:
            self._log_recovered()
            async_delete_proxy_slots_issue(self.hass, self._config_entry)
            self.async_set_updated_data(state)

    @callback
    def _handle_disconnect(self) -> None:
        """Mark push entities unavailable while the client reconnects."""
        self._log_unavailable()
        self.async_set_update_error(
            UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_lost",
            )
        )

    async def async_shutdown(self) -> None:
        """Stop the BLE client and coordinator refresh tasks."""
        try:
            if self._unsub_freshness_check is not None:
                self._unsub_freshness_check()
            if self._client is not None:
                await self._client.stop()
        finally:
            await super().async_shutdown()


type GattLinkConfigEntry = ConfigEntry[GattLinkCoordinator]
