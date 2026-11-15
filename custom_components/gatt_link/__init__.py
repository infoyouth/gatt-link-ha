"""Home Assistant integration for GATT Link BLE devices."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EventEntityRegistryUpdatedData
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from .coordinator import GattLinkConfigEntry, GattLinkCoordinator

PLATFORMS = (Platform.SENSOR,)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GattLinkConfigEntry,
) -> bool:
    """Set up a GATT Link device from a config entry."""
    coordinator = GattLinkCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    coordinator.start_freshness_check()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entity_ids = [
        registry_entry.entity_id
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass),
            entry.entry_id,
        )
    ]
    if entity_ids:

        @callback
        def _async_entity_registry_updated(
            event: Event[EventEntityRegistryUpdatedData],
        ) -> None:
            if event.data["action"] == "update" and "disabled_by" in event.data.get(
                "changes", {}
            ):
                hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

        entry.async_on_unload(
            async_track_entity_registry_updated_event(
                hass,
                entity_ids,
                _async_entity_registry_updated,
            )
        )
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
