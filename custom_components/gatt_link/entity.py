"""Base entity for GATT Link devices."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GattLinkCoordinator


class GattLinkEntity(CoordinatorEntity[GattLinkCoordinator]):
    """Base class for entities connected to a GATT Link device."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return identifying information about the connected device."""
        state = self.coordinator.data
        address = format_mac(self.coordinator.address)
        return DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            manufacturer=state.metadata.manufacturer,
            model=state.metadata.model,
            name=state.name or self.coordinator.device_name,
            sw_version=state.metadata.firmware_revision,
            hw_version=state.metadata.hardware_revision,
        )
