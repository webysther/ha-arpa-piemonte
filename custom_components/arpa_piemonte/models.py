"""The data of a station, whatever source gave it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Final

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from .const import (
    CONF_SENSOR_ID,
    CONF_SENSOR_LETTERS,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_THRESHOLDS,
    CONF_WEBSITE_PARAMS,
    MUNICIPALITY_ID_PREFIX,
    STATION_ID_PREFIX,
)
from .station_places import STATION_PLACES


class Quantity(StrEnum):
    """A quantity a station measures; the value is the key of its entity."""

    LEVEL = "level"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    RAIN_1H = "rain_1h"
    RAIN_3H = "rain_3h"
    RAIN_24H = "rain_24h"
    WIND_SPEED = "wind_speed"
    WIND_DIRECTION = "wind_direction"
    GUST_SPEED = "gust_speed"
    GUST_DIRECTION = "gust_direction"
    SNOW_DEPTH = "snow_depth"
    PRESSURE = "pressure"
    SOLAR_RADIATION = "solar_radiation"


SENSOR_QUANTITIES: Final[Mapping[str, tuple[Quantity, ...]]] = {
    "I": (Quantity.LEVEL,),
    "T": (Quantity.TEMPERATURE,),
    "H": (Quantity.HUMIDITY,),
    "P": (Quantity.RAIN_1H, Quantity.RAIN_3H, Quantity.RAIN_24H),
    "V": (
        Quantity.WIND_SPEED,
        Quantity.WIND_DIRECTION,
        Quantity.GUST_SPEED,
        Quantity.GUST_DIRECTION,
    ),
    "N": (Quantity.SNOW_DEPTH,),
    "B": (Quantity.PRESSURE,),
    "R": (Quantity.SOLAR_RADIATION,),
}
"""The quantities of each letter of the sensors of a station.

Measured on 2026-11-17 on the 374 stations: one station had a series without
its letter, 23 a letter without readings (a sensor that does not answer).
"""

WEBSITE_QUANTITIES: Final[Mapping[str, Quantity]] = {
    "baro": Quantity.PRESSURE,
    "radd": Quantity.SOLAR_RADIATION,
}
"""The quantities only the files of the Arpa website give, by the name of their
file: Meteo 3R and the api_realtime have no pressure nor radiation (measured on
2026-11-17).

