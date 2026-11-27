"""Tests for dynamically created GATT Link sensors."""

import asyncio
from dataclasses import replace
from typing import cast
from unittest.mock import Mock

import pytest
from custom_components.gatt_link.const import (
    CONF_CONNECTION_MODE,
    CONF_SCAN_INTERVAL,
    CONNECTION_MODE_POLL_AND_DISCONNECT,
    DOMAIN,
)
from gatt_link_ble.const import (
    BATTERY_LEVEL_CHAR_UUID,
    TEMPERATURE_CHAR_UUID,
    THINGY_COLOR_CHAR_UUID,
)
from gatt_link_ble.exceptions import GattConnectionError
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfoBleak,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.helpers import DEFAULT_STATE, FakeGattLinkClientFactory

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _state_value(hass: HomeAssistant, entity_id: str) -> str:
    """Return an entity state, failing clearly if the entity is missing."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


@pytest.mark.asyncio
async def test_only_supported_sensors_are_added(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """The sensor platform creates entities only for present characteristics."""
    mock_gatt_link_client.state = replace(
        DEFAULT_STATE,
        supported_features=frozenset({TEMPERATURE_CHAR_UUID, BATTERY_LEVEL_CHAR_UUID}),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thingy",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"address": "AA:BB:CC:DD:EE:FF"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert set(hass.states.async_entity_ids("sensor")) == {
        "sensor.thingy_temperature",
        "sensor.thingy_battery",
    }
    assert _state_value(hass, "sensor.thingy_temperature") == "20.0"
    assert _state_value(hass, "sensor.thingy_battery") == "90"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_illuminance_sensor_is_disabled_by_default(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """The raw Thingy light channel is present but disabled by default."""
    mock_gatt_link_client.state = replace(
        DEFAULT_STATE,
        sensors=replace(DEFAULT_STATE.sensors, illuminance=123),
        supported_features=frozenset({THINGY_COLOR_CHAR_UUID}),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thingy",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"address": "AA:BB:CC:DD:EE:FF"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        "aa:bb:cc:dd:ee:ff_illuminance",
    )
    assert entity_id is not None
    registry_entry = registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None

    registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()

    assert len(mock_gatt_link_client.clients) == 2
    assert hass.states.get(entity_id) is not None
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_push_updates_sensor_and_availability(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Push callbacks update the value and reconnects restore availability."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thingy",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"address": "AA:BB:CC:DD:EE:FF"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    client = mock_gatt_link_client.clients[0]
    client.publish(
        replace(
            DEFAULT_STATE,
            sensors=replace(DEFAULT_STATE.sensors, temperature=23.5),
        )
    )
    await hass.async_block_till_done()
    assert _state_value(hass, "sensor.thingy_temperature") == "23.5"

    client.disconnect()
    client.disconnect()
    await hass.async_block_till_done()
    assert _state_value(hass, "sensor.thingy_temperature") == STATE_UNAVAILABLE
    assert [
        record.message
        for record in caplog.records
        if record.message == "Thingy is offline: Bluetooth connection unavailable"
    ] == ["Thingy is offline: Bluetooth connection unavailable"]

    client.publish(DEFAULT_STATE)
    client.publish(DEFAULT_STATE)
    await hass.async_block_till_done()
    assert _state_value(hass, "sensor.thingy_temperature") == "20.0"
    assert [
        record.message
        for record in caplog.records
        if record.message == "Thingy is online: Bluetooth connection recovered"
    ] == ["Thingy is online: Bluetooth connection recovered"]
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_push_callbacks_after_unload_are_ignored(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Late state, disconnect, and recovery callbacks cannot revive unloaded data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thingy",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"address": "AA:BB:CC:DD:EE:FF"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data
    client = mock_gatt_link_client.clients[0]
    original_state = coordinator.data
    assert original_state is not None

    client.stop_gate = asyncio.Event()
    unload_task = hass.async_create_task(
        hass.config_entries.async_unload(entry.entry_id)
    )
    try:
        await client.stop_entered.wait()
        assert client.stop_in_progress
        assert client.active
        client.publish(
            replace(
                DEFAULT_STATE,
                sensors=replace(DEFAULT_STATE.sensors, temperature=29.0),
            )
        )
        client.disconnect()
    finally:
        client.stop_gate.set()

    assert await unload_task
    assert client.stop_calls == 1
    assert not client.active
    assert _state_value(hass, "sensor.thingy_temperature") == STATE_UNAVAILABLE

    client.publish(
        replace(
            DEFAULT_STATE,
            sensors=replace(DEFAULT_STATE.sensors, temperature=30.0),
        )
    )
    client.disconnect()
    client.publish(
        replace(
            DEFAULT_STATE,
            sensors=replace(DEFAULT_STATE.sensors, temperature=31.0),
        )
    )
    await hass.async_block_till_done()

    assert coordinator.data is original_state
    assert coordinator.last_update_success
    assert _state_value(hass, "sensor.thingy_temperature") == STATE_UNAVAILABLE

    create_task = Mock()
    monkeypatch.setattr(hass, "async_create_task", create_task)
    coordinator._async_handle_device_discovered(
        cast(BluetoothServiceInfoBleak, Mock()),
        cast(BluetoothChange, Mock()),
    )
    coordinator._async_retry_connection(dt_util.utcnow())
    create_task.assert_not_called()


@pytest.mark.asyncio
async def test_poll_failure_marks_sensor_unavailable_then_recovers(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """A transient polling failure marks sensors unavailable until the next read."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thingy",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options={
            CONF_CONNECTION_MODE: CONNECTION_MODE_POLL_AND_DISCONNECT,
            CONF_SCAN_INTERVAL: 37,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data
    entity_id = "sensor.thingy_temperature"
    assert _state_value(hass, entity_id) == "20.0"

    mock_gatt_link_client.poll_error = GattConnectionError("temporary read failure")
    await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert _state_value(hass, entity_id) == STATE_UNAVAILABLE
    assert mock_gatt_link_client.outstanding_operations == 0
    assert mock_gatt_link_client.active_clients == ()

    mock_gatt_link_client.poll_error = None
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert _state_value(hass, entity_id) == "20.0"
    assert mock_gatt_link_client.outstanding_operations == 0
    assert mock_gatt_link_client.active_clients == ()
    assert await hass.config_entries.async_unload(entry.entry_id)
