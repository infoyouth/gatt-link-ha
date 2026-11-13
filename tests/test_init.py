"""Tests for GATT Link config-entry setup and teardown."""

import pytest
from custom_components.gatt_link.const import (
    CONF_CONNECTION_MODE,
    CONF_SCAN_INTERVAL,
    CONNECTION_MODE_POLL_AND_DISCONNECT,
    DOMAIN,
)
from gatt_link_ble import ConnectionMode
from gatt_link_ble.exceptions import GattConnectionError
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.helpers import FakeGattLinkClientFactory

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


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
async def test_push_connection_error_prevents_setup(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Connection errors prevent the config entry from completing setup."""
    entry = _config_entry(hass)
    mock_gatt_link_client.start_error = GattConnectionError("connection failed")

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert mock_gatt_link_client.clients[0].start_calls == 1
