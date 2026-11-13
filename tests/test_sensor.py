"""Tests for dynamically created GATT Link sensors."""

from dataclasses import replace

import pytest
from custom_components.gatt_link.const import DOMAIN
from gatt_link_ble.const import BATTERY_LEVEL_CHAR_UUID, TEMPERATURE_CHAR_UUID
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
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
async def test_push_updates_sensor_and_availability(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
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
    await hass.async_block_till_done()
    assert _state_value(hass, "sensor.thingy_temperature") == STATE_UNAVAILABLE

    client.publish(DEFAULT_STATE)
    await hass.async_block_till_done()
    assert _state_value(hass, "sensor.thingy_temperature") == "20.0"
    assert await hass.config_entries.async_unload(entry.entry_id)
