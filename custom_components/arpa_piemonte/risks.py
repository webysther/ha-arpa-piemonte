"""The natural risks of a municipality, as its entities show them (pure).

The widget of the municipality on the Arpa website gives the level of each
risk on the day the alert bulletin is issued and on the next one, the danger
now, and the operational phase the municipality declared. The entities show
the risks of today and tomorrow in Italy: the bulletin is issued around 13:00,
so in the morning its first day is yesterday, today is its second, and
tomorrow is not known until the next bulletin.

The earthquakes, the avalanches and the nearest heat-wave city are those of a
position: the stations of the municipality, or the home of Home Assistant, as
its options choose.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any, Final

from aioarpapiemonte import (
    AlertLevel,
    AvalancheDanger,
    Earthquake,
    HeatCity,
    HeatLevel,
    MunicipalityAlerts,
    OperationalPhase,
    RegionBulletin,
    RiskType,
)
from aioarpapiemonte.urls import municipality_alerts_url

from .const import (
    CONF_HEAT_CITY,
    CONF_POSITION,
    CONF_RADIUS,
    CONF_WARNING_LEVEL,
    DEFAULT_HEAT_CITY,
    DEFAULT_POSITION,
    DEFAULT_RADIUS,
    DEFAULT_WARNING_LEVEL,
    ROME_TZ,
)
from .models import Position


class RiskDay(StrEnum):
    """A day of the risks of a municipality; the value ends the keys of its entities."""

    TODAY = "today"
    TOMORROW = "tomorrow"

    def date(self, today: date) -> date:
        """Return the date of the day, from the date of today in Italy."""
        return today + timedelta(days=list(RiskDay).index(self))


class PositionChoice(StrEnum):
    """Where the risks of a municipality are taken from, as its options say."""

    STATIONS = "stations"
    """The mean position of the stations of the municipality."""
    HOME = "home"
    """The home of Home Assistant."""


class HeatCityChoice(StrEnum):
    """Which capital gives the heat waves of a municipality, as its options say."""

    PROVINCE = "province"
    """The capital of its province."""
    NEAREST = "nearest"
    """The capital nearest to the position."""


RISK_KEYS: Final[Mapping[RiskType, str]] = {
    RiskType.HYDROGEOLOGICAL: "hydrogeological",
    RiskType.HYDRAULIC: "hydraulic",
    RiskType.THUNDERSTORMS: "thunderstorm",
    RiskType.SNOW: "snow",
    RiskType.AVALANCHES: "avalanche",
}
"""The key of each risk in the keys of its entities, in the order of the widget:
``hydraulic_risk_today``, as DPC names the binary sensors of its three risks."""

ALERT_LEVELS: Final = [
    str(level) for level in AlertLevel if level is not AlertLevel.UNKNOWN
]
"""The states of a level of the bulletin, and of the danger now: not_evaluated
(white, as the avalanches out of season), green, yellow, orange and red."""

PHASES: Final = [
    str(phase) for phase in OperationalPhase if phase is not OperationalPhase.UNKNOWN
]
"""The states of the operational phase: none, attention, pre_alarm and alarm."""

WARNING_LEVELS: Final = [str(level) for level in AlertLevel if level.is_alert]
"""The warning levels offered in the options: yellow, orange and red. Green, no
alert, would turn the binary sensors on all the time."""

HEAT_LEVELS: Final = [
    str(level) for level in HeatLevel if level is not HeatLevel.UNKNOWN
]
"""The states of the heat of a day: green (Arpa's level 0, no discomfort),
yellow, orange and red (its levels 1 to 3)."""

AVALANCHE_DANGERS: Final = [
    str(danger) for danger in AvalancheDanger if danger is not AvalancheDanger.UNKNOWN
]
"""The states of the avalanche danger: no_snow, then the European scale, low,
moderate, considerable, high and very_high."""

PIEDMONT_PROVINCES: Final = frozenset(city.province_code for city in HeatCity)
"""The ISTAT codes of the 8 provinces of Piedmont, those of the 8 capitals of
the heat-wave bulletins. The alert bulletin and its widget cover their
municipalities only: Palestro, in the province of Pavia, has a station of Arpa
Piemonte but no widget (404, checked on 2026-11-18)."""

MAX_RADIUS: Final = 400
"""The largest radius of the earthquakes offered, in km. The epicentres of the
list of Arpa went from 43.9 to 46.6 N and from 6.6 to 9.8 E (388 km across,
on 2026-11-17): 400 km takes them all from anywhere."""


def italian_date(now: datetime) -> date:
    """Return the date in Italy at a time: the day of the bulletin it falls on."""
    return now.astimezone(ROME_TZ).date()


def warning_level(options: Mapping[str, Any]) -> AlertLevel:
    """Return the warning level of the options of an entry; yellow without one."""
    chosen = options.get(CONF_WARNING_LEVEL)
    level = chosen if chosen in WARNING_LEVELS else DEFAULT_WARNING_LEVEL
    return AlertLevel[level.upper()]


def position_choice(options: Mapping[str, Any]) -> PositionChoice:
    """Return where the options take the risks from; the stations without one."""
    chosen = options.get(CONF_POSITION)
    return PositionChoice(chosen if chosen in set(PositionChoice) else DEFAULT_POSITION)


def heat_city_choice(options: Mapping[str, Any]) -> HeatCityChoice:
    """Return which capital the options take the heat from; the province without one."""
    chosen = options.get(CONF_HEAT_CITY)
    return HeatCityChoice(
        chosen if chosen in set(HeatCityChoice) else DEFAULT_HEAT_CITY
    )


def radius_km(options: Mapping[str, Any]) -> float:
    """Return the radius of the earthquakes of the options; 50 km without one."""
    return float(options.get(CONF_RADIUS, DEFAULT_RADIUS))


def has_alerts(municipality_code: str) -> bool:
    """Return whether the alert bulletin covers a municipality: one of Piedmont."""
    return municipality_code[:3] in PIEDMONT_PROVINCES


def mean_position(positions: Iterable[Position]) -> Position | None:
    """Return the mean of positions, as of the stations of a municipality.

    The stations of a municipality are a few km apart: their mean stands for
    it. None without any position.
    """
    known = list(positions)
    if not known:
        return None
    return Position(
        sum(position.latitude for position in known) / len(known),
        sum(position.longitude for position in known) / len(known),
    )


def heat_city(
    choice: HeatCityChoice, municipality_code: str, position: Position | None
) -> HeatCity | None:
    """Return the capital whose heat-wave bulletin a municipality shows.

    The capital of its province, or the nearest to the position. A
    municipality outside Piedmont (Palestro) takes the nearest one, and
    without a position, the capital of the province stands in. None when
    neither is known.
    """
    capital = HeatCity.capital_of(municipality_code)
    if choice is HeatCityChoice.PROVINCE and capital is not None:
        return capital
    if position is not None:
        return HeatCity.nearest(position.latitude, position.longitude)
    return capital


def level_state(level: AlertLevel) -> str | None:
    """Return the state of a level; None when it is not known."""
    return None if level is AlertLevel.UNKNOWN else str(level)


def phase_state(phase: OperationalPhase) -> str | None:
    """Return the state of an operational phase; None for a text not known."""
    return None if phase is OperationalPhase.UNKNOWN else str(phase)


def heat_state(level: HeatLevel | None) -> str | None:
    """Return the state of the heat of a day; None when it is not known."""
    return None if level is None or level is HeatLevel.UNKNOWN else str(level)


def danger_state(danger: AvalancheDanger) -> str | None:
    """Return the state of an avalanche danger; None when it is not known."""
    return None if danger is AvalancheDanger.UNKNOWN else str(danger)


def highest_alert(alerts: MunicipalityAlerts, today: date) -> AlertLevel:
    """Return the highest level of the risks today and tomorrow in Italy.

    UNKNOWN when the bulletin covers neither day.
    """
    return max(alerts.highest_on(day.date(today)) for day in RiskDay)


@dataclass(frozen=True, slots=True)
class RiskPlace:
    """Where the natural risks of a municipality are taken from."""

    choice: PositionChoice
    """What the options chose: the stations or the home."""
    position: Position | None
    """The position of the earthquakes and the avalanches; None for the
    stations of a municipality without any."""
    micro_region: str | None
    """The micro-region of the avalanches of the position; None outside them."""
    heat_city: HeatCity | None
    """The capital whose heat waves are shown; None when none is known."""


@dataclass(frozen=True, slots=True)
class NearbyEarthquake:
    """An earthquake within the radius of the position, and how far it is."""

    earthquake: Earthquake
    distance_km: float
    """Distance from the position to the epicentre, in km."""


def nearby_earthquakes(
    earthquakes: Iterable[Earthquake], position: Position, radius: float
) -> tuple[NearbyEarthquake, ...]:
    """Return the earthquakes within a radius of a position, in their order."""
    nearby = (
        NearbyEarthquake(
            earthquake, earthquake.distance_km(position.latitude, position.longitude)
        )
        for earthquake in earthquakes
    )
    return tuple(item for item in nearby if item.distance_km <= radius)


@dataclass(frozen=True, slots=True)
class AvalancheDays:
    """The avalanche bulletins of a micro-region, by the day in Italy they are for.

    A day without a bulletin, out of season or before it is published, has
    none.
    """

    region_id: str
    """The micro-region of EAWS ("IT-21-TO-03")."""
    bulletins: Mapping[date, RegionBulletin]

    def danger_on(self, day: date) -> AvalancheDanger:
        """Return the highest danger of a day; UNKNOWN without its bulletin."""
        bulletin = self.bulletins.get(day)
        return AvalancheDanger.UNKNOWN if bulletin is None else bulletin.danger


def widget_page_url(municipality_code: str) -> str:
    """Return the page of the widget of a municipality on the Arpa website.

    The page shows the risks of the municipality as Arpa does: the folder of
    the data of the widget (checked on 2026-11-18).
    """
    return municipality_alerts_url(municipality_code).removesuffix("index.json")
