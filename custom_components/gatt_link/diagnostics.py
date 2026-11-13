"""Diagnostics support for GATT Link."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS
from .coordinator import GattLinkConfigEntry

TO_REDACT = {CONF_ADDRESS, "unique_id"}


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant,
    entry: GattLinkConfigEntry,
) -> dict[str, Any]:
    """Return redacted config-entry and latest device diagnostics."""
    state = entry.runtime_data.data
    device_state = asdict(state)
    device_state["supported_features"] = sorted(state.supported_features)

    return async_redact_data(
        {
            "config_entry": entry.as_dict(),
            "device_state": device_state,
        },
        TO_REDACT,
    )
