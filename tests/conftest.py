"""Shared fixtures for the GATT Link integration tests."""

import pytest
from bleak.backends.device import BLEDevice
from custom_components.gatt_link import coordinator as coordinator_module
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from tests.helpers import FakeGattLinkClientFactory


@pytest.fixture
def mock_ble_device() -> BLEDevice:
    """Return a fake BLE device."""
    return BLEDevice("AA:BB:CC:DD:EE:FF", "Thingy", {})


@pytest.fixture
def mock_gatt_link_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_ble_device: BLEDevice,
) -> FakeGattLinkClientFactory:
    """Replace the BLE client and Bluetooth lookup with controlled mocks."""
    factory = FakeGattLinkClientFactory()
    monkeypatch.setattr(coordinator_module, "GattLinkClient", factory)

    def get_ble_device(
        _hass: HomeAssistant,
        _address: str,
        connectable: bool = True,
    ) -> BLEDevice:
        assert connectable
        return mock_ble_device

    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        get_ble_device,
    )
    return factory
