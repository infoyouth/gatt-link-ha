"""Sensor platform for GATT Link devices."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from gatt_link_ble import GattSensorData
from gatt_link_ble.const import (
    BATTERY_LEVEL_CHAR_UUID,
    HUMIDITY_CHAR_UUID,
    PRESSURE_CHAR_UUID,
    TEMPERATURE_CHAR_UUID,
    THINGY_COLOR_CHAR_UUID,
    THINGY_GAS_CHAR_UUID,
    THINGY_HUMIDITY_CHAR_UUID,
    THINGY_PRESSURE_CHAR_UUID,
    THINGY_TEMPERATURE_CHAR_UUID,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GattLinkConfigEntry, GattLinkCoordinator
from .entity import GattLinkEntity

PARALLEL_UPDATES = 0

type SensorValue = float | int | None
type SensorValueFunction = Callable[[GattSensorData], SensorValue]


@dataclass(frozen=True, slots=True)
class GattLinkSensorDescription:
    """Describe a GATT Link sensor and its BLE characteristic requirements."""

    entity: SensorEntityDescription
    characteristic_uuids: frozenset[str]
    value_fn: SensorValueFunction


SENSORS: tuple[GattLinkSensorDescription, ...] = (
    GattLinkSensorDescription(
        entity=SensorEntityDescription(
            key="temperature",
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        characteristic_uuids=frozenset(
            {TEMPERATURE_CHAR_UUID, THINGY_TEMPERATURE_CHAR_UUID}
        ),
        value_fn=lambda sensors: sensors.temperature,
    ),
    GattLinkSensorDescription(
        entity=SensorEntityDescription(
            key="humidity",
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        characteristic_uuids=frozenset({HUMIDITY_CHAR_UUID, THINGY_HUMIDITY_CHAR_UUID}),
        value_fn=lambda sensors: sensors.humidity,
    ),
    GattLinkSensorDescription(
        entity=SensorEntityDescription(
            key="pressure",
            translation_key="pressure",
            device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            native_unit_of_measurement=UnitOfPressure.HPA,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        characteristic_uuids=frozenset({PRESSURE_CHAR_UUID, THINGY_PRESSURE_CHAR_UUID}),
        value_fn=lambda sensors: sensors.pressure,
    ),
    GattLinkSensorDescription(
        entity=SensorEntityDescription(
            key="eco2",
            translation_key="eco2",
            device_class=SensorDeviceClass.CO2,
            native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        characteristic_uuids=frozenset({THINGY_GAS_CHAR_UUID}),
        value_fn=lambda sensors: sensors.eco2,
    ),
    GattLinkSensorDescription(
        entity=SensorEntityDescription(
            key="tvoc",
            translation_key="tvoc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
            native_unit_of_measurement=UnitOfRatio.PARTS_PER_BILLION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        characteristic_uuids=frozenset({THINGY_GAS_CHAR_UUID}),
        value_fn=lambda sensors: sensors.tvoc,
    ),
    GattLinkSensorDescription(
        entity=SensorEntityDescription(
            key="battery",
            translation_key="battery",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=True,
        ),
        characteristic_uuids=frozenset({BATTERY_LEVEL_CHAR_UUID}),
        value_fn=lambda sensors: sensors.battery,
    ),
    GattLinkSensorDescription(
        entity=SensorEntityDescription(
            key="illuminance",
            translation_key="illuminance",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        characteristic_uuids=frozenset({THINGY_COLOR_CHAR_UUID}),
        value_fn=lambda sensors: sensors.illuminance,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GattLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for supported characteristics on this device."""
    coordinator = entry.runtime_data
    remove_listener: Callable[[], None] | None = None
    added_sensor_keys: set[str] = set()
    unique_id_prefix = format_mac(coordinator.address)
    registered_unique_ids = {
        registry_entry.unique_id
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(_hass), entry.entry_id
        )
    }

    @callback
    def _async_remove_listener() -> None:
        nonlocal remove_listener
        if remove_listener is not None:
            remove_listener()
            remove_listener = None

    @callback
    def _async_add_sensors_when_ready() -> None:
        if coordinator.data is None:
            descriptions = [
                description
                for description in SENSORS
                if f"{unique_id_prefix}_{description.entity.key}"
                in registered_unique_ids
            ]
        else:
            supported_features = coordinator.data.supported_features
            descriptions = [
                description
                for description in SENSORS
                if not description.characteristic_uuids.isdisjoint(supported_features)
            ]
        descriptions = [
            description
            for description in descriptions
            if description.entity.key not in added_sensor_keys
        ]
        if descriptions:
            async_add_entities(
                GattLinkSensor(coordinator, description) for description in descriptions
            )
            added_sensor_keys.update(
                description.entity.key for description in descriptions
            )
        if coordinator.data is not None:
            _async_remove_listener()

    if coordinator.data is None:
        remove_listener = coordinator.async_add_listener(_async_add_sensors_when_ready)
        entry.async_on_unload(_async_remove_listener)
        _async_add_sensors_when_ready()
    else:
        _async_add_sensors_when_ready()


class GattLinkSensor(GattLinkEntity, SensorEntity):
    """Represent one sensor value from a GATT Link device."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: GattLinkCoordinator,
        description: GattLinkSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description.entity
        self._value_fn = description.value_fn
        self._attr_unique_id = (
            f"{format_mac(coordinator.address)}_{description.entity.key}"
        )

    @property
    @override
    def native_value(self) -> SensorValue:
        """Return the latest sensor value."""
        if self.coordinator.data is None:
            return None
        return self._value_fn(self.coordinator.data.sensors)
