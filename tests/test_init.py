"""Tests for GATT Link config-entry setup and teardown."""

import asyncio
import logging
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from custom_components.gatt_link import coordinator as coordinator_module
from custom_components.gatt_link.const import (
    CONF_CONNECTION_MODE,
    CONF_SCAN_INTERVAL,
    CONNECTION_MODE_POLL_AND_DISCONNECT,
    DOMAIN,
)
from custom_components.gatt_link.coordinator import GattLinkCoordinator
from gatt_link_ble import ConnectionMode
from gatt_link_ble.exceptions import GattConnectionError, GattTimeoutError
from habluetooth import BaseHaScanner
from homeassistant.components import bluetooth
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.helpers import FakeGattLinkClientFactory

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


class _TestBluetoothScanner(BaseHaScanner):
    """Provide discovered advertisement data for a synthetic scanner."""

    def get_discovered_device_advertisement_data(
        self,
        address: str,
    ) -> tuple[BLEDevice, AdvertisementData] | None:
        """Return synthetic advertisement data recorded by the base scanner."""
        if (service_info := self._previous_service_info.get(address)) is None:
            return None
        return (
            service_info.device,
            AdvertisementData(
                service_info.name,
                service_info.manufacturer_data,
                service_info.service_data,
                service_info.service_uuids,
                service_info.tx_power,
                service_info.rssi,
                (),
            ),
        )


def _config_entry(
    hass: HomeAssistant,
    options: dict[str, str | int] | None = None,
) -> MockConfigEntry:
    """Create and register a GATT Link config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thingy",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options=options or {},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize(
    ("data", "options", "translation_key"),
    [
        ({}, {}, "invalid_address"),
        (
            {"address": "AA:BB:CC:DD:EE:FF"},
            {CONF_CONNECTION_MODE: "invalid"},
            "invalid_connection_mode",
        ),
        (
            {"address": "AA:BB:CC:DD:EE:FF"},
            {CONF_SCAN_INTERVAL: 0},
            "invalid_scan_interval",
        ),
    ],
)
def test_coordinator_rejects_invalid_config(
    hass: HomeAssistant,
    data: dict[str, str],
    options: dict[str, str | int],
    translation_key: str,
) -> None:
    """Invalid stored config produces a translated setup error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thingy",
        unique_id="aa:bb:cc:dd:ee:ff",
        data=data,
        options=options,
    )

    with pytest.raises(ConfigEntryError) as error:
        GattLinkCoordinator(hass, entry)

    assert error.value.translation_domain == DOMAIN
    assert error.value.translation_key == translation_key


