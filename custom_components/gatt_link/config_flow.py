"""Config flow for the GATT Link integration."""

from typing import Any, override

import probatio
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ADDRESS,
    CONF_CONNECTION_MODE,
    CONF_SCAN_INTERVAL,
    CONNECTION_MODE_POLL_AND_DISCONNECT,
    CONNECTION_MODE_PUSH,
    DEFAULT_CONNECTION_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

SUPPORTED_SERVICE_UUIDS = frozenset(
    {
        "ef680100-9b35-4933-9b10-52ffa9740042",
        "0000181a-0000-1000-8000-00805f9b34fb",
    }
)


class GattLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle GATT Link device setup."""

    VERSION = 1

    _address: str | None
    _name: str | None

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        if not _is_supported_device(discovery_info):
            return self.async_abort(reason="no_devices_found")
        return await self._async_prepare_device(discovery_info)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow manual selection from discovered supported devices."""
        devices = _supported_devices(self.hass)
        if not devices:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            discovery_info = next(
                (
                    info
                    for info in devices
                    if format_mac(info.address) == format_mac(address)
                ),
                None,
            )
            if discovery_info is None:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_device_schema(devices),
                    errors={"base": "invalid_device"},
                )
            return await self._async_prepare_device(discovery_info)

        return self.async_show_form(
            step_id="user",
            data_schema=_device_schema(devices),
        )

    async def _async_prepare_device(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Set up device identity and ask for confirmation."""
        self._address = discovery_info.address
        self._name = discovery_info.name or discovery_info.address
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding the discovered device."""
        if self._address is None:
            return self.async_abort(reason="invalid_device")

        if user_input is not None:
            return self.async_create_entry(
                title=self._name or self._address,
                data={CONF_ADDRESS: self._address},
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={"name": self._name or self._address},
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return GattLinkOptionsFlow()


class GattLinkOptionsFlow(OptionsFlow):
    """Configure the device connection mode."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle connection options."""
        if user_input is not None:
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            if (
                isinstance(scan_interval, bool)
                or not isinstance(scan_interval, (int, float))
                or scan_interval < 1
                or scan_interval % 1
            ):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._options_schema(),
                    errors={"base": "invalid_scan_interval"},
                )

            return self.async_create_entry(
                title="",
                data={
                    CONF_CONNECTION_MODE: user_input[CONF_CONNECTION_MODE],
                    CONF_SCAN_INTERVAL: int(scan_interval),
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self._options_schema(),
        )

    def _options_schema(self) -> probatio.Schema:
        """Build the connection options form schema."""
        return probatio.Schema(
            {
                probatio.Required(
                    CONF_CONNECTION_MODE,
                    default=self.config_entry.options.get(
                        CONF_CONNECTION_MODE, DEFAULT_CONNECTION_MODE
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            CONNECTION_MODE_PUSH,
                            CONNECTION_MODE_POLL_AND_DISCONNECT,
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_CONNECTION_MODE,
                    )
                ),
                probatio.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )


def _supported_devices(
    hass: HomeAssistant,
) -> list[BluetoothServiceInfoBleak]:
    """Return discovered, connectable devices supported by this integration."""
    return [
        info
        for info in async_discovered_service_info(hass, connectable=True)
        if _is_supported_device(info)
    ]


def _is_supported_device(discovery_info: BluetoothServiceInfoBleak) -> bool:
    """Check whether an advertisement includes a supported service."""
    return not SUPPORTED_SERVICE_UUIDS.isdisjoint(discovery_info.service_uuids)


def _device_schema(
    devices: list[BluetoothServiceInfoBleak],
) -> probatio.Schema:
    """Build the manual device-selection schema."""
    options: list[SelectOptionDict] = [
        SelectOptionDict(
            label=info.name or info.address,
            value=info.address,
        )
        for info in devices
    ]
    return probatio.Schema(
        {
            probatio.Required(CONF_ADDRESS): SelectSelector(
                SelectSelectorConfig(
                    options=options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )
