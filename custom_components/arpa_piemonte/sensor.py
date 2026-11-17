"""The sensors of a station.

Its readings, the level against its thresholds, and where the readings come
from.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ArpaPiemonteConfigEntry, ArpaPiemonteCoordinator
from .entity import ArpaPiemonteEntity
from .models import LevelStatus, Quantity, Source, StationSnapshot, Thresholds

# The coordinator updates the entities
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MeasurementDescription(SensorEntityDescription):
    """A sensor of a quantity the station measures."""

    quantity: Quantity
    state_class: SensorStateClass = SensorStateClass.MEASUREMENT


def _rain(quantity: Quantity) -> MeasurementDescription:
    return MeasurementDescription(
        key=quantity.value,
        quantity=quantity,
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=1,
    )


def _wind_speed(quantity: Quantity) -> MeasurementDescription:
    return MeasurementDescription(
        key=quantity.value,
        quantity=quantity,
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
    )


def _wind_direction(quantity: Quantity) -> MeasurementDescription:
    return MeasurementDescription(
        key=quantity.value,
        quantity=quantity,
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
    )


MEASUREMENTS: tuple[MeasurementDescription, ...] = (
    MeasurementDescription(
        key=Quantity.LEVEL.value,
        quantity=Quantity.LEVEL,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
    ),
    MeasurementDescription(
        key=Quantity.TEMPERATURE.value,
        quantity=Quantity.TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    MeasurementDescription(
        key=Quantity.HUMIDITY.value,
        quantity=Quantity.HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    _rain(Quantity.RAIN_1H),
    _rain(Quantity.RAIN_3H),
    _rain(Quantity.RAIN_24H),
    _wind_speed(Quantity.WIND_SPEED),
    _wind_direction(Quantity.WIND_DIRECTION),
    _wind_speed(Quantity.GUST_SPEED),
    _wind_direction(Quantity.GUST_DIRECTION),
    MeasurementDescription(
        key=Quantity.SNOW_DEPTH.value,
        quantity=Quantity.SNOW_DEPTH,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        suggested_display_precision=0,
    ),
)


@dataclass(frozen=True, kw_only=True)
class StationDescription(SensorEntityDescription):
    """A sensor of the station as a whole."""

    value_fn: Callable[[StationSnapshot], str | float | datetime | None]
    level_only: bool = False
    """Only for a station that measures a water level."""


def _threshold(
    key: str, value_fn: Callable[[Thresholds], float | None]
) -> StationDescription:
    return StationDescription(
        key=key,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        level_only=True,
        value_fn=lambda snapshot: (
            value_fn(snapshot.thresholds) if snapshot.thresholds else None
        ),
    )


STATION_SENSORS: tuple[StationDescription, ...] = (
    StationDescription(
        key="level_status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in LevelStatus],
        level_only=True,
        value_fn=lambda snapshot: snapshot.level_status,
    ),
    _threshold("pre_alarm_threshold", lambda thresholds: thresholds.pre_alarm),
    _threshold("guard_threshold", lambda thresholds: thresholds.guard),
    _threshold("danger_threshold", lambda thresholds: thresholds.danger),
    StationDescription(
        key="data_source",
        device_class=SensorDeviceClass.ENUM,
        options=[source.value for source in Source],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda snapshot: snapshot.source,
    ),
    StationDescription(
        key="last_measurement",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda snapshot: snapshot.measured_at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArpaPiemonteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of each station, in its subentry."""
    del hass
    for subentry_id, coordinator in entry.runtime_data.stations.items():
        async_add_entities(
            _station_sensors(coordinator), config_subentry_id=subentry_id
        )


def _station_sensors(coordinator: ArpaPiemonteCoordinator) -> list[SensorEntity]:
    """Return the sensors of a station: those of the quantities it measures."""
    quantities = coordinator.station.quantities
    entities: list[SensorEntity] = [
        MeasurementSensor(coordinator, description)
        for description in MEASUREMENTS
        if description.quantity in quantities
    ]
    entities.extend(
        StationSensor(coordinator, description)
        for description in STATION_SENSORS
        if coordinator.station.has_level or not description.level_only
    )
    return entities


class MeasurementSensor(ArpaPiemonteEntity, SensorEntity):
    """The latest reading of a quantity.

    It has no attributes: they would change with every download and be written
    again in the history. The time of the reading is the sensor
    ``last_measurement``, and its source ``data_source``.
    """

    entity_description: MeasurementDescription

    def __init__(
        self, coordinator: ArpaPiemonteCoordinator, description: MeasurementDescription
    ) -> None:
        """Initialize the sensor of a quantity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return whether a current reading of the quantity is known."""
        return (
            super().available
            and self.entity_description.quantity in self.coordinator.data.measurements
        )

    @property
    def native_value(self) -> float | None:
        """Return the latest reading."""
        measurement = self.coordinator.data.measurements.get(
            self.entity_description.quantity
        )
        return None if measurement is None else measurement.value


class StationSensor(ArpaPiemonteEntity, SensorEntity):
    """A sensor of the station as a whole."""

    entity_description: StationDescription

    def __init__(
        self, coordinator: ArpaPiemonteCoordinator, description: StationDescription
    ) -> None:
        """Initialize the sensor of the station."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | float | datetime | None:
        """Return the value of the station."""
        return self.entity_description.value_fn(self.coordinator.data)
