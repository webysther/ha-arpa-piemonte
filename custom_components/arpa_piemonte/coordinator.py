"""The readings of a station, from Meteo 3R or, when it fails, the official sources.

Meteo 3R is asked at every update: it is the freshest source, every 30
minutes. When it fails, or a quantity of it is too old, the files of the Arpa
website are asked for the level, temperature, humidity and snow (hourly, about
40 minutes late), and the api_realtime for the rest (hourly, about 3 hours and
40 minutes late). Each quantity shows the newest reading of all; on the same
time, Meteo 3R. The official sources are asked only when they could give a
newer reading than the one shown, and not more often than their pace.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial

from aioarpapiemonte import ArpaPiemonteError, ParamSeries
from aiometeo3r import Meteo3rError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .adapters import (
    REALTIME_FIELDS,
    WEBSITE_PARAMS,
    from_meteo3r,
    from_realtime,
    from_website,
    thresholds_of_meteo3r,
    thresholds_of_website,
)
from .const import (
    DOMAIN,
    LOGGER,
    PRIMARY_STALE_AFTER,
    REALTIME_LAG,
    REALTIME_MIN_INTERVAL,
    UPDATE_INTERVAL,
    WEBSITE_LAG,
    WEBSITE_MIN_INTERVAL,
)
from .models import (
    Measurement,
    Quantity,
    Source,
    StationConfig,
    StationSnapshot,
    Thresholds,
)
from .selection import newest, select
from .sources import ArpaSources

type SourceError = Meteo3rError | ArpaPiemonteError


@dataclass(slots=True)
class SourceResult:
    """What a source answered: readings, and thresholds when it has them."""

    measurements: dict[Quantity, Measurement] = field(default_factory=dict)
    thresholds: Thresholds | None = None
    error: SourceError | None = None
    """The first failure, when only part of the source answered."""


class SourceTracker:
    """The latest readings of a source for a station, kept when it fails."""

    def __init__(self, station: str, source: Source, min_interval: timedelta) -> None:
        """Initialize the tracker of a source."""
        self._station = station
        self.source = source
        self._min_interval = min_interval
        self.measurements: dict[Quantity, Measurement] = {}
        self.thresholds: Thresholds | None = None
        self.error: SourceError | None = None
        """Why the last request failed; None when it succeeded."""
        self.attempted_at: datetime | None = None
        """When the source was last asked, failed or not."""

    def is_due(self, now: datetime) -> bool:
        """Return whether the source may be asked again."""
        return (
            self.attempted_at is None or now - self.attempted_at >= self._min_interval
        )

    async def refresh(
        self, fetch: Callable[[], Awaitable[SourceResult]], now: datetime
    ) -> None:
        """Ask the source; on failure keep its previous readings."""
        self.attempted_at = now
        try:
            result = await fetch()
        except (Meteo3rError, ArpaPiemonteError) as err:
            self._failed(err)
            return
        self.measurements.update(result.measurements)
        if result.thresholds is not None:
            self.thresholds = result.thresholds
        if result.error is not None:
            self._failed(result.error)
            return
        if self.error is not None:
            LOGGER.info("[%s] %s answers again", self._station, self.source)
        self.error = None

    def _failed(self, err: SourceError) -> None:
        if self.error is None:
            LOGGER.warning(
                "[%s] %s did not answer: %s", self._station, self.source, err
            )
        self.error = err


class ArpaPiemonteCoordinator(DataUpdateCoordinator[StationSnapshot]):
    """Keep the latest readings of a station."""

    config_entry: ArpaPiemonteConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        station: StationConfig,
        sources: ArpaSources,
    ) -> None:
        """Initialize the coordinator of a station of the entry of its municipality."""
        self.station = station
        self._sources = sources
        self.meteo3r = SourceTracker(station.name, Source.METEO3R, timedelta(0))
        self.website = SourceTracker(
            station.name, Source.ARPA_WEBSITE, WEBSITE_MIN_INTERVAL
        )
        self.realtime = SourceTracker(
            station.name, Source.ARPA_REALTIME, REALTIME_MIN_INTERVAL
        )
        self._shown: dict[Quantity, Measurement] = {}
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {station.name}",
            update_interval=UPDATE_INTERVAL,
            # The snapshot compares by value: an update without new readings
            # (a 304 of Meteo 3R) writes nothing
            always_update=False,
        )

    @property
    def trackers(self) -> tuple[SourceTracker, ...]:
        """Return the trackers of the sources, from the preferred one."""
        return (self.meteo3r, self.website, self.realtime)

    async def _async_update_data(self) -> StationSnapshot:
        """Return the latest readings of the station."""
        now = dt_util.utcnow()
        quantities = self.station.quantities
        await self.meteo3r.refresh(self._fetch_meteo3r, now)

        website = [
            quantity
            for quantity in quantities
            if quantity in WEBSITE_PARAMS
            and self._needs_fallback(quantity, now)
            and self._could_improve(quantity, WEBSITE_LAG, now)
        ]
        if website and self.station.sensor_id and self.website.is_due(now):
            await self.website.refresh(partial(self._fetch_website, website), now)

        if any(
            quantity in REALTIME_FIELDS
            and self._needs_fallback(quantity, now)
            and self._could_improve(quantity, REALTIME_LAG, now)
            for quantity in quantities
        ) and self.realtime.is_due(now):
            await self.realtime.refresh(self._fetch_realtime, now)

        self._shown = select(
            (tracker.measurements for tracker in self.trackers),
            self._shown,
            quantities,
            now,
        )
        snapshot = StationSnapshot(dict(self._shown), self._thresholds())
        errors = [tracker.error for tracker in self.trackers if tracker.error]
        if not snapshot.measurements and errors:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(errors[0])},
            )
        return snapshot

    def _needs_fallback(self, quantity: Quantity, now: datetime) -> bool:
        """Return whether Meteo 3R does not give a recent reading of a quantity."""
        reading = self.meteo3r.measurements.get(quantity)
        return (
            self.meteo3r.error is not None
            or reading is None
            or now - reading.measured_at > PRIMARY_STALE_AFTER
        )

    def _could_improve(self, quantity: Quantity, lag: timedelta, now: datetime) -> bool:
        """Return whether a source this late could give a newer reading."""
        best = newest(self._candidates(quantity), now)
        return best is None or now - best.measured_at > lag

    def _candidates(self, quantity: Quantity) -> Iterable[Measurement]:
        for tracker in self.trackers:
            if quantity in tracker.measurements:
                yield tracker.measurements[quantity]
        if quantity in self._shown:
            yield self._shown[quantity]

    def _thresholds(self) -> Thresholds | None:
        """Return the thresholds of the newest source that gave them."""
        if not self.station.has_level:
            return None
        for thresholds in (self.meteo3r.thresholds, self.website.thresholds):
            if thresholds is not None and thresholds.known:
                return thresholds
        return self.station.thresholds

    async def _fetch_meteo3r(self) -> SourceResult:
        data = await self._sources.meteo3r.get_station_data(self.station.station_code)
        return SourceResult(from_meteo3r(data), thresholds_of_meteo3r(data))

    async def _fetch_website(self, quantities: list[Quantity]) -> SourceResult:
        """Return the files of the Arpa website of the quantities, as they answer."""
        assert self.station.sensor_id is not None
        files: list[tuple[Quantity, ParamSeries]] = []
        result = SourceResult()
        for quantity in quantities:
            try:
                series = await self._sources.arpa.get_series(
                    WEBSITE_PARAMS[quantity], self.station.sensor_id
                )
            except ArpaPiemonteError as err:
                result.error = result.error or err
                continue
            files.append((quantity, series))
            if quantity is Quantity.LEVEL:
                result.thresholds = thresholds_of_website(series)
        if result.error is not None and not files:
            raise result.error
        result.measurements = from_website(files)
        return result

    async def _fetch_realtime(self) -> SourceResult:
        data = await self._sources.arpa.get_realtime_data(self.station.station_code)
        return SourceResult(from_realtime(data))


@dataclass(frozen=True, slots=True)
class ArpaPiemonteData:
    """What the entry of a municipality keeps while it is loaded."""

    stations: Mapping[str, ArpaPiemonteCoordinator]
    """The coordinator of each station, by the ID of its subentry."""


type ArpaPiemonteConfigEntry = ConfigEntry[ArpaPiemonteData]
