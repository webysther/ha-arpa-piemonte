"""The readings of a station, from Meteo 3R or, when it fails, the official sources.

Meteo 3R is asked at every update: it is the freshest source, every 30
minutes. When it fails, or a quantity of it is too old, the files of the Arpa
website are asked for the level, temperature, humidity and snow (hourly, about
40 minutes late), and the api_realtime for the rest (hourly, about 3 hours and
40 minutes late). Each quantity shows the newest reading of all; on the same
time, Meteo 3R. The official sources are asked only when they could give a
newer reading than the one shown, and not more often than their pace.

The pressure and the solar radiation only the website gives: as Meteo 3R never
has them, it is asked for them at its pace.

The natural risks of the municipality have coordinators of their own: its
alerts, from its widget on the Arpa website; the earthquakes near it; the
heat waves of a capital; the avalanches of its micro-region, from EAWS.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import partial
from typing import Any

from aioarpapiemonte import (
    AVALANCHE_ATTRIBUTION,
    ArpaPiemonteError,
    ArpaPiemonteNotFoundError,
    HeatCity,
    HeatForecast,
    MunicipalityAlerts,
    ParamSeries,
    RegionBulletin,
)
from aiometeo3r import Meteo3rError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .adapters import (
    REALTIME_FIELDS,
    WEBSITE_PARAMS,
    from_meteo3r,
    from_realtime,
    from_website,
    series_of_meteo3r,
    series_of_website,
    thresholds_of_meteo3r,
    thresholds_of_website,
)
from .const import (
    ATTRIBUTION,
    AVALANCHES_OFF_SEASON_INTERVAL,
    AVALANCHES_UPDATE_INTERVAL,
    CONF_MUNICIPALITY_CODE,
    DOMAIN,
    EARTHQUAKES_UPDATE_INTERVAL,
    HEAT_UPDATE_INTERVAL,
    LOGGER,
    PRIMARY_STALE_AFTER,
    REALTIME_LAG,
    REALTIME_MIN_INTERVAL,
    RISKS_UPDATE_INTERVAL,
    ROME_TZ,
    UPDATE_INTERVAL,
    WEBSITE_LAG,
    WEBSITE_MIN_INTERVAL,
)
from .models import (
    Measurement,
    Position,
    Quantity,
    Series,
    Source,
    StationConfig,
    StationSnapshot,
    Thresholds,
)
from .risks import (
    AvalancheDays,
    NearbyEarthquake,
    PositionChoice,
    RiskDay,
    RiskPlace,
    has_alerts,
    heat_city,
    heat_city_choice,
    italian_date,
    mean_position,
    nearby_earthquakes,
    position_choice,
    radius_km,
)
from .selection import newest, select
from .sources import ArpaSources

type SourceError = Meteo3rError | ArpaPiemonteError


@dataclass(slots=True)
class SourceResult:
    """What a source answered: readings, and thresholds when it has them."""

    measurements: dict[Quantity, Measurement] = field(default_factory=dict)
    thresholds: Thresholds | None = None
    series: dict[Quantity, Series] = field(default_factory=dict)
    """The recent readings of the quantities the source gives them of."""
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
        self.series: dict[Quantity, Series] = {}
        """The latest series of each quantity, kept when the source fails."""
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
        self.series.update(result.series)
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
        snapshot = StationSnapshot(
            dict(self._shown),
            self._thresholds(),
            {**self.meteo3r.series, **self.website.series},
        )
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
        return SourceResult(
            from_meteo3r(data), thresholds_of_meteo3r(data), series_of_meteo3r(data)
        )

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
        result.series = series_of_website(files)
        return result

    async def _fetch_realtime(self) -> SourceResult:
        data = await self._sources.arpa.get_realtime_data(self.station.station_code)
        return SourceResult(from_realtime(data))


class RisksCoordinator[DataT](DataUpdateCoordinator[DataT]):
    """Keep a natural risk of a municipality: its alerts, earthquakes, heat or snow.

    The sources answer ``304 Not Modified`` while they do not change, and the
    data compares by value: an update without news writes nothing. Those
    shown by day follow the days in Italy (:meth:`async_follow_the_days`).
    """

    config_entry: ArpaPiemonteConfigEntry
    attribution: str = ATTRIBUTION
    """The credit of the data, which its entities carry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        sources: ArpaSources,
        kind: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator of a kind of risk of a municipality."""
        self.municipality_code: str = entry.data[CONF_MUNICIPALITY_CODE]
        self._sources = sources
        self._unsub_midnight: CALLBACK_TYPE | None = None
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title} {kind}",
            update_interval=update_interval,
            always_update=False,
        )

    def _failed(self, err: ArpaPiemonteError) -> UpdateFailed:
        """Return the failure of an update, naming the municipality and the error."""
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="risks_update_failed",
            translation_placeholders={
                "municipality": self.config_entry.title,
                "error": str(err),
            },
        )

    @callback
    def async_follow_the_days(self) -> None:
        """Update the entities at the next midnight in Italy, then every midnight.

        They show today and tomorrow: at midnight, tomorrow becomes today
        without a new bulletin, and nothing else would update them.
        """
        tomorrow = italian_date(dt_util.utcnow()) + timedelta(days=1)
        self._unsub_midnight = async_track_point_in_utc_time(
            self.hass,
            self._async_new_day,
            datetime.combine(tomorrow, time(), tzinfo=ROME_TZ),
        )

    @callback
    def _async_new_day(self, now: datetime) -> None:
        """Show the risks of the new day, and wait for the next one."""
        del now
        self.async_follow_the_days()
        self.async_update_listeners()

    async def async_shutdown(self) -> None:
        """Stop the updates, and the change of day."""
        await super().async_shutdown()
        if self._unsub_midnight is not None:
            self._unsub_midnight()
            self._unsub_midnight = None


class AlertsCoordinator(RisksCoordinator[MunicipalityAlerts]):
    """Keep the alerts of a municipality, from its widget on the Arpa website."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, sources: ArpaSources
    ) -> None:
        """Initialize the coordinator of the alerts of the municipality of an entry."""
        super().__init__(hass, entry, sources, "alerts", RISKS_UPDATE_INTERVAL)

    async def _async_update_data(self) -> MunicipalityAlerts:
        """Return the alerts, the danger now and the phase of the municipality."""
        try:
            return await self._sources.arpa.get_municipality_alerts(
                self.municipality_code
            )
        except ArpaPiemonteError as err:
            raise self._failed(err) from err


