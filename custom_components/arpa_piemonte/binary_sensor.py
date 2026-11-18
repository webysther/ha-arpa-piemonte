"""The binary sensors of the risks: of a river, and of the alerts of a municipality.

The flood risk of a hydrometer is its level status as on or off, for
automations and dashboards that want a safety sensor, as the risks of the
civil protection. The risks of the municipality are on, today or tomorrow,
from the warning level of its options.
"""

from __future__ import annotations

from dataclasses import dataclass

from aioarpapiemonte import AlertLevel, RiskType

# BinarySensorDeviceClass is re-exported without being declared: binary_sensor.const
# only exists since 2026.9
from homeassistant.components.binary_sensor import (  # type: ignore[attr-defined]
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    ArpaPiemonteConfigEntry,
    ArpaPiemonteCoordinator,
    MunicipalityRisksCoordinator,
)
from .entity import ArpaPiemonteEntity, MunicipalityRisksEntity
from .models import FLOOD_RISK_STATUSES
from .risks import RISK_KEYS, RiskDay, warning_level

# The coordinator updates the entities
PARALLEL_UPDATES = 0

FLOOD_RISK = BinarySensorEntityDescription(
    key="flood_risk", device_class=BinarySensorDeviceClass.SAFETY
)


@dataclass(frozen=True, kw_only=True)
class RiskDescription(BinarySensorEntityDescription):
    """The binary sensor of a risk of the municipality on a day."""

    risk: RiskType
    day: RiskDay


RISKS: tuple[RiskDescription, ...] = tuple(
    RiskDescription(
        key=f"{RISK_KEYS[risk]}_risk_{day}",
        device_class=BinarySensorDeviceClass.SAFETY,
        risk=risk,
        day=day,
    )
    for day in RiskDay
    for risk in RiskType
)
"""Each risk of the bulletin, today and tomorrow: hydraulic_risk_today."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArpaPiemonteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the flood risk of the hydrometers, and the risks of the municipality.

    The flood risk of a hydrometer with a threshold is in its subentry; the
    risks of the municipality, in its entry.
    """
    del hass
    for subentry_id, coordinator in entry.runtime_data.stations.items():
        station = coordinator.station
        if station.has_level and station.thresholds.known:
            async_add_entities(
                [FloodRiskSensor(coordinator)], config_subentry_id=subentry_id
            )
    risks = entry.runtime_data.risks
    async_add_entities(RiskBinarySensor(risks, description) for description in RISKS)


class FloodRiskSensor(ArpaPiemonteEntity, BinarySensorEntity):
    """On (unsafe) while the level is at the pre-alarm threshold or above.

    It follows the level status: unavailable while the level is.
    """

    entity_description = FLOOD_RISK

    def __init__(self, coordinator: ArpaPiemonteCoordinator) -> None:
        """Initialize the flood risk of a hydrometer."""
        super().__init__(coordinator, Platform.BINARY_SENSOR, FLOOD_RISK.key)

    @property
    def available(self) -> bool:
        """Return whether the level is known against the thresholds."""
        return super().available and self.coordinator.data.level_status is not None

    @property
    def is_on(self) -> bool:
        """Return whether the level is at the pre-alarm threshold or above."""
        return self.coordinator.data.level_status in FLOOD_RISK_STATUSES


class RiskBinarySensor(MunicipalityRisksEntity, BinarySensorEntity):
    """On (unsafe) while a risk is at the warning level or above on its day.

    Unknown while the bulletin does not cover the day: tomorrow, until the
    bulletin of today is issued, around 13:00.
    """

    entity_description: RiskDescription

    def __init__(
        self, coordinator: MunicipalityRisksCoordinator, description: RiskDescription
    ) -> None:
        """Initialize the binary sensor of a risk on a day."""
        super().__init__(coordinator, Platform.BINARY_SENSOR, description.key)
        self.entity_description = description
        self._warning_level = warning_level(coordinator.config_entry.options)

    @property
    def is_on(self) -> bool | None:
        """Return whether the risk is at the warning level or above on the day."""
        description = self.entity_description
        level = self.coordinator.data.level_on(
            description.risk, description.day.date(self.today)
        )
        if level is AlertLevel.UNKNOWN:
            return None
        return level >= self._warning_level
