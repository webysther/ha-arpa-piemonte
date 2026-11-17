"""Tests of the charts of a station, as images."""

from __future__ import annotations

from http import HTTPStatus
import json

from aiometeo3r import Host
from aiometeo3r.urls import station_path
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from . import (
    PRAY_DATA,
    fixture_json,
    fixture_text,
    municipality_entry,
    serve_meteo3r,
    serve_realtime,
    serve_website,
    setup_integration,
    station_subentry,
)
from .test_init import GONE, GONE_DATA, serve_nothing_for
from .test_sensor import COLLE_LOMBARDA, COLLE_LOMBARDA_DATA, VINADIO

LEVEL_CHART = "image.arpa_piemonte_pray_sessera_level_chart"
NEWEST = "2026-11-17T02:00:00+00:00"
"""The time of the newest reading of the fixtures."""


async def chart_of(hass: HomeAssistant, entity_id: str) -> str:
    """Return the SVG of a chart, from its entity in every version."""
    entity = hass.data[IMAGE_DOMAIN].get_entity(entity_id)
    assert entity.content_type == "image/svg+xml"
    content = await entity.async_image()
    assert content is not None
    return str(content.decode())


async def test_charts_of_a_hydrometer(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the charts of Pray: level with its thresholds, rain, temperature."""
    registry = er.async_get(hass)
    charts = {
        entity.unique_id: entity.entity_id
        for entity in er.async_entries_for_config_entry(
            registry, init_integration.entry_id
        )
        if entity.domain == "image"
    }

    assert charts == {
        "PIE_188-level_chart": LEVEL_CHART,
        "PIE_188-rain_chart": "image.arpa_piemonte_pray_sessera_rain_chart",
        "PIE_188-temperature_chart": (
            "image.arpa_piemonte_pray_sessera_temperature_chart"
        ),
    }
    state = hass.states.get(LEVEL_CHART)
    assert state is not None
    assert state.state == NEWEST
    svg = await chart_of(hass, LEVEL_CHART)
    assert svg.startswith("<svg")
    assert "2.3 m" in svg
    assert "3.8 m" in svg


async def test_charts_of_a_weather_station(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the charts of Colle Lombarda: no level, wind and snow."""
    aioclient_mock.get(
        Host.PRIMARY.url(station_path(COLLE_LOMBARDA)),
        text=fixture_text("misure_PIE_001.json"),
    )
    entry = municipality_entry(
        VINADIO, "Vinadio", station_subentry(COLLE_LOMBARDA_DATA)
    )

    await setup_integration(hass, entry)

    keys = {
        entity.unique_id.removeprefix("PIE_001-")
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if entity.domain == "image"
    }
    assert keys == {
        "rain_chart",
        "temperature_chart",
        "humidity_chart",
        "snow_chart",
        "wind_chart",
    }
    assert "km/h" in await chart_of(
        hass, "image.arpa_piemonte_colle_lombarda_wind_chart"
    )


async def test_chart_drawn_again_with_new_readings(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_sources: AiohttpClientMocker,
) -> None:
    """Test that a chart follows the readings of Meteo 3R."""
    before = await chart_of(hass, LEVEL_CHART)
    data = fixture_json("misure_PIE_188.json")
    data["DATI"]["I"][-1] = 2.9
    mock_sources.clear_requests()
    serve_meteo3r(mock_sources, text=json.dumps(data))
    (coordinator,) = init_integration.runtime_data.stations.values()

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert await chart_of(hass, LEVEL_CHART) != before


async def test_no_chart_without_meteo3r(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the charts are unavailable while Meteo 3R gave no series."""
    serve_meteo3r(aioclient_mock, status=HTTPStatus.SERVICE_UNAVAILABLE)
    serve_website(aioclient_mock)
    serve_realtime(aioclient_mock)

    await setup_integration(hass, mock_config_entry)

    level = hass.states.get("sensor.arpa_piemonte_pray_sessera_level")
    assert level is not None
    assert level.state == "0.86"
    chart = hass.states.get(LEVEL_CHART)
    assert chart is not None
    assert chart.state == STATE_UNAVAILABLE


async def test_chart_served_as_svg(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    # Requested after init_integration, so its access token is issued after the
    # clock is moved to the frozen time and does not expire
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that Home Assistant serves the chart as an SVG image."""
    del init_integration
    client = await hass_client()

    response = await client.get(f"/api/image_proxy/{LEVEL_CHART}")

    assert response.status == HTTPStatus.OK
    assert response.content_type == "image/svg+xml"
    assert (await response.text()).startswith("<svg")


async def test_chart_of_a_station_that_never_answered(
    hass: HomeAssistant, mock_sources: AiohttpClientMocker
) -> None:
    """Test the chart of a station that never answered, beside one that did."""
    serve_nothing_for(mock_sources, GONE)
    entry = municipality_entry(
        "096050",
        "Pray",
        station_subentry(PRAY_DATA, "Sessera"),
        station_subentry(GONE_DATA),
    )

    await setup_integration(hass, entry)

    chart = hass.states.get("image.arpa_piemonte_gone_temperature_chart")
    assert chart is not None
    assert chart.state == STATE_UNAVAILABLE
