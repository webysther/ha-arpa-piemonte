"""Tests of the pressure and the solar radiation: only the Arpa website gives them."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus

from aiometeo3r import Host
from aiometeo3r.urls import station_path
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.arpa_piemonte.const import (
    CONF_SENSOR_ID,
    CONF_WEBSITE_PARAMS,
    DOMAIN,
    WEBSITE_SERIES_SPAN,
)
from custom_components.arpa_piemonte.coordinator import ArpaPiemonteCoordinator
from custom_components.arpa_piemonte.models import Quantity, Source

from . import (
    AVIGLIANA,
    AVIGLIANA_DATA,
    AVIGLIANA_MUNICIPALITY,
    AVIGLIANA_UNIQUE_ID,
    PRESSURE_URL,
    RADIATION_URL,
    entity_id_of,
    municipality_entry,
    requested,
    serve_avigliana,
    setup_integration,
    station_subentry,
)
from .test_image import NEWEST, chart_of

METEO3R_URL = Host.PRIMARY.url(station_path(AVIGLIANA))


def avigliana_entry(**changes: object) -> MockConfigEntry:
    """Return the entry of Avigliana, with its station as given."""
    return municipality_entry(
        AVIGLIANA_MUNICIPALITY,
        "Avigliana",
        station_subentry({**AVIGLIANA_DATA, **changes}),
    )


def coordinator_of(entry: MockConfigEntry) -> ArpaPiemonteCoordinator:
    """Return the coordinator of the station of an entry."""
    (coordinator,) = entry.runtime_data.stations.values()
    assert isinstance(coordinator, ArpaPiemonteCoordinator)
    return coordinator


def state_of(hass: HomeAssistant, key: str, platform: str = "sensor") -> str:
    """Return the state of an entity of Avigliana."""
    state = hass.states.get(entity_id_of(hass, key, AVIGLIANA_UNIQUE_ID, platform))
    assert state is not None
    return state.state


def keys_of(hass: HomeAssistant, entry: MockConfigEntry) -> set[str]:
    """Return the keys of the entities of the station of an entry."""
    return {
        entity.unique_id.removeprefix(f"{AVIGLIANA_UNIQUE_ID}-")
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }


async def test_pressure_and_radiation_from_the_website(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the website gives the pressure and the radiation, not the rest."""
    serve_avigliana(aioclient_mock)

    await setup_integration(hass, avigliana_entry())

    # Meteo 3R answers: the website is asked for these two files only
    assert requested(aioclient_mock) == [METEO3R_URL, PRESSURE_URL, RADIATION_URL]
    pressure = hass.states.get(entity_id_of(hass, "pressure", AVIGLIANA_UNIQUE_ID))
    assert pressure is not None
    assert pressure.state == "970.2"
    assert pressure.attributes[ATTR_UNIT_OF_MEASUREMENT] == "hPa"
    assert pressure.attributes[ATTR_DEVICE_CLASS] == "atmospheric_pressure"
    assert pressure.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    radiation = hass.states.get(
        entity_id_of(hass, "solar_radiation", AVIGLIANA_UNIQUE_ID)
    )
    assert radiation is not None
    assert radiation.state == "0.0"
    assert radiation.attributes[ATTR_UNIT_OF_MEASUREMENT] == "W/m²"
    assert radiation.attributes[ATTR_DEVICE_CLASS] == "irradiance"
    # They always come from the website: the source says Meteo 3R answers
    assert state_of(hass, "data_source") == Source.METEO3R


async def test_the_website_is_asked_at_its_pace(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the website is asked again 20 minutes later, not at every update."""
    serve_avigliana(aioclient_mock)
    entry = avigliana_entry()
    await setup_integration(hass, entry)

    for minutes, website in ((10, False), (10, True)):
        aioclient_mock.clear_requests()
        serve_avigliana(aioclient_mock)
        freezer.tick(timedelta(minutes=minutes))
        await coordinator_of(entry).async_refresh()
        await hass.async_block_till_done()
        assert (PRESSURE_URL in requested(aioclient_mock)) is website


async def test_charts_of_pressure_and_radiation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the charts of the pressure and the radiation, as long as the others."""
    serve_avigliana(aioclient_mock)
    entry = avigliana_entry()

    await setup_integration(hass, entry)

    assert state_of(hass, "pressure_chart", "image") == NEWEST
    assert state_of(hass, "radiation_chart", "image") == NEWEST
    pressure = await chart_of(
        hass, entity_id_of(hass, "pressure_chart", AVIGLIANA_UNIQUE_ID, "image")
    )
    assert ">hPa</text>" in pressure
    radiation = await chart_of(
        hass, entity_id_of(hass, "radiation_chart", AVIGLIANA_UNIQUE_ID, "image")
    )
    assert ">W/m²</text>" in radiation
    series = coordinator_of(entry).data.series[Quantity.PRESSURE]
    assert series[-1].time - series[0].time == WEBSITE_SERIES_SPAN


async def test_the_website_does_not_answer(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the station loads without them, its source still Meteo 3R."""
    serve_avigliana(aioclient_mock, status=HTTPStatus.SERVICE_UNAVAILABLE)
    entry = avigliana_entry()

    await setup_integration(hass, entry)

    assert state_of(hass, "temperature") == "1.3"
    assert state_of(hass, "pressure") == STATE_UNAVAILABLE
    assert state_of(hass, "pressure_chart", "image") == STATE_UNAVAILABLE
    assert state_of(hass, "data_source") == Source.METEO3R


@pytest.mark.parametrize(
    ("changes", "website"),
    [
        # The website lists other files: a dead barometer and radiometer
        ({CONF_WEBSITE_PARAMS: ["igro", "pluv", "terma"]}, False),
        # No file on the website at all
        ({CONF_SENSOR_ID: None}, False),
        # Files unknown: the letters B and R stand in for them
        ({CONF_WEBSITE_PARAMS: None}, True),
    ],
)
async def test_which_stations_have_them(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    changes: dict[str, object],
    website: bool,
) -> None:
    """Test that a station has them by its files on the website, or else its letters."""
    serve_avigliana(aioclient_mock)
    entry = avigliana_entry(**changes)

    await setup_integration(hass, entry)

    keys = keys_of(hass, entry)
    for key in ("pressure", "solar_radiation", "pressure_chart", "radiation_chart"):
        assert (key in keys) is website
    assert (PRESSURE_URL in requested(aioclient_mock)) is website
    assert "temperature" in keys


async def test_the_entities_are_of_the_integration(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the entities are those of the station, with English entity IDs."""
    serve_avigliana(aioclient_mock)
    await setup_integration(hass, avigliana_entry())

    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{AVIGLIANA_UNIQUE_ID}-pressure"
        )
        == "sensor.arpa_piemonte_avigliana_pressure"
    )
