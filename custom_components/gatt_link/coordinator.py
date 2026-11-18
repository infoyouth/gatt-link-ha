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
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfoBleak,
)
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
CONNECTION_RETRY_INTERVAL = timedelta(seconds=30)


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
        self._unsub_bluetooth_callback: Callable[[], None] | None = None
        self._unsub_connection_retry: Callable[[], None] | None = None

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
        if (
            self.connection_mode is ConnectionMode.POLL_AND_DISCONNECT
            and self._unsub_freshness_check is None
        ):
            self._unsub_freshness_check = async_track_time_interval(
                self.hass,
                self._async_check_data_freshness,
                timedelta(seconds=self._scan_interval),
            )

    def start_connection_recovery(self) -> None:
        """Retry startup when Bluetooth sees the configured device again."""
        _LOGGER.debug(
            "[BT-DIAG] Registering connectable-device discovery callback for %s "
            "(mode=%s)",
            self.device_name,
            self.connection_mode.value,
        )
        self._unsub_bluetooth_callback = bluetooth.async_register_callback(
            self.hass,
            self._async_handle_device_discovered,
            {"address": self.address, "connectable": True},
            bluetooth.BluetoothScanningMode.ACTIVE,
            replay=bluetooth.BluetoothCallbackReplay.NEWEST_FIRST,
        )
        if self.connection_mode is ConnectionMode.PUSH:
            self._unsub_connection_retry = async_track_time_interval(
                self.hass,
                self._async_retry_connection,
                CONNECTION_RETRY_INTERVAL,
            )
            _LOGGER.debug(
                "[BT-DIAG] Scheduled fallback connection retries for %s every %s",
                self.device_name,
                CONNECTION_RETRY_INTERVAL,
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
            _LOGGER.debug(
                "[BT-DIAG] Starting poll-and-disconnect client for %s",
                self.device_name,
            )
            try:
                state = await client.poll()
            except GattLinkError as err:
                _LOGGER.debug(
                    "[BT-DIAG] Poll failed for %s (%s)",
                    self.device_name,
                    type(err).__name__,
                )
                if isinstance(err, GattConnectionError):
                    self._log_unavailable()
                async_handle_connection_error(self.hass, self._config_entry, err)
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="read_failed",
                ) from err
            self._log_recovered()
            _LOGGER.debug("[BT-DIAG] Poll succeeded for %s", self.device_name)
            async_delete_proxy_slots_issue(self.hass, self._config_entry)
            self.start_freshness_check()
            self._stop_connection_recovery()
            return state

        if self._client is None:
            ble_device = self._get_live_ble_device()
            if ble_device is None:
                if not self._unavailable_logged:
                    self._log_ble_reachability_diagnostics()
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
            _LOGGER.debug("[BT-DIAG] Starting PUSH client for %s", self.device_name)
            try:
                await client.start()
            except GattLinkError as err:
                _LOGGER.debug(
                    "[BT-DIAG] PUSH client start failed for %s (%s)",
                    self.device_name,
                    type(err).__name__,
                )
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
            _LOGGER.debug("[BT-DIAG] PUSH client started for %s", self.device_name)
            async_delete_proxy_slots_issue(self.hass, self._config_entry)
            self._stop_connection_recovery()

        return self._client.state

    @callback
    def _async_handle_device_discovered(
        self,
        _service_info: BluetoothServiceInfoBleak,
        _change: BluetoothChange,
    ) -> None:
        """Retry setup as soon as HA sees the configured connectable device."""
        _LOGGER.debug(
            "[BT-DIAG] HA discovery callback for %s (change=%s, connectable=%s, "
            "rssi=%s); requesting refresh",
            self.device_name,
            _change,
            _service_info.connectable,
            _service_info.rssi,
        )
        self.hass.async_create_task(self.async_request_refresh())

    @callback
    def _async_retry_connection(self, _now: datetime) -> None:
        """Retry push startup periodically if a discovery event was missed."""
        if self._client is None:
            _LOGGER.debug(
                "[BT-DIAG] PUSH fallback retry fired for %s; requesting refresh",
                self.device_name,
            )
            self.hass.async_create_task(self.async_request_refresh())

    @callback
    def _stop_connection_recovery(self) -> None:
        """Stop startup retries after the first successful connection or poll."""
        if self._unsub_bluetooth_callback is not None:
            self._unsub_bluetooth_callback()
            self._unsub_bluetooth_callback = None
        if self._unsub_connection_retry is not None:
            self._unsub_connection_retry()
            self._unsub_connection_retry = None
        _LOGGER.debug("[BT-DIAG] Stopped startup recovery for %s", self.device_name)

    @callback
    def _get_live_ble_device(self) -> BLEDevice | None:
        """Return Home Assistant's current BLE device for this address."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass,
            self.address,
            connectable=True,
        )
        used_fallback = ble_device is None
        if used_fallback:
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass,
                self.address,
                connectable=False,
            )
        _LOGGER.debug(
            "[BT-DIAG] HA Bluetooth lookup for %s (mode=%s, connectable=True): %s",
            self.device_name,
            self.connection_mode.value,
            "found" if ble_device is not None else "not found",
        )
        if ble_device is not None and used_fallback:
            _LOGGER.debug(
                "[BT-DIAG] HA Bluetooth lookup resolved %s from fallback history",
                self.device_name,
            )
        if ble_device is None:
            scanner_devices = bluetooth.async_scanner_devices_by_address(
                self.hass,
                self.address,
                connectable=False,
            )
            advertisement = bluetooth.async_last_service_info(
                self.hass,
                self.address,
                connectable=False,
            )
            connectable_advertisement = bluetooth.async_last_service_info(
                self.hass,
                self.address,
                connectable=True,
            )
            _LOGGER.debug(
                "[BT-DIAG] HA scanner history for %s: advertisement=%s "
                "(reported_connectable=%s), connectable_history=%s",
                self.device_name,
                "present" if advertisement is not None else "absent",
                advertisement.connectable if advertisement is not None else None,
                "present" if connectable_advertisement is not None else "absent",
            )
            _LOGGER.debug(
                "[BT-DIAG] HA scanners seeing %s: %s",
                self.device_name,
                [
                    (
                        f"#{index}(scanner_connectable="
                        f"{scanner_device.scanner.connectable}, "
                        f"scanning={scanner_device.scanner.scanning}, "
                        f"rssi={scanner_device.advertisement.rssi})"
                    )
                    for index, scanner_device in enumerate(scanner_devices, start=1)
                ],
            )
        return ble_device

    @callback
    def _log_ble_reachability_diagnostics(self) -> None:
        """Log why Home Assistant cannot currently resolve a connectable device."""
        diagnostics_fn = getattr(
            bluetooth, "async_address_reachability_diagnostics", None
        )
        intent_type = getattr(bluetooth, "BluetoothReachabilityIntent", None)
        if not callable(diagnostics_fn) or intent_type is None:
            _LOGGER.debug("Bluetooth reachability diagnostics are unavailable")
            return

        try:
            diagnostics = diagnostics_fn(
                self.hass,
                self.address,
                intent_type.CONNECTION,
            )
        except Exception as err:
            _LOGGER.debug(
                "Unable to collect Bluetooth reachability diagnostics (%s)",
                type(err).__name__,
            )
            return

        _LOGGER.warning("[BT-DIAG] Bluetooth reachability diagnostics: %s", diagnostics)

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
            self._stop_connection_recovery()
            if self._unsub_freshness_check is not None:
                self._unsub_freshness_check()
            if self._client is not None:
                await self._client.stop()
        finally:
            await super().async_shutdown()


type GattLinkConfigEntry = ConfigEntry[GattLinkCoordinator]
