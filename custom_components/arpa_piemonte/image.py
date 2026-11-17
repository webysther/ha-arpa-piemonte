"""The charts of a station, as images.

The recent readings of Meteo 3R, and of the Arpa website for the pressure and
the solar radiation.

Each chart is drawn when new readings arrive, and kept until the next ones:
it is served from memory, without asking any source. Its state is the time of
its newest reading, so it changes only with the readings.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .charts import (
    Chart,
    draw,
    humidity_chart,
    level_chart,
    pressure_chart,
    radiation_chart,
    rain_chart,
    snow_chart,
    temperature_chart,
    wind_chart,
)
from .coordinator import ArpaPiemonteConfigEntry, ArpaPiemonteCoordinator
from .entity import ArpaPiemonteEntity
from .models import Quantity, StationSnapshot

# The coordinator updates the entities
PARALLEL_UPDATES = 0

SVG: Final = "image/svg+xml"
"""The type of the charts: Home Assistant serves any image/ type."""


@dataclass(frozen=True, kw_only=True)
class ChartDescription(ImageEntityDescription):
    """The chart of a quantity of a station."""

    quantity: Quantity
    """The quantity the station needs to have the chart."""
    chart_fn: Callable[[StationSnapshot], Chart | None]


CHARTS: tuple[ChartDescription, ...] = (
    ChartDescription(
        key="level_chart",
        quantity=Quantity.LEVEL,
        chart_fn=lambda snapshot: level_chart(
            snapshot.series.get(Quantity.LEVEL, ()), snapshot.thresholds
        ),
    ),
    ChartDescription(
        key="rain_chart",
        quantity=Quantity.RAIN_1H,
        chart_fn=lambda snapshot: rain_chart(snapshot.series.get(Quantity.RAIN_1H, ())),
    ),
    ChartDescription(
        key="temperature_chart",
        quantity=Quantity.TEMPERATURE,
        chart_fn=lambda snapshot: temperature_chart(
            snapshot.series.get(Quantity.TEMPERATURE, ())
        ),
    ),
    ChartDescription(
        key="humidity_chart",
        quantity=Quantity.HUMIDITY,
        chart_fn=lambda snapshot: humidity_chart(
            snapshot.series.get(Quantity.HUMIDITY, ())
        ),
    ),
    ChartDescription(
        key="snow_chart",
        quantity=Quantity.SNOW_DEPTH,
        chart_fn=lambda snapshot: snow_chart(
            snapshot.series.get(Quantity.SNOW_DEPTH, ())
        ),
    ),
    ChartDescription(
        key="wind_chart",
        quantity=Quantity.WIND_SPEED,
        chart_fn=lambda snapshot: wind_chart(
            snapshot.series.get(Quantity.WIND_SPEED, ()),
            snapshot.series.get(Quantity.GUST_SPEED, ()),
        ),
    ),
    ChartDescription(
        key="pressure_chart",
        quantity=Quantity.PRESSURE,
        chart_fn=lambda snapshot: pressure_chart(
            snapshot.series.get(Quantity.PRESSURE, ())
        ),
    ),
    ChartDescription(
        key="radiation_chart",
        quantity=Quantity.SOLAR_RADIATION,
        chart_fn=lambda snapshot: radiation_chart(
            snapshot.series.get(Quantity.SOLAR_RADIATION, ())
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArpaPiemonteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the charts of each station: those of the quantities it measures."""
    for subentry_id, coordinator in entry.runtime_data.stations.items():
        quantities = coordinator.station.quantities
        async_add_entities(
            [
                ChartImage(hass, coordinator, description)
                for description in CHARTS
                if description.quantity in quantities
            ],
            config_subentry_id=subentry_id,
        )


class ChartImage(ArpaPiemonteEntity, ImageEntity):
    """A chart of the recent readings of a station, as SVG.

    Unavailable while its source has given no reading of its quantity.
    """

    entity_description: ChartDescription
    _attr_content_type = SVG

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ArpaPiemonteCoordinator,
        description: ChartDescription,
    ) -> None:
        """Initialize a chart of the station."""
        ArpaPiemonteEntity.__init__(self, coordinator, Platform.IMAGE, description.key)
        ImageEntity.__init__(self, hass)
        self.entity_description = description
        self._svg: bytes | None = None
        self._draw()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Draw the chart again with the new readings."""
        self._draw()
        super()._handle_coordinator_update()

    def _draw(self) -> None:
        """Draw the chart of the readings, in the time zone of Home Assistant."""
        snapshot = self.coordinator.data
        chart = None if snapshot is None else self.entity_description.chart_fn(snapshot)
        if chart is None:
            self._svg = None
            self._attr_image_last_updated = None
            return
        self._svg = draw(chart, dt_util.get_default_time_zone()).encode()
        self._attr_image_last_updated = chart.end

    @property
    def available(self) -> bool:
        """Return whether the chart has readings to show."""
        return super().available and self._svg is not None

    async def async_image(self) -> bytes | None:
        """Return the chart, as drawn with the latest readings."""
        return self._svg
