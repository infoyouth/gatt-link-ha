"""Tests for actionable GATT Link repair issues."""

import pytest
from custom_components.gatt_link.const import DOMAIN
from gatt_link_ble.exceptions import GattConnectionError
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.helpers import FakeGattLinkClientFactory

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.asyncio
async def test_proxy_slot_issue_is_created_and_cleared_on_recovery(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Proxy-slot failures create actionable guidance, cleared on reconnect."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thingy",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"address": "AA:BB:CC:DD:EE:FF"},
    )
    entry.add_to_hass(hass)
    issue_id = f"proxy_slots_{entry.entry_id}"
    mock_gatt_link_client.start_error = GattConnectionError("ESP_GATT_CONN_CONN_CANCEL")

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    mock_gatt_link_client.start_error = None
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_unrelated_connection_error_does_not_create_repair(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Generic BLE failures do not produce a misleading proxy repair."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thingy",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"address": "AA:BB:CC:DD:EE:FF"},
    )
    entry.add_to_hass(hass)
    mock_gatt_link_client.start_error = GattConnectionError("connection failed")

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert not any(
        issue_id.startswith("proxy_slots_")
        for domain, issue_id in ir.async_get(hass).issues
        if domain == DOMAIN
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