@pytest.mark.asyncio
async def test_push_setup_starts_client_and_unload_stops_it(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Push mode starts one persistent client and stops it on unload."""
    entry = _config_entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.connection_mode is ConnectionMode.PUSH
    assert len(mock_gatt_link_client.clients) == 1
    assert mock_gatt_link_client.clients[0].start_calls == 1

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_repeated_shutdown_leaves_no_active_client(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Repeated coordinator shutdown remains safe and leaves no client active."""
    entry = _config_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data
    client = mock_gatt_link_client.clients[0]

    await coordinator.async_shutdown()
    await coordinator.async_shutdown()

    assert not client.active
    assert mock_gatt_link_client.active_clients == ()
    assert mock_gatt_link_client.outstanding_operations == 0
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_shutdown_cancellation_drains_client_stop(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Cancelling shutdown does not abandon an in-flight client disconnect."""
    entry = _config_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data
    client = mock_gatt_link_client.clients[0]
    client.stop_gate = asyncio.Event()
    shutdown_task = hass.async_create_task(coordinator.async_shutdown())

    try:
        await client.stop_entered.wait()
        shutdown_task.cancel()
        client.stop_gate.set()
        await asyncio.gather(shutdown_task, return_exceptions=True)

        assert shutdown_task.cancelled()
        assert not client.active
        assert mock_gatt_link_client.outstanding_operations == 0
    finally:
        client.stop_gate.set()
        await asyncio.gather(shutdown_task, return_exceptions=True)
        await coordinator.async_shutdown()
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_shutdown_cancels_pending_push_start(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Shutdown cancels an in-flight initial start without leaking the client."""
    mock_gatt_link_client.start_gate = asyncio.Event()
    coordinator = GattLinkCoordinator(hass, _config_entry(hass))
    refresh_task = hass.async_create_task(coordinator.async_refresh())

    try:
        await mock_gatt_link_client.client_created.wait()
        client = mock_gatt_link_client.clients[0]
        await client.start_entered.wait()

        assert client.active
        assert mock_gatt_link_client.active_clients == (client,)
        assert mock_gatt_link_client.outstanding_operations == 1

        await coordinator.async_shutdown()

        assert refresh_task.done()
        assert not client.active
        assert client.start_cleanup_calls == 1
        assert mock_gatt_link_client.outstanding_operations == 0
        assert mock_gatt_link_client.active_clients == ()
    finally:
        if mock_gatt_link_client.start_gate is not None:
            mock_gatt_link_client.start_gate.set()
        await asyncio.gather(refresh_task, return_exceptions=True)
        await coordinator.async_shutdown()


@pytest.mark.asyncio
async def test_cancellation_during_poll_cleans_up_operation(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Cancelling setup during a poll leaves no client operation running."""
    mock_gatt_link_client.poll_gate = asyncio.Event()
    entry = _config_entry(
        hass,
        {
            CONF_CONNECTION_MODE: CONNECTION_MODE_POLL_AND_DISCONNECT,
            CONF_SCAN_INTERVAL: 37,
        },
    )
    setup_task = hass.async_create_task(hass.config_entries.async_setup(entry.entry_id))

    try:
        await mock_gatt_link_client.client_created.wait()
        client = mock_gatt_link_client.clients[0]
        await client.poll_entered.wait()

        setup_task.cancel()
        await asyncio.gather(setup_task, return_exceptions=True)

        assert not client.poll_in_progress
        assert mock_gatt_link_client.outstanding_operations == 0
        assert mock_gatt_link_client.active_clients == ()
    finally:
        if mock_gatt_link_client.poll_gate is not None:
            mock_gatt_link_client.poll_gate.set()
        await asyncio.gather(setup_task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scanner_connectable", "expected_connectable_lookup"),
    [(True, True), (False, False)],
)
async def test_live_bluetooth_manager_indexes_scanner_advertisements(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
    scanner_connectable: bool,
    expected_connectable_lookup: bool,
) -> None:
    """Exercise HA's Bluetooth histories and lookup with a synthetic scanner."""
    entry = _config_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    scanner = _TestBluetoothScanner(
        source="test-scanner",
        adapter="test-adapter",
        connectable=scanner_connectable,
    )
    unsubscribe_scanner = bluetooth.async_register_scanner(hass, scanner)
    try:
        scanner._async_on_advertisement(
            address="aa:bb:cc:dd:ee:ff",
            rssi=-60,
            local_name="Thingy",
            service_uuids=["ef680100-9b35-4933-9b10-52ffa9740042"],
            service_data={},
            manufacturer_data={},
            tx_power=None,
            details={},
            advertisement_monotonic_time=time.monotonic(),
        )
        await hass.async_block_till_done()

        assert scanner._previous_service_info.get("aa:bb:cc:dd:ee:ff") is not None

        coordinator = entry.runtime_data
        scanner_devices = bluetooth.async_scanner_devices_by_address(
            hass,
            coordinator.address,
            connectable=False,
        )
        all_history = bluetooth.async_last_service_info(
            hass,
            coordinator.address,
            connectable=False,
        )
        connectable_history = bluetooth.async_last_service_info(
            hass,
            coordinator.address,
            connectable=True,
        )
        assert len(scanner_devices) == 1
        assert all_history is not None
        assert all_history.service_uuids == ["ef680100-9b35-4933-9b10-52ffa9740042"]
        assert (connectable_history is not None) is expected_connectable_lookup
    finally:
        unsubscribe_scanner()
        assert await hass.config_entries.async_unload(entry.entry_id)
    assert mock_gatt_link_client.clients[0].stop_calls == 1


@pytest.mark.asyncio
async def test_poll_mode_uses_configured_interval(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Poll mode polls and disconnects on coordinator refreshes."""
    interval = 37
    entry = _config_entry(
        hass,
        {
            CONF_CONNECTION_MODE: CONNECTION_MODE_POLL_AND_DISCONNECT,
            CONF_SCAN_INTERVAL: interval,
        },
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data
    assert coordinator.update_interval.total_seconds() == interval
    assert mock_gatt_link_client.clients[0].mode is ConnectionMode.POLL_AND_DISCONNECT
    assert mock_gatt_link_client.clients[0].poll_calls == 1

    await coordinator.async_refresh()

    assert len(mock_gatt_link_client.clients) == 2
    assert mock_gatt_link_client.clients[1].poll_calls == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_poll_mode_marks_data_unavailable_when_stale_then_recovers(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Polled entities become unavailable after two missed update intervals."""
    interval = 37
    entry = _config_entry(
        hass,
        {
            CONF_CONNECTION_MODE: CONNECTION_MODE_POLL_AND_DISCONNECT,
            CONF_SCAN_INTERVAL: interval,
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data
    entity_id = "sensor.thingy_temperature"
    assert hass.states.get(entity_id) is not None

    coordinator.last_update_success_time = dt_util.utcnow() - timedelta(
        seconds=interval * 2 + 1
    )
    coordinator._async_check_data_freshness(dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await coordinator.async_refresh()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "20.0"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_poll_mode_keeps_entry_loaded_when_device_is_missing(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Polling fails cleanly when Bluetooth no longer sees the device."""
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *_args, **_kwargs: None,
    )
    entry = _config_entry(
        hass,
        {
            CONF_CONNECTION_MODE: CONNECTION_MODE_POLL_AND_DISCONNECT,
            CONF_SCAN_INTERVAL: 37,
        },
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.data is None
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_registered_sensors_are_unavailable_when_device_is_missing(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restore known sensors as unavailable if startup has no device state."""
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *_args, **_kwargs: None,
    )
    entry = _config_entry(hass)
    registered_sensor = er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        "aa:bb:cc:dd:ee:ff_temperature",
        config_entry=entry,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    state = hass.states.get(registered_sensor.entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_poll_mode_translates_ble_read_errors(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Polling turns BLE failures into translated coordinator errors."""
    mock_gatt_link_client.poll_error = GattConnectionError("connection failed")
    entry = _config_entry(
        hass,
        {
            CONF_CONNECTION_MODE: CONNECTION_MODE_POLL_AND_DISCONNECT,
            CONF_SCAN_INTERVAL: 37,
        },
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.data is None
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_push_mode_logs_reachability_diagnostics_when_device_is_missing(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Push startup logs HA reachability details when lookup returns no device."""
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *_args, **_kwargs: None,
    )
    connection_intent = object()
    diagnostics = Mock(return_value="No connectable scanner currently sees device")
    monkeypatch.setattr(
        bluetooth,
        "BluetoothReachabilityIntent",
        SimpleNamespace(CONNECTION=connection_intent),
        raising=False,
    )
    monkeypatch.setattr(
        bluetooth,
        "async_address_reachability_diagnostics",
        diagnostics,
        raising=False,
    )
    advertisement = SimpleNamespace(connectable=False)
    last_service_info = Mock(
        side_effect=lambda _hass, _address, *, connectable=True: (
            advertisement if not connectable else None
        )
    )
    monkeypatch.setattr(
        bluetooth,
        "async_last_service_info",
        last_service_info,
    )
    scanner_device = SimpleNamespace(
        scanner=SimpleNamespace(connectable=True, scanning=True),
        advertisement=SimpleNamespace(rssi=-60),
    )
    scanner_devices = Mock(return_value=[scanner_device])
    monkeypatch.setattr(
        bluetooth,
        "async_scanner_devices_by_address",
        scanner_devices,
    )
    coordinator = GattLinkCoordinator(hass, _config_entry(hass))

    with caplog.at_level(logging.DEBUG), pytest.raises(UpdateFailed) as error:
        await coordinator._async_update_data()

    assert error.value.translation_key == "bluetooth_device_unavailable"
    diagnostics.assert_called_once_with(hass, coordinator.address, connection_intent)
    assert last_service_info.call_count == 2
    scanner_devices.assert_called_once_with(
        hass,
        coordinator.address,
        connectable=False,
    )
    assert "Bluetooth could not resolve" in caplog.text
    assert (
        "advertisement=present (reported_connectable=False), connectable_history=absent"
    ) in caplog.text
    assert "#1(scanner_connectable=True, scanning=True, rssi=-60)" in caplog.text
    assert "No connectable scanner currently sees device" in caplog.text
    assert "AA:BB:CC:DD:EE:FF" not in caplog.text


@pytest.mark.asyncio
async def test_push_mode_rejects_nonconnectable_only_history(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Push waits for connectable discovery when only all-history has the device."""
    live_lookup = Mock(
        side_effect=lambda _hass, _address, connectable=True: (
            None if connectable else BLEDevice("AA:BB:CC:DD:EE:FF", "Thingy", {})
        )
    )
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        live_lookup,
    )
    entry = _config_entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.runtime_data.data is None
    assert mock_gatt_link_client.clients == []
    live_lookup.assert_called_once_with(hass, "aa:bb:cc:dd:ee:ff", connectable=True)
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_push_mode_falls_back_to_discovered_service_info(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
    mock_ble_device: BLEDevice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Push starts when HA discovery list contains MyT but history lookups do not."""
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        bluetooth,
        "async_discovered_service_info",
        lambda *_args, **_kwargs: [
            SimpleNamespace(
                address="AA:BB:CC:DD:EE:FF",
                device=mock_ble_device,
            )
        ],
    )
    entry = _config_entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert mock_gatt_link_client.clients[0].start_calls == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_push_mode_does_not_collect_diagnostics_when_device_is_found(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful initial lookup does not collect failure diagnostics."""
    diagnostics = Mock()
    monkeypatch.setattr(
        bluetooth,
        "async_address_reachability_diagnostics",
        diagnostics,
        raising=False,
    )
    entry = _config_entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    diagnostics.assert_not_called()
    assert mock_gatt_link_client.clients[0].start_calls == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_reachability_diagnostic_failure_preserves_update_error(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A diagnostics exception does not replace the original lookup failure."""
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *_args, **_kwargs: None,
    )
    connection_intent = object()
    diagnostics = Mock(side_effect=RuntimeError("diagnostics unavailable"))
    monkeypatch.setattr(
        bluetooth,
        "BluetoothReachabilityIntent",
        SimpleNamespace(CONNECTION=connection_intent),
        raising=False,
    )
    monkeypatch.setattr(
        bluetooth,
        "async_address_reachability_diagnostics",
        diagnostics,
        raising=False,
    )
    coordinator = GattLinkCoordinator(hass, _config_entry(hass))

    with caplog.at_level(logging.DEBUG), pytest.raises(UpdateFailed) as error:
        await coordinator._async_update_data()

    assert error.value.translation_key == "bluetooth_device_unavailable"
    assert "Unable to collect Bluetooth reachability diagnostics (RuntimeError)" in (
        caplog.text
    )


@pytest.mark.asyncio
async def test_push_mode_preserves_error_when_reachability_api_is_unavailable(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Older supported HA versions without the diagnostic API still work."""
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.delattr(
        bluetooth,
        "async_address_reachability_diagnostics",
        raising=False,
    )
    monkeypatch.delattr(bluetooth, "BluetoothReachabilityIntent", raising=False)
    coordinator = GattLinkCoordinator(hass, _config_entry(hass))

    with pytest.raises(UpdateFailed) as error:
        await coordinator._async_update_data()

    assert error.value.translation_key == "bluetooth_device_unavailable"


def test_reconnect_provider_requires_a_previously_seen_ble_device(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reconnect cannot proceed before a BLE device has been cached."""
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *_args, **_kwargs: None,
    )
    coordinator = GattLinkCoordinator(
        hass,
        MockConfigEntry(
            domain=DOMAIN,
            title="Thingy",
            unique_id="aa:bb:cc:dd:ee:ff",
            data={"address": "AA:BB:CC:DD:EE:FF"},
        ),
    )

    with pytest.raises(UpdateFailed) as error:
        coordinator._get_ble_device_for_reconnect()

    assert error.value.translation_key == "bluetooth_device_unavailable"


def test_reconnect_provider_requires_fresh_connectable_device(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reconnect waits for connectable discovery instead of using stale history."""
    stale_device = BLEDevice("AA:BB:CC:DD:EE:FF", "Stale Thingy", {})
    discovered_device: BLEDevice | None = None
    lookups: list[bool] = []

    def get_ble_device(
        _hass: HomeAssistant,
        _address: str,
        connectable: bool = True,
    ) -> BLEDevice | None:
        lookups.append(connectable)
        return discovered_device if connectable else stale_device

    monkeypatch.setattr(bluetooth, "async_ble_device_from_address", get_ble_device)
    monkeypatch.setattr(
        bluetooth,
        "async_discovered_service_info",
        lambda *_args, **_kwargs: [],
    )
    coordinator = GattLinkCoordinator(
        hass,
        MockConfigEntry(
            domain=DOMAIN,
            title="Thingy",
            unique_id="aa:bb:cc:dd:ee:ff",
            data={"address": "AA:BB:CC:DD:EE:FF"},
        ),
    )
    with pytest.raises(UpdateFailed) as error:
        coordinator._get_ble_device_for_reconnect()

    assert error.value.translation_key == "bluetooth_device_unavailable"
    assert lookups == [True]

    discovered_device = BLEDevice("AA:BB:CC:DD:EE:FF", "Fresh Thingy", {})
    assert coordinator._get_ble_device_for_reconnect() is discovered_device
    assert lookups == [True, True]


@pytest.mark.asyncio
async def test_options_update_reloads_client(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Changing options restarts the BLE client with the new mode."""
    entry = _config_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_CONNECTION_MODE: CONNECTION_MODE_POLL_AND_DISCONNECT,
            CONF_SCAN_INTERVAL: 45,
        },
    )
    await hass.async_block_till_done()

    assert len(mock_gatt_link_client.clients) == 2
    assert mock_gatt_link_client.clients[0].stop_calls == 1
    assert mock_gatt_link_client.clients[1].mode is ConnectionMode.POLL_AND_DISCONNECT
    assert entry.runtime_data.update_interval.total_seconds() == 45
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        GattConnectionError("connection failed"),
        GattTimeoutError("connection timed out"),
    ],
    ids=["connection-error", "timeout"],
)
async def test_push_connection_error_keeps_setup_loaded_for_retry(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
    error: GattConnectionError,
) -> None:
    """Connection errors prevent the config entry from completing setup."""
    entry = _config_entry(hass)
    mock_gatt_link_client.start_error = error

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert mock_gatt_link_client.clients[0].start_calls == 1
    assert entry.runtime_data.data is None
    assert isinstance(entry.runtime_data.last_exception, UpdateFailed)
    assert entry.runtime_data.last_exception.translation_key == "connection_failed"
    assert mock_gatt_link_client.outstanding_operations == 0
    assert mock_gatt_link_client.active_clients == ()
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_push_setup_recovers_when_device_is_discovered(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
    mock_ble_device: BLEDevice,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A later Bluetooth discovery starts the client and adds supported sensors."""
    device_available = False
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *_args, **_kwargs: mock_ble_device if device_available else None,
    )
    register_callback = Mock(return_value=Mock())
    monkeypatch.setattr(bluetooth, "async_register_callback", register_callback)
    entry = _config_entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.data is None
    assert hass.states.get("sensor.thingy_temperature") is None
    assert register_callback.call_args.args[2] == {
        "address": "aa:bb:cc:dd:ee:ff",
        "connectable": True,
    }
    assert register_callback.call_args.args[3] is bluetooth.BluetoothScanningMode.ACTIVE

    device_available = True
    register_callback.call_args.args[1](
        SimpleNamespace(
            address="AA:BB:CC:DD:EE:FF",
            connectable=True,
            rssi=-60,
            device=mock_ble_device,
        ),
        Mock(),
    )
    await hass.async_block_till_done()

    assert entry.runtime_data.data is not None
    assert mock_gatt_link_client.clients[0].start_calls == 1
    state = hass.states.get("sensor.thingy_temperature")
    assert state is not None
    assert state.state == "20.0"
    assert "HA discovery callback" in caplog.text
    register_callback.return_value.assert_called_once()
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_push_setup_retries_when_discovery_event_is_missed(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
    mock_ble_device: BLEDevice,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The timed fallback starts the client if HA misses the discovery callback."""
    device_available = False
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *_args, **_kwargs: mock_ble_device if device_available else None,
    )
    monkeypatch.setattr(bluetooth, "async_register_callback", Mock(return_value=Mock()))
    retry_registration = Mock(return_value=Mock())
    monkeypatch.setattr(
        coordinator_module,
        "async_track_time_interval",
        retry_registration,
    )
    entry = _config_entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.data is None
    assert retry_registration.call_args.args[2] == timedelta(seconds=30)

    device_available = True
    retry_registration.call_args.args[1](dt_util.utcnow())
    await hass.async_block_till_done()

    assert entry.runtime_data.data is not None
    assert mock_gatt_link_client.clients[0].start_calls == 1
    assert "PUSH fallback retry fired" in caplog.text
    assert await hass.config_entries.async_unload(entry.entry_id)
