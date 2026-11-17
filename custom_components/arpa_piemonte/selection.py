"""Which reading a station shows, among those of its sources. Pure: no I/O."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime

from .const import MAX_CLOCK_SKEW, UNAVAILABLE_AFTER
from .models import Measurement, Quantity


def is_current(measurement: Measurement, now: datetime) -> bool:
    """Return whether a reading can be shown: neither too old nor in the future."""
    return (
        measurement.measured_at <= now + MAX_CLOCK_SKEW
        and now - measurement.measured_at <= UNAVAILABLE_AFTER
    )


def newest(candidates: Iterable[Measurement], now: datetime) -> Measurement | None:
    """Return the newest current reading; on the same time, the preferred source.

    Between two readings of the same time and source, the first one wins: give
    the latest downloads first, so that a reading corrected by Arpa replaces
    the one shown.
    """
    best: Measurement | None = None
    for candidate in candidates:
        if not is_current(candidate, now):
            continue
        if best is None or (candidate.measured_at, -candidate.source.priority) > (
            best.measured_at,
            -best.source.priority,
        ):
            best = candidate
    return best


def select(
    sources: Iterable[Mapping[Quantity, Measurement]],
    shown: Mapping[Quantity, Measurement],
    quantities: Iterable[Quantity],
    now: datetime,
) -> dict[Quantity, Measurement]:
    """Return the reading to show of each quantity.

    The newest current reading of the sources, or the one shown, wins: a
    source that answers with an older reading (a host with an older file)
    never takes the station back in time. A quantity without any current
    reading is left out, and its entity becomes unavailable.
    """
    sources = list(sources)
    selected = {}
    for quantity in quantities:
        candidates = [source[quantity] for source in sources if quantity in source]
        if quantity in shown:
            candidates.append(shown[quantity])
        best = newest(candidates, now)
        if best is not None:
            selected[quantity] = best
    return selected
