"""The sensors of a station, and of the natural risks of its municipality.

Of a station: its readings, the level against its thresholds, and where the
readings come from. Of the risks: the highest alert, the danger now, the
operational phase, the level of each risk today and tomorrow, and the
bulletin; the earthquakes nearby; the heat waves; the avalanche danger.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from aioarpapiemonte import (
    MICRO_REGION_NAMES,
    HeatForecast,
    MunicipalityAlerts,
    RiskType,
)
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
    Platform,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    ArpaPiemonteConfigEntry,
    ArpaPiemonteCoordinator,
    RisksCoordinator,
)
from .entity import ArpaPiemonteEntity, MunicipalityRisksEntity
from .models import LevelStatus, Quantity, Source, StationSnapshot, Thresholds
from .risks import (
    ALERT_LEVELS,
    AVALANCHE_DANGERS,
    HEAT_LEVELS,
    PHASES,
    RISK_KEYS,
    AvalancheDays,
    NearbyEarthquake,
    RiskDay,
    danger_state,
    heat_state,
    highest_alert,
    level_state,
    phase_state,
)

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
    # At the station, not at sea level: Avigliana, at 344 m, read 952 to 983 hPa
    # (measured on 2026-11-17)
    MeasurementDescription(
        key=Quantity.PRESSURE.value,
        quantity=Quantity.PRESSURE,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        suggested_display_precision=1,
    ),
    MeasurementDescription(
        key=Quantity.SOLAR_RADIATION.value,
        quantity=Quantity.SOLAR_RADIATION,
        device_class=SensorDeviceClass.IRRADIANCE,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
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


@dataclass(frozen=True, kw_only=True)
class RiskSensorDescription[DataT](SensorEntityDescription):
    """A sensor of a natural risk of a municipality, from its coordinator."""

    value_fn: Callable[[DataT, date], str | int | datetime | None]
    """Return the value, from the data and the date of today in Italy."""


def _risk_level(
    risk: RiskType, day: RiskDay
) -> RiskSensorDescription[MunicipalityAlerts]:
    """Return the sensor of the level of a risk on a day: hydraulic_risk_level_today."""
    return RiskSensorDescription(
        key=f"{RISK_KEYS[risk]}_risk_level_{day}",
        device_class=SensorDeviceClass.ENUM,
        options=ALERT_LEVELS,
        value_fn=lambda alerts, today: level_state(
            alerts.level_on(risk, day.date(today))
        ),
    )


ALERT_SENSORS: tuple[RiskSensorDescription[MunicipalityAlerts], ...] = (
    RiskSensorDescription(
        key="highest_alert",
        device_class=SensorDeviceClass.ENUM,
        options=ALERT_LEVELS,
        value_fn=lambda alerts, today: level_state(highest_alert(alerts, today)),
    ),
    RiskSensorDescription(
        key="current_danger",
        device_class=SensorDeviceClass.ENUM,
        options=ALERT_LEVELS,
        value_fn=lambda alerts, _: level_state(alerts.current_danger),
    ),
    RiskSensorDescription(
        key="operational_phase",
        device_class=SensorDeviceClass.ENUM,
        options=PHASES,
        value_fn=lambda alerts, _: phase_state(alerts.phase),
    ),
    *(_risk_level(risk, day) for day in RiskDay for risk in RiskType),
    RiskSensorDescription(
        key="alert_zone",
        entity_category=EntityCategory.DIAGNOSTIC,
        # "Piem-B"; "Piem-G, Piem-L" for a municipality in two zones, as Asti
        value_fn=lambda alerts, _: ", ".join(alerts.zones) or None,
    ),
    RiskSensorDescription(
        key="alert_bulletin",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda alerts, _: alerts.issued,
    ),
    RiskSensorDescription(
        key="next_alert_bulletin",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda alerts, _: alerts.next_update,
    ),
)
"""The sensors of the alerts: the highest alert of today and tomorrow, the danger
now, the operational phase, the level of each risk on each day, then the zone
and the bulletin as diagnostics."""

EARTHQUAKE_SENSORS: tuple[RiskSensorDescription[tuple[NearbyEarthquake, ...]], ...] = (
    RiskSensorDescription(
        key="nearby_earthquakes",
        value_fn=lambda earthquakes, _: len(earthquakes),
    ),
)
"""The number of earthquakes of the last 30 days within the radius: each is a
geolocation entity too."""


def _heat_wave(day: RiskDay) -> RiskSensorDescription[HeatForecast]:
    """Return the sensor of the heat of a day: heat_wave_today."""
    return RiskSensorDescription(
        key=f"heat_wave_{day}",
        device_class=SensorDeviceClass.ENUM,
        options=HEAT_LEVELS,
        value_fn=lambda forecast, today: heat_state(
            None if (heat := forecast.on(day.date(today))) is None else heat.level
        ),
    )


HEAT_SENSORS: tuple[RiskSensorDescription[HeatForecast], ...] = (
    *(_heat_wave(day) for day in RiskDay),
    RiskSensorDescription(
        key="heat_wave_city",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda forecast, _: forecast.city.value.title(),
    ),
)
"""The heat of today and tomorrow in the capital, and the capital as a
diagnostic."""


def _avalanche_danger(day: RiskDay) -> RiskSensorDescription[AvalancheDays]:
    """Return the sensor of the avalanche danger of a day: avalanche_danger_today."""
    return RiskSensorDescription(
        key=f"avalanche_danger_{day}",
        device_class=SensorDeviceClass.ENUM,
        options=AVALANCHE_DANGERS,
        value_fn=lambda days, today: danger_state(days.danger_on(day.date(today))),
    )


AVALANCHE_SENSORS: tuple[RiskSensorDescription[AvalancheDays], ...] = (
    *(_avalanche_danger(day) for day in RiskDay),
    RiskSensorDescription(
        key="avalanche_region",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda days, _: MICRO_REGION_NAMES.get(days.region_id, days.region_id),
    ),
)
"""The avalanche danger of today and tomorrow in the micro-region of the
position, the highest of the bulletin, and the micro-region as a diagnostic."""

RISK_SENSORS: tuple[RiskSensorDescription[Any], ...] = (
    *ALERT_SENSORS,
    *EARTHQUAKE_SENSORS,
    *HEAT_SENSORS,
    *AVALANCHE_SENSORS,
)
"""Every sensor of the risks of a municipality: those of the risks it has."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArpaPiemonteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of each station, in its subentry, and of the risks."""
    del hass
    for subentry_id, coordinator in entry.runtime_data.stations.items():
        async_add_entities(
            _station_sensors(coordinator), config_subentry_id=subentry_id
        )
    risks = entry.runtime_data.risks
    async_add_entities(
        [
            *_risk_sensors(risks.alerts, ALERT_SENSORS),
            *_risk_sensors(risks.earthquakes, EARTHQUAKE_SENSORS),
            *_risk_sensors(risks.heat, HEAT_SENSORS),
            *_risk_sensors(risks.avalanches, AVALANCHE_SENSORS),
        ]
    )


def _risk_sensors[DataT](
    coordinator: RisksCoordinator[DataT] | None,
    descriptions: Iterable[RiskSensorDescription[DataT]],
) -> list[SensorEntity]:
    """Return the sensors of a risk; none when the municipality does not have it."""
    if coordinator is None:
        return []
    return [RisksSensor(coordinator, description) for description in descriptions]


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
        super().__init__(coordinator, Platform.SENSOR, description.key)
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
        super().__init__(coordinator, Platform.SENSOR, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | float | datetime | None:
        """Return the value of the station."""
        return self.entity_description.value_fn(self.coordinator.data)


class RisksSensor[DataT](
    MunicipalityRisksEntity[RisksCoordinator[DataT]], SensorEntity
):
    """A sensor of a natural risk of a municipality."""

    entity_description: RiskSensorDescription[DataT]

    def __init__(
        self,
        coordinator: RisksCoordinator[DataT],
        description: RiskSensorDescription[DataT],
    ) -> None:
        """Initialize a sensor of a risk."""
        super().__init__(coordinator, Platform.SENSOR, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | datetime | None:
        """Return the value, today in Italy."""
        return self.entity_description.value_fn(self.coordinator.data, self.today)
