"""Home Assistant integration for GATT Link BLE devices."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import GattLinkConfigEntry, GattLinkCoordinator

PLATFORMS = (Platform.SENSOR,)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GattLinkConfigEntry,
) -> bool:
    """Set up a GATT Link device from a config entry."""
    coordinator = GattLinkCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: GattLinkConfigEntry,
) -> bool:
    """Unload a GATT Link device."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload the integration when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