class EarthquakesCoordinator(RisksCoordinator[tuple[NearbyEarthquake, ...]]):
    """Keep the earthquakes of the last 30 days within a radius of a position."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        sources: ArpaSources,
        position: Position,
        radius: float,
    ) -> None:
        """Initialize the coordinator of the earthquakes near a position, in km."""
        self.position = position
        self.radius = radius
        super().__init__(
            hass, entry, sources, "earthquakes", EARTHQUAKES_UPDATE_INTERVAL
        )

    async def _async_update_data(self) -> tuple[NearbyEarthquake, ...]:
        """Return the earthquakes within the radius, the newest first."""
        try:
            earthquakes = await self._sources.arpa.get_earthquakes()
        except ArpaPiemonteError as err:
            raise self._failed(err) from err
        return nearby_earthquakes(earthquakes, self.position, self.radius)


class HeatCoordinator(RisksCoordinator[HeatForecast]):
    """Keep the heat-wave bulletin of one of the 8 capitals of province."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        sources: ArpaSources,
        city: HeatCity,
    ) -> None:
        """Initialize the coordinator of the heat waves of a city."""
        self.city = city
        super().__init__(hass, entry, sources, "heat", HEAT_UPDATE_INTERVAL)

    async def _async_update_data(self) -> HeatForecast:
        """Return the bulletin of the city: out of season, the last one."""
        try:
            return await self._sources.arpa.get_heat_forecast(self.city)
        except ArpaPiemonteError as err:
            raise self._failed(err) from err


class AvalanchesCoordinator(RisksCoordinator[AvalancheDays]):
    """Keep the avalanche bulletins of a micro-region, today and tomorrow.

    Asked every hour while there is a bulletin for today, and every 6 hours
    out of season, when there is none.
    """

    attribution = AVALANCHE_ATTRIBUTION

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        sources: ArpaSources,
        region_id: str,
    ) -> None:
        """Initialize the coordinator of the avalanches of a micro-region of EAWS."""
        self.region_id = region_id
        super().__init__(hass, entry, sources, "avalanches", AVALANCHES_UPDATE_INTERVAL)

    async def _async_update_data(self) -> AvalancheDays:
        """Return the bulletins of the micro-region of today and tomorrow in Italy.

        A day without a bulletin has none: out of season, or tomorrow before
        it is published, at about 17:00.
        """
        today = italian_date(dt_util.utcnow())
        bulletins: dict[date, RegionBulletin] = {}
        in_season = False
        for day in RiskDay:
            when = day.date(today)
            try:
                bulletin = await self._sources.arpa.get_avalanche_bulletin(when)
            except ArpaPiemonteNotFoundError:
                continue
            except ArpaPiemonteError as err:
                raise self._failed(err) from err
            in_season = in_season or day is RiskDay.TODAY
            if (region := bulletin.of_region(self.region_id)) is not None:
                bulletins[when] = region
        self.update_interval = (
            AVALANCHES_UPDATE_INTERVAL if in_season else AVALANCHES_OFF_SEASON_INTERVAL
        )
        return AvalancheDays(self.region_id, bulletins)


