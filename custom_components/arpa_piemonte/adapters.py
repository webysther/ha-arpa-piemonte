"""The readings of each source, as readings of the integration.

Which source gives which quantity was measured on 2026-11-17, on the 374
stations: every reading of Meteo 3R equals the api_realtime at the same time,
for every quantity; the files of the Arpa website equal them for the level,
the temperature, the humidity and the snow. The rain of the website is of 10
minutes, and its wind is in m/s while the others give km/h: neither is used.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Final

from aioarpapiemonte import Param, ParamSeries, RealtimeData, RealtimeField
from aiometeo3r import Quantity as Meteo3rQuantity, StationData

from .models import Measurement, Quantity, Reading, Series, Source, Thresholds

METEO3R_QUANTITIES: Final[Mapping[Quantity, Meteo3rQuantity]] = {
    Quantity.LEVEL: Meteo3rQuantity.LEVEL,
    Quantity.TEMPERATURE: Meteo3rQuantity.TEMPERATURE,
    Quantity.HUMIDITY: Meteo3rQuantity.HUMIDITY,
    Quantity.RAIN_1H: Meteo3rQuantity.RAIN_1H,
    Quantity.RAIN_3H: Meteo3rQuantity.RAIN_3H,
    Quantity.RAIN_24H: Meteo3rQuantity.RAIN_24H,
    Quantity.WIND_SPEED: Meteo3rQuantity.WIND_SPEED,
    Quantity.WIND_DIRECTION: Meteo3rQuantity.WIND_DIRECTION,
    Quantity.GUST_SPEED: Meteo3rQuantity.GUST_SPEED,
    Quantity.GUST_DIRECTION: Meteo3rQuantity.GUST_DIRECTION,
    Quantity.SNOW_DEPTH: Meteo3rQuantity.SNOW_DEPTH,
}
"""The series of Meteo 3R of each quantity."""

WEBSITE_PARAMS: Final[Mapping[Quantity, Param]] = {
    Quantity.LEVEL: Param.LEVEL,
    Quantity.TEMPERATURE: Param.TEMPERATURE,
    Quantity.HUMIDITY: Param.HUMIDITY,
    Quantity.SNOW_DEPTH: Param.SNOW_DEPTH,
}
"""The files of the Arpa website equal to Meteo 3R: only these are read."""

REALTIME_FIELDS: Final[Mapping[Quantity, RealtimeField]] = {
    Quantity.LEVEL: RealtimeField.HYDROMETRIC_LEVEL,
    Quantity.TEMPERATURE: RealtimeField.AIR_TEMPERATURE,
    Quantity.HUMIDITY: RealtimeField.HUMIDITY,
    Quantity.RAIN_1H: RealtimeField.CUM_RAIN_1H,
    Quantity.RAIN_3H: RealtimeField.CUM_RAIN_3H,
    Quantity.RAIN_24H: RealtimeField.CUM_RAIN_24H,
    Quantity.WIND_SPEED: RealtimeField.WIND,
    Quantity.WIND_DIRECTION: RealtimeField.WIND_DIRECTION,
    Quantity.GUST_SPEED: RealtimeField.GUST_OF_WIND,
    Quantity.GUST_DIRECTION: RealtimeField.GUST_DIRECTION,
    Quantity.SNOW_DEPTH: RealtimeField.SNOW_HEIGHT,
}
"""The fields of the api_realtime of each quantity."""


def from_meteo3r(data: StationData) -> dict[Quantity, Measurement]:
    """Return the latest reading of each quantity of a station of Meteo 3R."""
    measurements = {}
    for quantity, series in METEO3R_QUANTITIES.items():
        reading = data.latest(series)
        if reading is not None:
            measurements[quantity] = Measurement(
                float(reading.value), reading.time, Source.METEO3R
            )
    return measurements


def series_of_meteo3r(data: StationData) -> dict[Quantity, Series]:
    """Return the readings of each quantity of a station of Meteo 3R."""
    series = {}
    for quantity, meteo3r_quantity in METEO3R_QUANTITIES.items():
        readings = tuple(
            Reading(reading.time, float(reading.value))
            for reading in data.series_of(meteo3r_quantity)
        )
        if readings:
            series[quantity] = readings
    return series


def thresholds_of_meteo3r(data: StationData) -> Thresholds:
    """Return the thresholds of a station of Meteo 3R."""
    thresholds = data.station.thresholds
    return Thresholds(thresholds.pre_alarm, thresholds.guard, thresholds.danger)


def from_website(
    files: Iterable[tuple[Quantity, ParamSeries]],
) -> dict[Quantity, Measurement]:
    """Return the latest valid reading of each file of the Arpa website."""
    measurements = {}
    for quantity, series in files:
        reading = series.latest()
        if reading is not None:
            measurements[quantity] = Measurement(
                float(reading.value), reading.time, Source.ARPA_WEBSITE
            )
    return measurements


def thresholds_of_website(series: ParamSeries) -> Thresholds | None:
    """Return the thresholds of a level file of the Arpa website."""
    if series.thresholds is None:
        return None
    thresholds = series.thresholds
    return Thresholds(thresholds.pre_alarm, thresholds.guard, thresholds.danger)


def from_realtime(data: RealtimeData) -> dict[Quantity, Measurement]:
    """Return the latest value of each quantity of the api_realtime."""
    measurements = {}
    for quantity, realtime_field in REALTIME_FIELDS.items():
        reading = data.latest(realtime_field)
        if reading is not None:
            measurements[quantity] = Measurement(
                float(reading.value), reading.time, Source.ARPA_REALTIME
            )
    return measurements
