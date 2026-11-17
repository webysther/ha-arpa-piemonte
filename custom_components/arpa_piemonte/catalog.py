"""The stations the user can add, by municipality (pure).

The municipality comes first, then its station: Piedmont has 278
municipalities with a station and 62 rivers, and 264 of the 374 stations
measure no river (measured on 2026-11-17). A municipality has 1 to 8
stations, and never two on the same river.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
import unicodedata

from aioarpapiemonte import RealtimeStation
from aiometeo3r import Station

from .models import Thresholds


@dataclass(frozen=True, slots=True)
class Municipality:
    """A municipality with stations of Arpa Piemonte."""

    code: str
    """ISTAT code, the current one ("096050")."""
    name: str
    """Name as Arpa writes it: an accent is an apostrophe ("Mondovi'")."""


@dataclass(frozen=True, slots=True)
class StationChoice:
    """A station the user can add, from the list of Meteo 3R or of the api_realtime."""

    code: str
    name: str
    river: str | None
    """River or lake, in title case ("Sessera"); None without a hydrometer."""
    municipality: Municipality
    latitude: float
    longitude: float
    sensor_letters: str
    thresholds: Thresholds
    sensor_id: str | None = None
    """Identifier on the Arpa website, when the list gives it (the api_realtime)."""

    @classmethod
    def of_meteo3r(cls, station: Station) -> StationChoice:
        """Return a station of the list of Meteo 3R."""
        thresholds = station.thresholds
        return cls(
            code=station.code,
            name=station.name,
            river=station.river.title() if station.river else None,
            municipality=Municipality(station.municipality_code, station.municipality),
            latitude=station.latitude,
            longitude=station.longitude,
            sensor_letters=station.sensor_letters,
            thresholds=Thresholds(
                thresholds.pre_alarm, thresholds.guard, thresholds.danger
            ),
        )

    @classmethod
    def of_realtime(cls, station: RealtimeStation) -> StationChoice:
        """Return a station of the list of the api_realtime, named in capitals."""
        thresholds = station.thresholds
        return cls(
            code=station.station_code,
            name=station.name.title(),
            river=station.river.title() if station.river else None,
            municipality=Municipality(
                station.municipality_code, station.municipality.title()
            ),
            latitude=station.latitude,
            longitude=station.longitude,
            sensor_letters=station.station_type,
            thresholds=Thresholds(
                thresholds.pre_alarm, thresholds.guard, thresholds.danger
            ),
            sensor_id=station.sensor_id,
        )

    @property
    def title(self) -> str:
        """Return the title of the station in its municipality: its river or name."""
        return self.river or self.name

    @property
    def label(self) -> str:
        """Return how the station is listed in its municipality: river, then name."""
        if self.river:
            return f"{self.river} — {self.name}"
        return self.name


def normalize(name: str) -> str:
    """Return a name for comparing what is typed: "Mondovì" is "Mondovi'".

    Arpa writes an accent as an apostrophe and keeps hyphens ("Pont-Canavese"):
    only letters and digits count, without accents or case.
    """
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    return "".join(character for character in decomposed if character.isalnum())


class StationCatalog:
    """The stations of the network, by municipality."""

    def __init__(self, stations: Iterable[StationChoice]) -> None:
        """Initialize the catalog of the stations of a list."""
        self.stations = {station.code: station for station in stations}
        """The stations, by code."""

    @property
    def municipalities(self) -> list[Municipality]:
        """Return the municipalities with a station, in alphabetical order."""
        found = {station.municipality for station in self.stations.values()}
        return sorted(found, key=lambda municipality: normalize(municipality.name))

    def municipality(self, typed: str) -> Municipality | None:
        """Return the municipality of a name chosen or typed; None if not listed."""
        wanted = normalize(typed)
        return next(
            (
                municipality
                for municipality in self.municipalities
                if normalize(municipality.name) == wanted
            ),
            None,
        )

    def stations_of(
        self, municipality_code: str, *, added: Collection[str] = ()
    ) -> list[StationChoice]:
        """Return the stations of a municipality not added yet, the rivers first.

        ``added`` are the codes of the stations already added.
        """
        return sorted(
            (
                station
                for station in self.stations.values()
                if station.municipality.code == municipality_code
                and station.code not in added
            ),
            key=lambda station: (
                station.river is None,
                normalize(station.river or ""),
                normalize(station.name),
            ),
        )
