"""Diagnostics of a municipality and of its stations.

What each source answered for a station, and what it shows. Nothing here
locates the user: a station is a public place, and the integration stores no
other position.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import ArpaPiemonteConfigEntry, ArpaPiemonteCoordinator, SourceTracker
from .models import Measurement, Quantity
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
        "sources": {
            tracker.source.value: _source(tracker) for tracker in coordinator.trackers
        },
    }


def _meteo3r_host(hass: HomeAssistant) -> str | None:
    """Return the host of Meteo 3R asked first, shared by every station."""
    host = async_get_sources(hass).meteo3r.active_host
    return None if host is None else host.value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of a municipality: its entry and every station."""
    return {
        "entry": entry.as_dict(),
        "stations": {
            coordinator.station.station_code: _station(coordinator)
            for coordinator in entry.runtime_data.stations.values()
        },
        "meteo3r_host": _meteo3r_host(hass),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return the diagnostics of the station of a device."""
    coordinator = next(
        coordinator
        for coordinator in entry.runtime_data.stations.values()
        if (DOMAIN, coordinator.station.unique_id) in device.identifiers
    )
    return {"station": _station(coordinator), "meteo3r_host": _meteo3r_host(hass)}
