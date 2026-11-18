"""The natural risks of a municipality, as its entities show them (pure).

The widget of the municipality on the Arpa website gives the level of each
risk on the day the alert bulletin is issued and on the next one, the danger
now, and the operational phase the municipality declared. The entities show
the risks of today and tomorrow in Italy: the bulletin is issued around 13:00,
so in the morning its first day is yesterday, today is its second, and
tomorrow is not known until the next bulletin.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any, Final

from aioarpapiemonte import AlertLevel, MunicipalityAlerts, OperationalPhase, RiskType
from aioarpapiemonte.urls import municipality_alerts_url

from .const import CONF_WARNING_LEVEL, DEFAULT_WARNING_LEVEL, ROME_TZ


class RiskDay(StrEnum):
    """A day of the risks of a municipality; the value ends the keys of its entities."""

    TODAY = "today"
    TOMORROW = "tomorrow"

    def date(self, today: date) -> date:
        """Return the date of the day, from the date of today in Italy."""
        return today + timedelta(days=list(RiskDay).index(self))


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


def italian_date(now: datetime) -> date:
    """Return the date in Italy at a time: the day of the bulletin it falls on."""
    return now.astimezone(ROME_TZ).date()


def warning_level(options: Mapping[str, Any]) -> AlertLevel:
    """Return the warning level of the options of an entry; yellow without one."""
    chosen = options.get(CONF_WARNING_LEVEL)
    level = chosen if chosen in WARNING_LEVELS else DEFAULT_WARNING_LEVEL
    return AlertLevel[level.upper()]


def level_state(level: AlertLevel) -> str | None:
    """Return the state of a level; None when it is not known."""
    return None if level is AlertLevel.UNKNOWN else str(level)


def phase_state(phase: OperationalPhase) -> str | None:
    """Return the state of an operational phase; None for a text not known."""
    return None if phase is OperationalPhase.UNKNOWN else str(phase)


def highest_alert(alerts: MunicipalityAlerts, today: date) -> AlertLevel:
    """Return the highest level of the risks today and tomorrow in Italy.

    UNKNOWN when the bulletin covers neither day.
    """
    return max(alerts.highest_on(day.date(today)) for day in RiskDay)


def widget_page_url(municipality_code: str) -> str:
    """Return the page of the widget of a municipality on the Arpa website.

    The page shows the risks of the municipality as Arpa does: the folder of
    the data of the widget (checked on 2026-11-18).
    """
    return municipality_alerts_url(municipality_code).removesuffix("index.json")
