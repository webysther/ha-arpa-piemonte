"""Diagnostics of a station: what each source answered, and what is shown.

Nothing here locates the user: a station is a public place, and the
integration stores no other position.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import ArpaPiemonteConfigEntry, SourceTracker
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


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of a station."""
    coordinator = entry.runtime_data
    snapshot = coordinator.data
    host = async_get_sources(hass).meteo3r.active_host
    return {
        "entry": entry.as_dict(),
        "station": asdict(coordinator.station),
        "last_update_success": coordinator.last_update_success,
        "shown": _readings(dict(snapshot.measurements)),
        "thresholds": None
        if snapshot.thresholds is None
        else asdict(snapshot.thresholds),
        "sources": {
            tracker.source.value: _source(tracker) for tracker in coordinator.trackers
        },
        "meteo3r_host": None if host is None else host.value,
    }
