"""Tests for redacted GATT Link diagnostics."""

import json
from dataclasses import asdict, replace

import pytest
from custom_components.gatt_link.const import DOMAIN
from custom_components.gatt_link.diagnostics import (
    async_get_config_entry_diagnostics,
)
from gatt_link_ble import DeviceMetadata
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.helpers import DEFAULT_STATE, FakeGattLinkClientFactory

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.asyncio
async def test_diagnostics_redact_address_and_unique_id(
    hass: HomeAssistant,
    mock_gatt_link_client: FakeGattLinkClientFactory,
) -> None:
    """Diagnostics expose useful device data without Bluetooth identifiers."""
    metadata = DeviceMetadata(
        manufacturer="Nordic Semiconductor",
        model="Thingy",
        firmware_revision="1.2.3",
        hardware_revision="A",
    )
    mock_gatt_link_client.state = replace(DEFAULT_STATE, metadata=metadata)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thingy",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"address": "AA:BB:CC:DD:EE:FF"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(diagnostics, sort_keys=True)

    assert entry.unique_id is not None
    assert entry.unique_id not in serialized
    assert DEFAULT_STATE.address not in serialized
    assert diagnostics["config_entry"]["unique_id"] == REDACTED
    assert diagnostics["config_entry"]["data"]["address"] == REDACTED
    assert diagnostics["device_state"]["address"] == REDACTED
    assert diagnostics["device_state"]["supported_features"] == sorted(
        DEFAULT_STATE.supported_features
    )
    assert diagnostics["device_state"]["metadata"] == asdict(metadata)
    assert diagnostics["device_state"]["sensors"] == asdict(DEFAULT_STATE.sensors)
    assert await hass.config_entries.async_unload(entry.entry_id)
