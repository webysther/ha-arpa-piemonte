"""Tests of where the risks of a municipality are taken from: its options."""

from __future__ import annotations

from typing import Any

from aioarpapiemonte import HeatCity
from homeassistant.core import HomeAssistant
import pytest

from custom_components.arpa_piemonte.const import (
    CONF_HEAT_CITY,
    CONF_POSITION,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
)
from custom_components.arpa_piemonte.coordinator import async_risk_place
from custom_components.arpa_piemonte.models import Position, StationConfig
from custom_components.arpa_piemonte.risks import (
    HeatCityChoice,
    PositionChoice,
    has_alerts,
    heat_city,
    mean_position,
)
from custom_components.arpa_piemonte.sources import async_get_sources

from . import municipality_entry

HOME = Position(45.0786, 6.7036)
"""A home at Bardonecchia, in the micro-region IT-21-TO-03."""


def stations(*codes: str) -> list[StationConfig]:
    """Return stations, at the positions of the list of 2026-11-17."""
    return [
        StationConfig.from_data({CONF_STATION_CODE: code, CONF_STATION_NAME: code})
        for code in codes
    ]


@pytest.mark.parametrize(
    ("municipality", "codes", "options", "position", "micro_region", "city"),
    [
        # Pray Sessera: in no micro-region, in the province of Biella
        ("096050", ("188",), {}, Position(45.67389, 8.22167), None, HeatCity.BIELLA),
        # Biella: the mean of a station in the mountains and one in the city is
        # in no micro-region, the station in the mountains is
        (
            "096004",
            ("123", "S2566"),
            {},
            Position(45.59264, 8.01875),
            "IT-21-VC-01",
            HeatCity.BIELLA,
        ),
        # The home, and the capital nearest to it
        (
            "096050",
            ("188",),
            {CONF_POSITION: "home", CONF_HEAT_CITY: "nearest"},
            HOME,
            "IT-21-TO-03",
            HeatCity.TORINO,
        ),
        # No station: no position, the capital of the province
        ("096050", (), {}, None, None, HeatCity.BIELLA),
        ("096050", (), {CONF_HEAT_CITY: "nearest"}, None, None, HeatCity.BIELLA),
        # Palestro, in the province of Pavia: the nearest capital
        ("018107", ("200",), {}, Position(45.285, 8.54), None, HeatCity.VERCELLI),
        ("018107", (), {}, None, None, None),
    ],
)
async def test_place_of_the_risks(
    hass: HomeAssistant,
    municipality: str,
    codes: tuple[str, ...],
    options: dict[str, Any],
    position: Position | None,
    micro_region: str | None,
    city: HeatCity | None,
) -> None:
    """Test the position, micro-region and heat-wave city of the risks."""
    hass.config.latitude, hass.config.longitude = HOME.latitude, HOME.longitude
    entry = municipality_entry(municipality, municipality, options=options)

    place = await async_risk_place(
        hass, entry, async_get_sources(hass), stations(*codes)
    )

    if position is None:
        assert place.position is None
    else:
        assert place.position is not None
        assert (place.position.latitude, place.position.longitude) == pytest.approx(
            (position.latitude, position.longitude)
        )
    assert place.micro_region == micro_region
    assert place.heat_city is city
    assert place.choice is PositionChoice(options.get(CONF_POSITION, "stations"))


def test_mean_position() -> None:
    """Test the mean of the positions of stations, none without any."""
    assert mean_position([]) is None
    assert mean_position([Position(45.0, 8.0), Position(46.0, 9.0)]) == Position(
        45.5, 8.5
    )


def test_heat_city_without_a_position() -> None:
    """Test the capital of the province standing in for the nearest one."""
    assert heat_city(HeatCityChoice.NEAREST, "001272", None) is HeatCity.TORINO
    assert heat_city(HeatCityChoice.PROVINCE, "018107", None) is None


@pytest.mark.parametrize(
    ("municipality", "alerts"),
    [("096050", True), ("001272", True), ("103072", True), ("018107", False)],
)
def test_alerts_of_piedmont_only(municipality: str, alerts: bool) -> None:
    """Test that the alert bulletin covers the municipalities of Piedmont only."""
    assert has_alerts(municipality) is alerts