The list of stations of the website names the files a station has. The
letters B and R say more: 2 of the 47 barometers and 2 of the 66 radiometers
have a file that is empty, years old or missing (measured on 2026-11-17).
"""


class Source(StrEnum):
    """Where a reading comes from, from the preferred one."""

    METEO3R = "meteo3r"
    """The Meteo 3R app of Arpa Piemonte: every 30 minutes, ~40 minutes late."""
    ARPA_WEBSITE = "arpa_website"
    """The files of the Arpa website: hourly, ~40 minutes late."""
    ARPA_REALTIME = "arpa_realtime"
    """The api_realtime of Arpa Piemonte: hourly, ~3 h 40 min late."""

    @property
    def priority(self) -> int:
        """Return the rank of the source: 0 for the preferred one."""
        return list(Source).index(self)


class LevelStatus(StrEnum):
    """The water level against the thresholds of the station."""

    NORMAL = "normal"
    PRE_ALARM = "pre_alarm"
    GUARD = "guard"
    DANGER = "danger"


FLOOD_RISK_STATUSES: Final = frozenset(
    {LevelStatus.PRE_ALARM, LevelStatus.GUARD, LevelStatus.DANGER}
)
"""The level statuses that are a flood risk: from the pre-alarm threshold up,
the first one Arpa Piemonte sets on a hydrometer (the user's choice)."""


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Alert thresholds of a hydrometer, in metres; any may be missing."""

    pre_alarm: float | None = None
    guard: float | None = None
    danger: float | None = None

    @property
    def known(self) -> bool:
        """Return whether at least one threshold is known."""
        return any(
            value is not None for value in (self.pre_alarm, self.guard, self.danger)
        )

    def status(self, level: float) -> LevelStatus | None:
        """Return the highest threshold the level reaches; None without any."""
        if not self.known:
            return None
        for status, limit in (
            (LevelStatus.DANGER, self.danger),
            (LevelStatus.GUARD, self.guard),
            (LevelStatus.PRE_ALARM, self.pre_alarm),
        ):
            if limit is not None and level >= limit:
                return status
        return LevelStatus.NORMAL

    def as_dict(self) -> dict[str, float | None]:
        """Return the thresholds as config entry data."""
        return {"pre_alarm": self.pre_alarm, "guard": self.guard, "danger": self.danger}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Thresholds:
        """Return the thresholds of config entry data."""
        data = data or {}
        return cls(data.get("pre_alarm"), data.get("guard"), data.get("danger"))


@dataclass(frozen=True, slots=True)
class Measurement:
    """A reading of a quantity, and where it comes from."""

    value: float
    measured_at: datetime
    """Time of the measurement, in UTC: not when it was downloaded."""
    source: Source


@dataclass(frozen=True, slots=True)
class Reading:
    """A value of a series, at the time it was measured."""

    time: datetime
    """Time of the measurement, in UTC."""
    value: float


type Series = tuple[Reading, ...]
"""The readings of a quantity, from the oldest, at strictly increasing times."""


@dataclass(frozen=True, slots=True)
class StationSnapshot:
    """What a station shows: the latest reading of each quantity, and the series.

    It holds nothing that changes without a new reading (no time of download,
    no host), so an update without new readings is equal to the previous one
    and writes nothing.
    """

    measurements: Mapping[Quantity, Measurement] = field(default_factory=dict)
    thresholds: Thresholds | None = None
    series: Mapping[Quantity, Series] = field(default_factory=dict)
    """The recent readings of each quantity: those of Meteo 3R, 3 to 4 days
    every 30 minutes, and of the website for the pressure and the solar
    radiation, every hour. Kept as they were while their source does not
    answer."""

    @property
    def source(self) -> Source | None:
        """Return the slowest source among the readings Meteo 3R can give.

        The pressure and the solar radiation always come from the website:
        they would hide whether Meteo 3R answers. None without any reading.
        """
        website_only = set(WEBSITE_QUANTITIES.values())
        return max(
            (
                measurement.source
                for quantity, measurement in self.measurements.items()
                if quantity not in website_only
            ),
            key=lambda source: source.priority,
            default=None,
        )

    @property
    def measured_at(self) -> datetime | None:
        """Return the time of the newest reading; None without any."""
        return max(
            (measurement.measured_at for measurement in self.measurements.values()),
            default=None,
        )

    @property
    def level_status(self) -> LevelStatus | None:
        """Return the level against the thresholds; None without either."""
        level = self.measurements.get(Quantity.LEVEL)
        if level is None or self.thresholds is None:
            return None
        return self.thresholds.status(level.value)


def municipality_unique_id(municipality_code: str) -> str:
    """Return the unique ID of the entry of a municipality ("ISTAT_096050")."""
    return f"{MUNICIPALITY_ID_PREFIX}{municipality_code}"


def station_unique_id(station_code: str) -> str:
    """Return the unique ID of a station ("PIE_188"), of its device and entities."""
    return f"{STATION_ID_PREFIX}{station_code}"


@dataclass(frozen=True, slots=True)
class Position:
    """A position, WGS84."""

    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class StationConfig:
    """A station, as its config subentry stores it."""

    station_code: str
    name: str
    sensor_id: str | None
    sensor_letters: str
    thresholds: Thresholds
    website_params: tuple[str, ...] | None = None
    """The files of the station on the Arpa website, sorted; None when unknown."""
    position: Position | None = None
    """Where the station is, as the list of the stations gives it; None when
    unknown."""

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> StationConfig:
        """Return the station of the data of its config subentry.

        A station added before its files on the website were stored has none:
        its letters stand in for them. One added before its position was
        stored has the position of the list of 2026-11-17 (``STATION_PLACES``).
        """
        code = data[CONF_STATION_CODE]
        params = data.get(CONF_WEBSITE_PARAMS)
        position: Position | None = None
        if data.get(CONF_LATITUDE) is not None and data.get(CONF_LONGITUDE) is not None:
            position = Position(data[CONF_LATITUDE], data[CONF_LONGITUDE])
        elif (place := STATION_PLACES.get(code)) is not None:
            position = Position(place.latitude, place.longitude)
        return cls(
            station_code=code,
            name=data[CONF_STATION_NAME],
            sensor_id=data.get(CONF_SENSOR_ID),
            sensor_letters=data.get(CONF_SENSOR_LETTERS, ""),
            thresholds=Thresholds.from_dict(data.get(CONF_THRESHOLDS)),
            website_params=None if params is None else tuple(sorted(params)),
            position=position,
        )

    def as_data(self) -> dict[str, Any]:
        """Return the station as the data of its config subentry."""
        return {
            CONF_STATION_CODE: self.station_code,
            CONF_STATION_NAME: self.name,
            CONF_SENSOR_ID: self.sensor_id,
            CONF_SENSOR_LETTERS: self.sensor_letters,
            CONF_THRESHOLDS: self.thresholds.as_dict(),
            CONF_WEBSITE_PARAMS: (
                None if self.website_params is None else list(self.website_params)
            ),
            CONF_LATITUDE: None if self.position is None else self.position.latitude,
            CONF_LONGITUDE: None if self.position is None else self.position.longitude,
        }

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the station, of its device and entities."""
        return station_unique_id(self.station_code)

    @property
    def quantities(self) -> tuple[Quantity, ...]:
        """Return the quantities of the station, from its sensors, in order.

        The pressure and the solar radiation need a file on the website: those
        its list names, or else those of the letters of the sensors.
        """
        found = {
            quantity
            for letter in self.sensor_letters.upper()
            for quantity in SENSOR_QUANTITIES.get(letter, ())
        }
        website_only = set(WEBSITE_QUANTITIES.values())
        if self.sensor_id is None:
            found -= website_only
        elif self.website_params is not None:
            found -= website_only
            found |= {
                WEBSITE_QUANTITIES[param]
                for param in self.website_params
                if param in WEBSITE_QUANTITIES
            }
        return tuple(quantity for quantity in Quantity if quantity in found)

    @property
    def has_level(self) -> bool:
        """Return whether the station measures a water level."""
        return Quantity.LEVEL in self.quantities
