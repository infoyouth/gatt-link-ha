"""Repair issue helpers for GATT Link."""

from gatt_link_ble import GattConnectionError, GattLinkError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_PROXY_SLOT_ERROR = "ESP_GATT_CONN_CONN_CANCEL"


def _proxy_slots_issue_id(entry: ConfigEntry) -> str:
    """Return the repair issue ID for one config entry."""
    return f"proxy_slots_{entry.entry_id}"


def async_handle_connection_error(
    hass: HomeAssistant,
    entry: ConfigEntry,
    error: GattLinkError,
) -> None:
    """Create actionable guidance for a Bluetooth proxy slot failure."""
    if not isinstance(error, GattConnectionError) or _PROXY_SLOT_ERROR not in str(
        error
    ):
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        _proxy_slots_issue_id(entry),
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="proxy_slots_exhausted",
    )


def async_delete_proxy_slots_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear proxy slot guidance after a successful connection."""
    ir.async_delete_issue(hass, DOMAIN, _proxy_slots_issue_id(entry))
