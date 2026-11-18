"""Tests of the heat waves of a municipality: the bulletin of one of 8 capitals."""

from __future__ import annotations

from http import HTTPStatus
import json
from typing import Any

from aioarpapiemonte import HeatCity
from aioarpapiemonte.urls import heat_forecast_url
from aiometeo3r import Host
from aiometeo3r.urls import station_path
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import ATTR_OPTIONS
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.arpa_piemonte.const import (
    CONF_HEAT_CITY,
    CONF_POSITION,
    CONF_SENSOR_ID,
    CONF_SENSOR_LETTERS,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_THRESHOLDS,
    DOMAIN,
)

from . import (
    PRAY_DATA,
    PRAY_MUNICIPALITY,
    WIDGETS,
    device_of,
    fixture_json,
    fixture_text,
    municipality_entry,
    serve_avalanches,
    serve_earthquakes,
    serve_heat,
    serve_meteo3r,
    setup_integration,
    station_subentry,
)

IN_SEASON = "2026-09-30 10:00:00+00:00"
"""Noon in Italy on the day of the last bulletin of the season, 2026-09-30."""

PALESTRO = "018107"
"""Palestro, in the province of Pavia: a station of Arpa Piemonte in Lombardy."""
PALESTRO_STATION = "200"
PALESTRO_DATA: dict[str, Any] = {
    CONF_STATION_CODE: PALESTRO_STATION,
    CONF_STATION_NAME: "Palestro",
    CONF_SENSOR_ID: None,
    CONF_SENSOR_LETTERS: "I",
    CONF_THRESHOLDS: {},
}


def state(hass: HomeAssistant, entity_id: str) -> str:
    """Return the state of an entity."""
    entity = hass.states.get(entity_id)
    assert entity is not None
    return entity.state


def heat_of_biella(levels: tuple[str, str, str]) -> dict[str, Any]:
    """Return the bulletin of Biella of 2026-09-30, with the levels of its days."""
    bulletin = fixture_json("caldo_biella.json")
    for day, level in zip(bulletin["BIELLA"].values(), levels, strict=True):
        day["livello_disagio"] = level
    return bulletin


def pray(**options: Any) -> MockConfigEntry:
    """Return the entry of Pray with its station and options."""
    return municipality_entry(
        PRAY_MUNICIPALITY,
        "Pray",
        station_subentry(PRAY_DATA, "Sessera"),
        options=options,
    )


async def test_heat_out_of_season(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that the last bulletin of the season covers neither today nor tomorrow."""
    del init_integration
    today = hass.states.get("sensor.arpa_piemonte_pray_heat_wave_today")

    assert today is not None
    assert today.state == STATE_UNKNOWN
    assert today.attributes[ATTR_OPTIONS] == ["green", "yellow", "orange", "red"]
    assert state(hass, "sensor.arpa_piemonte_pray_heat_wave_tomorrow") == STATE_UNKNOWN
    # The capital of the province of Pray
    assert state(hass, "sensor.arpa_piemonte_pray_heat_wave_city") == "Biella"


async def test_heat_in_season(
    hass: HomeAssistant,
    mock_sources: AiohttpClientMocker,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the heat of today and tomorrow, by the levels 0 to 3 of Arpa."""
    del mock_sources
    freezer.move_to(IN_SEASON)
    aioclient_mock.clear_requests()
    serve_meteo3r(aioclient_mock)
    aioclient_mock.get(WIDGETS, text=fixture_text("widget_096050.json"))
    serve_earthquakes(aioclient_mock, fixture_json("sismica_tabella.json"))
    serve_heat(aioclient_mock, {HeatCity.BIELLA: heat_of_biella(("2", "3", "0"))})
    serve_avalanches(aioclient_mock)

    await setup_integration(hass, pray())

    assert state(hass, "sensor.arpa_piemonte_pray_heat_wave_today") == "orange"
    assert state(hass, "sensor.arpa_piemonte_pray_heat_wave_tomorrow") == "red"


@pytest.mark.parametrize(
    ("options", "city"),
    [
        ({}, "Biella"),
        # The home is at Bardonecchia: Torino is nearest, not Biella
        ({CONF_POSITION: "home", CONF_HEAT_CITY: "nearest"}, "Torino"),
        ({CONF_POSITION: "home"}, "Biella"),
        # The stations are near Biella
        ({CONF_HEAT_CITY: "nearest"}, "Biella"),
    ],
)
async def test_heat_city(
    hass: HomeAssistant,
    mock_sources: AiohttpClientMocker,
    options: dict[str, Any],
    city: str,
) -> None:
    """Test the capital of the heat waves: of the province, or the nearest."""
    del mock_sources
    hass.config.latitude, hass.config.longitude = 45.0786, 6.7036

    await setup_integration(hass, pray(**options))

    assert state(hass, "sensor.arpa_piemonte_pray_heat_wave_city") == city


async def test_palestro_has_no_alerts(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test Palestro, in Lombardy: no widget, the heat of the nearest capital."""
    # The file of Pray Sessera, as the station of Palestro
    data = fixture_json("misure_PIE_188.json")
    data["IDRETE_CODSTAZ"] = data["ANAGRAFICA"]["IDRETE_CODSTAZ"] = "PIE_200"
    data["ANAGRAFICA"]["CODSTAZ"] = PALESTRO_STATION
    for host in Host:
        aioclient_mock.get(
            host.url(station_path(PALESTRO_STATION)), text=json.dumps(data)
        )
    entry = municipality_entry(PALESTRO, "Palestro", station_subentry(PALESTRO_DATA))

    await setup_integration(hass, entry)

    assert state(hass, "sensor.arpa_piemonte_palestro_heat_wave_city") == "Vercelli"
    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(
            "sensor", DOMAIN, f"ISTAT_{PALESTRO}-highest_alert"
        )
        is None
    )
    assert not any(
        WIDGETS.search(str(url)) for _, url, _, _ in aioclient_mock.mock_calls
    )
    device = device_of(hass, entry.entry_id, f"ISTAT_{PALESTRO}")
    assert device is not None
    assert device.configuration_url is None


async def test_heat_unavailable(
    hass: HomeAssistant,
    mock_sources: AiohttpClientMocker,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the heat is unavailable while the bulletin of its city fails."""
    del mock_sources
    aioclient_mock.clear_requests()
    serve_meteo3r(aioclient_mock)
    aioclient_mock.get(WIDGETS, text=fixture_text("widget_096050.json"))
    serve_earthquakes(aioclient_mock, fixture_json("sismica_tabella.json"))
    aioclient_mock.get(
        heat_forecast_url(HeatCity.BIELLA), status=HTTPStatus.INTERNAL_SERVER_ERROR
    )
    serve_avalanches(aioclient_mock)

    await setup_integration(hass, pray())

    assert state(hass, "sensor.arpa_piemonte_pray_heat_wave_today") == STATE_UNAVAILABLE
