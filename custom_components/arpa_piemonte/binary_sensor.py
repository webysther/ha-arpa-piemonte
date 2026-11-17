"""The binary sensor of a hydrometer: whether its river is a flood risk.

It is the level status as on or off, for automations and dashboards that
want a safety sensor, as the risks of the civil protection.
"""

from __future__ import annotations

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

from .coordinator import ArpaPiemonteConfigEntry, ArpaPiemonteCoordinator
from .entity import ArpaPiemonteEntity
from .models import FLOOD_RISK_STATUSES

# The coordinator updates the entities
PARALLEL_UPDATES = 0

FLOOD_RISK = BinarySensorEntityDescription(
    key="flood_risk", device_class=BinarySensorDeviceClass.SAFETY
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArpaPiemonteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the flood risk of each hydrometer with a threshold, in its subentry."""
    del hass
    for subentry_id, coordinator in entry.runtime_data.stations.items():
        station = coordinator.station
        if station.has_level and station.thresholds.known:
            async_add_entities(
                [FloodRiskSensor(coordinator)], config_subentry_id=subentry_id
            )


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
