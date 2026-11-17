"""Tests of the catalog of the stations, by municipality."""

from __future__ import annotations

from aioarpapiemonte.parsers import parse_pie_anag
from aiometeo3r.parsers import parse_registry
import pytest

from custom_components.arpa_piemonte.catalog import (
    Municipality,
    StationCatalog,
    StationChoice,
    normalize,
)
from custom_components.arpa_piemonte.models import Thresholds

from . import fixture_json

METEO3R = StationCatalog(
    StationChoice.of_meteo3r(station)
    for station in parse_registry(fixture_json("misureAnagrafica.json"))
)
REALTIME = StationCatalog(
    StationChoice.of_realtime(station)
    for station in parse_pie_anag(fixture_json("pie_anag.json"))
)
TORINO = "001272"


@pytest.mark.parametrize(
    ("typed", "listed"),
    [
        ("Mondovì", "Mondovi'"),
        (" MONDOVI ", "Mondovi'"),
        ("Pont Canavese", "Pont-Canavese"),
        ("sauze d'oulx", "Sauze D'Oulx"),
        ("Castell' Alfero", "Castell'Alfero"),
    ],
)
def test_normalize(typed: str, listed: str) -> None:
    """Test that a name typed by hand matches the name Arpa writes."""
    assert normalize(typed) == normalize(listed)


def test_municipalities() -> None:
    """Test the municipalities: alphabetical, each name its own after normalizing."""
    municipalities = METEO3R.municipalities

    assert len(METEO3R.stations) == 374
    assert len(municipalities) == 278
    assert municipalities[0] == Municipality("004001", "Acceglio")
    assert len({normalize(municipality.name) for municipality in municipalities}) == 278


def test_both_lists_give_the_same_municipalities() -> None:
    """Test that the api_realtime names the municipalities as Meteo 3R does."""
    assert REALTIME.municipalities == METEO3R.municipalities


def test_municipality_of_a_typed_name() -> None:
    """Test the municipality of a name, and of a name without station."""
    assert METEO3R.municipality("mondovì") == Municipality("004130", "Mondovi'")
    assert METEO3R.municipality("Roma") is None
    assert METEO3R.municipality("") is None


def test_stations_of_a_municipality() -> None:
    """Test the stations of Torino: the rivers first, then the others."""
    stations = METEO3R.stations_of(TORINO)

    assert [station.label for station in stations] == [
        "Dora Riparia — Torino Dora Riparia",
        "Po — Torino Murazzi Po",
        "Stura Di Lanzo — Torino Stura Di Lanzo",
        "Torino Alenia",
        "Torino Giardini Reali",
        "Torino Reiss Romoli",
        "Torino Vallere",
        "Torino Via Della Consolata",
    ]
    assert [station.title for station in stations[:2]] == ["Dora Riparia", "Po"]
    assert stations[-1].title == "Torino Via Della Consolata"


def test_stations_not_added_yet() -> None:
    """Test that the stations already added are left out."""
    added = {station.code for station in METEO3R.stations_of(TORINO)[1:]}

    assert len(METEO3R.stations_of(TORINO, added=added)) == 1
    assert METEO3R.stations_of("999999") == []


def test_station_of_the_api_realtime() -> None:
    """Test a station of the api_realtime, named in capitals there."""
    pray = REALTIME.stations["188"]

    assert pray.name == "Pray Sessera"
    assert pray.river == "Sessera"
    assert pray.municipality == Municipality("096050", "Pray")
    assert pray.sensor_id == "002105900"
    assert pray.thresholds == Thresholds(2.3, 3.0, 3.8)
    assert pray.label == "Sessera — Pray Sessera"
