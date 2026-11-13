"""Tests for the GATT Link config and options flows."""

from collections.abc import Iterable

import pytest
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from custom_components.gatt_link import config_flow
from custom_components.gatt_link.const import (
    CONF_ADDRESS,
    CONF_CONNECTION_MODE,
    CONF_SCAN_INTERVAL,
    CONNECTION_MODE_POLL_AND_DISCONNECT,
    CONNECTION_MODE_PUSH,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from home_assistant_bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

ENVIRONMENTAL_SERVICE_UUID = "0000181a-0000-1000-8000-00805f9b34fb"
THINGY_SERVICE_UUID = "ef680100-9b35-4933-9b10-52ffa9740042"
UNSUPPORTED_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"


def _service_info(
    address: str,
    name: str,
    service_uuid: str,
) -> BluetoothServiceInfoBleak:
    """Create a Bluetooth service advertisement for a test device."""
    device = BLEDevice(address, name, {})
    advertisement = AdvertisementData(
        local_name=name,
        manufacturer_data={},
        service_data={},
        service_uuids=[service_uuid],
        tx_power=None,
        rssi=-55,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak.from_device_and_advertisement_data(
        device,
        advertisement,
        "local",
        0.0,
        True,
    )


async def _create_device_entry(
    hass: HomeAssistant,
    discovery_info: BluetoothServiceInfoBleak,
) -> None:
    """Run Bluetooth setup through its confirmation step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=discovery_info,
    )
    assert result["type"] == "form"
    assert result["step_id"] == "bluetooth_confirm"
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )


@pytest.mark.asyncio
async def test_bluetooth_discovery_creates_entry(hass: HomeAssistant) -> None:
    """A supported Bluetooth device is added after confirmation."""
    discovery_info = _service_info(
        "AA:BB:CC:DD:EE:FF",
        "Thingy",
        THINGY_SERVICE_UUID,
    )

    await _create_device_entry(hass, discovery_info)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.title == "Thingy"
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff"
    assert entry.data == {CONF_ADDRESS: discovery_info.address}


@pytest.mark.asyncio
async def test_manual_flow_filters_unsupported_devices(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual setup only offers supported discovered advertisements."""
    supported = _service_info(
        "AA:BB:CC:DD:EE:01",
        "Environmental sensor",
        ENVIRONMENTAL_SERVICE_UUID,
    )
    unsupported = _service_info(
        "AA:BB:CC:DD:EE:02",
        "Other device",
        UNSUPPORTED_SERVICE_UUID,
    )

    def discovered_devices(
        _hass: HomeAssistant, *, connectable: bool = True
    ) -> Iterable[BluetoothServiceInfoBleak]:
        assert connectable
        return [supported, unsupported]

    monkeypatch.setattr(
        config_flow,
        "async_discovered_service_info",
        discovered_devices,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: supported.address},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "bluetooth_confirm"
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {CONF_ADDRESS: supported.address}


@pytest.mark.asyncio
async def test_bluetooth_discovery_aborts_for_duplicate_device(
    hass: HomeAssistant,
) -> None:
    """A device cannot be configured more than once."""
    discovery_info = _service_info(
        "AA:BB:CC:DD:EE:FF",
        "Thingy",
        THINGY_SERVICE_UUID,
    )
    await _create_device_entry(hass, discovery_info)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=discovery_info,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_manual_flow_aborts_without_supported_devices(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual setup aborts when no supported device is discovered."""
    unsupported = _service_info(
        "AA:BB:CC:DD:EE:02",
        "Other device",
        UNSUPPORTED_SERVICE_UUID,
    )

    def discovered_devices(
        _hass: HomeAssistant, *, connectable: bool = True
    ) -> Iterable[BluetoothServiceInfoBleak]:
        assert connectable
        return [unsupported]

    monkeypatch.setattr(
        config_flow,
        "async_discovered_service_info",
        discovered_devices,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_found"


@pytest.mark.asyncio
async def test_options_flow_uses_defaults_and_saves_options(
    hass: HomeAssistant,
) -> None:
    """Options flow defaults to push and the standard polling interval."""
    discovery_info = _service_info(
        "AA:BB:CC:DD:EE:FF",
        "Thingy",
        THINGY_SERVICE_UUID,
    )
    await _create_device_entry(hass, discovery_info)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_CONNECTION_MODE: CONNECTION_MODE_PUSH,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    }

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CONNECTION_MODE: CONNECTION_MODE_POLL_AND_DISCONNECT,
            CONF_SCAN_INTERVAL: 45,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_CONNECTION_MODE: CONNECTION_MODE_POLL_AND_DISCONNECT,
        CONF_SCAN_INTERVAL: 45,
    }


@pytest.mark.asyncio
async def test_options_flow_rejects_nonpositive_interval(
    hass: HomeAssistant,
) -> None:
    """The polling interval must be a positive whole number."""
    discovery_info = _service_info(
        "AA:BB:CC:DD:EE:FF",
        "Thingy",
        THINGY_SERVICE_UUID,
    )
    await _create_device_entry(hass, discovery_info)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CONNECTION_MODE: CONNECTION_MODE_PUSH,
            CONF_SCAN_INTERVAL: 0,
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_scan_interval"}
