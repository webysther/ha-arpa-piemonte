"""Diagnostics of a municipality, of its stations and of its natural risks.

What each source answered for a station, and what it shows; what the widget
of the municipality gave. Nothing here locates the user: a station and a
municipality are public places, and the integration stores no other position.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from aioarpapiemonte import MunicipalityAlerts
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import (
    ArpaPiemonteConfigEntry,
    ArpaPiemonteCoordinator,
    MunicipalityRisksCoordinator,
    SourceTracker,
)
from .models import Measurement, Quantity, municipality_unique_id
from .sources import async_get_sources


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


def _risks(coordinator: MunicipalityRisksCoordinator) -> dict[str, Any]:
    """Return the diagnostics of the natural risks of a municipality."""
    return {
        "municipality_code": coordinator.municipality_code,
        "last_update_success": coordinator.last_update_success,
        "error": None
        if coordinator.last_update_success
        else str(coordinator.last_exception),
        "alerts": None if coordinator.data is None else _alerts(coordinator.data),
    }


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
    risks = entry.runtime_data.risks
    if (DOMAIN, municipality_unique_id(risks.municipality_code)) in device.identifiers:
        return {"risks": _risks(risks)}
    coordinator = next(
        coordinator
        for coordinator in entry.runtime_data.stations.values()
        if (DOMAIN, coordinator.station.unique_id) in device.identifiers
    )
    return {"station": _station(coordinator), "meteo3r_host": _meteo3r_host(hass)}
