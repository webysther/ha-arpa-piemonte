"""Diagnostics of a municipality, of its stations and of its natural risks.

What each source answered for a station, and what it shows; what each source
of the risks gave. Nothing here locates the user: a station and a municipality
are public places. When the risks are taken from the home, what would tell
where it is, its micro-region and its heat-wave city, is redacted, and the
distances of the earthquakes are never given, as three of them would locate
it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Final

from aioarpapiemonte import MunicipalityAlerts
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_MUNICIPALITY_CODE, DOMAIN
from .coordinator import (
    ArpaPiemonteConfigEntry,
    ArpaPiemonteCoordinator,
    MunicipalityRisks,
    RisksCoordinator,
    SourceTracker,
)
from .models import Measurement, Quantity, municipality_unique_id
from .risks import AvalancheDays, NearbyEarthquake, PositionChoice
from .sources import async_get_sources

HOME_PLACES: Final = frozenset({"micro_region", "heat_city", "region", "city"})
"""What tells where the home is, when the risks are taken from it."""


def _readings(measurements: dict[Quantity, Measurement]) -> dict[str, Any]:
    return {
        quantity.value: {
            "value": measurement.value,
            "measured_at": measurement.measured_at.isoformat(),
            "source": measurement.source.value,
        }
        for quantity, measurement in measurements.items()
    }


def _source(tracker: SourceTracker) -> dict[str, Any]:
    return {
        "error": None if tracker.error is None else str(tracker.error),
        "attempted_at": (
            None if tracker.attempted_at is None else tracker.attempted_at.isoformat()
        ),
        "readings": _readings(tracker.measurements),
        "thresholds": None
        if tracker.thresholds is None
        else asdict(tracker.thresholds),
    }


def _station(coordinator: ArpaPiemonteCoordinator) -> dict[str, Any]:
    """Return the diagnostics of a station."""
    snapshot = coordinator.data
    return {
        "station": asdict(coordinator.station),
        "last_update_success": coordinator.last_update_success,
        "shown": None if snapshot is None else _readings(dict(snapshot.measurements)),
        "thresholds": None
        if snapshot is None or snapshot.thresholds is None
        else asdict(snapshot.thresholds),
        # The number of readings of each series of the charts, not the readings
        "series": None
        if snapshot is None
        else {
            quantity.value: len(series) for quantity, series in snapshot.series.items()
        },
        "sources": {
            tracker.source.value: _source(tracker) for tracker in coordinator.trackers
        },
    }


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _alerts(alerts: MunicipalityAlerts) -> dict[str, Any]:
    """Return what the widget of a municipality gave, with the levels by name."""
    return {
        "name": alerts.name,
        "alert": str(alerts.alert),
        # e.g. "idraulico_next_day": "yellow"
        "risks": {f"{item.risk}_{item.day}": str(item.level) for item in alerts.risks},
        "current_danger": str(alerts.current_danger),
        "current_danger_time": _time(alerts.current_danger_time),
        "phase": str(alerts.phase),
        "phase_text": alerts.phase_text,
        "phase_time": _time(alerts.phase_time),
        "bulletin": alerts.bulletin,
        "issued": _time(alerts.issued),
        "issue_day": None if alerts.issue_day is None else alerts.issue_day.isoformat(),
        "next_update": _time(alerts.next_update),
        "zones": list(alerts.zones),
    }


def _date(value: date) -> str:
    return value.isoformat()


def _earthquakes(earthquakes: tuple[NearbyEarthquake, ...]) -> list[dict[str, Any]]:
    """Return the earthquakes within the radius, without their distances."""
    return [
        {
            "id": item.earthquake.id,
            "time": item.earthquake.time.isoformat(),
            "magnitude": item.earthquake.magnitude,
            "district": item.earthquake.district,
            "reviewed": item.earthquake.reviewed,
        }
        for item in earthquakes
    ]


def _avalanches(days: AvalancheDays) -> dict[str, Any]:
    """Return the avalanche danger of each day with a bulletin."""
    return {
        "region": days.region_id,
        "bulletins": {
            _date(day): {
                "danger": str(bulletin.danger),
                "published": _time(bulletin.published),
            }
            for day, bulletin in days.bulletins.items()
        },
    }


def _risk[DataT](
    coordinator: RisksCoordinator[DataT] | None, describe: Callable[[DataT], Any]
) -> dict[str, Any] | None:
    """Return what a source of a risk gave; None when the municipality lacks it."""
    if coordinator is None:
        return None
    return {
        "last_update_success": coordinator.last_update_success,
        "error": None
        if coordinator.last_update_success
        else str(coordinator.last_exception),
        "data": None if coordinator.data is None else describe(coordinator.data),
    }


def _risks(risks: MunicipalityRisks) -> dict[str, Any]:
    """Return the diagnostics of the natural risks of a municipality."""
    place = risks.place
    diagnostics = {
        "place": {
            "position": str(place.choice),
            "located": place.position is not None,
            "micro_region": place.micro_region,
            "heat_city": None if place.heat_city is None else str(place.heat_city),
        },
        "alerts": _risk(risks.alerts, _alerts),
        "earthquakes": _risk(risks.earthquakes, _earthquakes),
        "heat": _risk(
            risks.heat,
            lambda forecast: {
                "city": str(forecast.city),
                "issued": _time(forecast.issued),
                "days": {_date(day.day): str(day.level) for day in forecast.days},
            },
        ),
        "avalanches": _risk(risks.avalanches, _avalanches),
    }
    if place.choice is PositionChoice.HOME:
        return async_redact_data(diagnostics, HOME_PLACES)
    return diagnostics


def _meteo3r_host(hass: HomeAssistant) -> str | None:
    """Return the host of Meteo 3R asked first, shared by every station."""
    host = async_get_sources(hass).meteo3r.active_host
    return None if host is None else host.value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of a municipality: its entry, stations and risks."""
    return {
        "entry": entry.as_dict(),
        "stations": {
            coordinator.station.station_code: _station(coordinator)
            for coordinator in entry.runtime_data.stations.values()
        },
        "risks": _risks(entry.runtime_data.risks),
        "meteo3r_host": _meteo3r_host(hass),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return the diagnostics of the station of a device, or of the risks."""
    risks = municipality_unique_id(entry.data[CONF_MUNICIPALITY_CODE])
    if (DOMAIN, risks) in device.identifiers:
        return {"risks": _risks(entry.runtime_data.risks)}
    coordinator = next(
        coordinator
        for coordinator in entry.runtime_data.stations.values()
        if (DOMAIN, coordinator.station.unique_id) in device.identifiers
    )
    return {"station": _station(coordinator), "meteo3r_host": _meteo3r_host(hass)}
