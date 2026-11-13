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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GattLinkConfigEntry, GattLinkCoordinator
from .entity import GattLinkEntity

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
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GattLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for supported characteristics on this device."""
    coordinator = entry.runtime_data
    supported_features = coordinator.data.supported_features
    async_add_entities(
        GattLinkSensor(coordinator, description)
        for description in SENSORS
        if not description.characteristic_uuids.isdisjoint(supported_features)
    )


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
        return self._value_fn(self.coordinator.data.sensors)
