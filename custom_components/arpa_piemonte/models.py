"""The data of a station, whatever source gave it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final

from .const import (
    CONF_SENSOR_ID,
    CONF_SENSOR_LETTERS,
    CONF_STATION_CODE,
    CONF_THRESHOLDS,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


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
}
"""The quantities of each letter of the sensors of a station.

Measured on 2026-11-17 on the 374 stations: one station had a series without
its letter, 23 a letter without readings (a sensor that does not answer).
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
class StationSnapshot:
    """What a station shows: the latest reading of each quantity.

    It holds nothing that changes without a new reading (no time of download,
    no host), so an update without new readings is equal to the previous one
    and writes nothing.
    """

    measurements: Mapping[Quantity, Measurement] = field(default_factory=dict)
    thresholds: Thresholds | None = None

    @property
    def source(self) -> Source | None:
        """Return the slowest source among the readings shown; None without any."""
        return max(
            (measurement.source for measurement in self.measurements.values()),
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


@dataclass(frozen=True, slots=True)
class StationConfig:
    """A station, as its config entry stores it."""

    station_code: str
    sensor_id: str | None
    sensor_letters: str
    thresholds: Thresholds

    @classmethod
    def of(cls, entry: ConfigEntry) -> StationConfig:
        """Return the station of a config entry."""
        return cls(
            station_code=entry.data[CONF_STATION_CODE],
            sensor_id=entry.data.get(CONF_SENSOR_ID),
            sensor_letters=entry.data.get(CONF_SENSOR_LETTERS, ""),
            thresholds=Thresholds.from_dict(entry.data.get(CONF_THRESHOLDS)),
        )

    @property
    def quantities(self) -> tuple[Quantity, ...]:
        """Return the quantities of the station, from its sensors, in order."""
        found = {
            quantity
            for letter in self.sensor_letters.upper()
            for quantity in SENSOR_QUANTITIES.get(letter, ())
        }
        return tuple(quantity for quantity in Quantity if quantity in found)

    @property
    def has_level(self) -> bool:
        """Return whether the station measures a water level."""
        return Quantity.LEVEL in self.quantities