@dataclass(frozen=True, slots=True)
class MunicipalityRisks:
    """The natural risks of a municipality: where from, and their coordinators.

    A risk the municipality does not have has no coordinator: the alerts
    outside Piedmont, the earthquakes and the avalanches without a position,
    the avalanches outside the micro-regions, the heat without a city.
    """

    place: RiskPlace
    alerts: AlertsCoordinator | None = None
    earthquakes: EarthquakesCoordinator | None = None
    heat: HeatCoordinator | None = None
    avalanches: AvalanchesCoordinator | None = None

    @property
    def coordinators(self) -> tuple[RisksCoordinator[Any], ...]:
        """Return the coordinators of the risks the municipality has."""
        return tuple(
            coordinator
            for coordinator in (
                self.alerts,
                self.earthquakes,
                self.heat,
                self.avalanches,
            )
            if coordinator is not None
        )

    @property
    def daily(self) -> tuple[RisksCoordinator[Any], ...]:
        """Return the coordinators of the risks shown by day: not the earthquakes."""
        return tuple(
            coordinator
            for coordinator in (self.alerts, self.heat, self.avalanches)
            if coordinator is not None
        )


async def async_risk_place(
    hass: HomeAssistant,
    entry: ConfigEntry,
    sources: ArpaSources,
    stations: Iterable[StationConfig],
) -> RiskPlace:
    """Return where the risks of a municipality are taken from, by its options.

    The position is the mean of its stations, or the home of Home Assistant.
    The micro-region of the avalanches is that of the position or, when the
    mean of the stations is in none, that of the first station in one: the
    mean of a station in the mountains and one in the valley can fall outside
    them (6 of the 106 municipalities with a station in a micro-region, in the
    list of 2026-11-17). aioarpapiemonte ships the micro-regions of EAWS:
    reading them asks no source.
    """
    choice = position_choice(entry.options)
    candidates: list[Position]
    position: Position | None
    if choice is PositionChoice.HOME:
        home = Position(hass.config.latitude, hass.config.longitude)
        position = home
        candidates = [home]
    else:
        known = [station.position for station in stations if station.position]
        position = mean_position(known)
        candidates = [] if position is None else [position, *known]
    micro_region: str | None = None
    for candidate in candidates:
        micro_region = await sources.arpa.get_micro_region(
            candidate.latitude, candidate.longitude
        )
        if micro_region is not None:
            break
    city = heat_city(
        heat_city_choice(entry.options), entry.data[CONF_MUNICIPALITY_CODE], position
    )
    return RiskPlace(choice, position, micro_region, city)


def municipality_risks(
    hass: HomeAssistant, entry: ConfigEntry, sources: ArpaSources, place: RiskPlace
) -> MunicipalityRisks:
    """Return the coordinators of the risks a municipality has, from its place."""
    return MunicipalityRisks(
        place,
        alerts=(
            AlertsCoordinator(hass, entry, sources)
            if has_alerts(entry.data[CONF_MUNICIPALITY_CODE])
            else None
        ),
        earthquakes=(
            None
            if place.position is None
            else EarthquakesCoordinator(
                hass, entry, sources, place.position, radius_km(entry.options)
            )
        ),
        heat=(
            None
            if place.heat_city is None
            else HeatCoordinator(hass, entry, sources, place.heat_city)
        ),
        avalanches=(
            None
            if place.micro_region is None
            else AvalanchesCoordinator(hass, entry, sources, place.micro_region)
        ),
    )


@dataclass(frozen=True, slots=True)
class ArpaPiemonteData:
    """What the entry of a municipality keeps while it is loaded."""

    stations: Mapping[str, ArpaPiemonteCoordinator]
    """The coordinator of each station, by the ID of its subentry."""
    risks: MunicipalityRisks
    """The natural risks of the municipality."""


type ArpaPiemonteConfigEntry = ConfigEntry[ArpaPiemonteData]
