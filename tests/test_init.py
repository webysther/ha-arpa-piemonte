"""Tests of the setup and unload of a municipality and its stations."""

from __future__ import annotations

from http import HTTPStatus
from types import MappingProxyType

from aiometeo3r import Host
from aiometeo3r.urls import station_path
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.arpa_piemonte.const import (
    CONF_SENSOR_ID,
    CONF_SENSOR_LETTERS,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_THRESHOLDS,
    DOMAIN,
    SUBENTRY_STATION,
)
from custom_components.arpa_piemonte.coordinator import ArpaPiemonteCoordinator

from . import (
    PRAY_DATA,
    PRAY_MUNICIPALITY,
    device_of,
    entity_id_of,
    municipality_entry,
    serve_meteo3r,
    serve_realtime,
    serve_website,
    setup_integration,
    station_subentry,
)

GONE = "999"
"""A station no source answers for."""
GONE_DATA = {
    CONF_STATION_CODE: GONE,
    CONF_STATION_NAME: "Gone",
    CONF_SENSOR_ID: None,
    CONF_SENSOR_LETTERS: "T",
    CONF_THRESHOLDS: {},
}


def serve_nothing_for(aioclient_mock: AiohttpClientMocker, code: str) -> None:
    """Answer an error for a station on both hosts of Meteo 3R and the api_realtime."""
    for host in Host:
        aioclient_mock.get(host.url(station_path(code)), status=HTTPStatus.NOT_FOUND)
    aioclient_mock.get(
        f"https://utility.arpa.piemonte.it/api_realtime/data_pie?station_code={code}",
        status=HTTPStatus.SERVICE_UNAVAILABLE,
    )


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that a municipality is set up with its station, and unloaded."""
    assert init_integration.state is ConfigEntryState.LOADED
    (coordinator,) = init_integration.runtime_data.stations.values()
    assert isinstance(coordinator, ArpaPiemonteCoordinator)
    assert coordinator.station.station_code == "188"

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_retry_while_no_source_answers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the setup is tried again while no source answers."""
    serve_meteo3r(aioclient_mock, status=HTTPStatus.SERVICE_UNAVAILABLE)
    serve_website(aioclient_mock, status=HTTPStatus.SERVICE_UNAVAILABLE)
    serve_realtime(aioclient_mock, status=HTTPStatus.SERVICE_UNAVAILABLE)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_a_station_that_does_not_answer(
    hass: HomeAssistant, mock_sources: AiohttpClientMocker
) -> None:
    """Test that a station that does not answer does not stop the others."""
    serve_nothing_for(mock_sources, GONE)
    entry = municipality_entry(
        PRAY_MUNICIPALITY,
        "Pray",
        station_subentry(PRAY_DATA, "Sessera"),
        station_subentry(GONE_DATA),
    )

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    level = hass.states.get(entity_id_of(hass, "level"))
    assert level is not None
    assert level.state == "0.86"
    temperature = hass.states.get(entity_id_of(hass, "temperature", "PIE_999"))
    assert temperature is not None
    assert temperature.state == STATE_UNAVAILABLE


async def test_a_municipality_without_stations(hass: HomeAssistant) -> None:
    """Test that a municipality whose stations were all removed loads empty."""
    entry = municipality_entry(PRAY_MUNICIPALITY, "Pray")

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.stations == {}


async def test_add_and_remove_a_station(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_sources: AiohttpClientMocker,
) -> None:
    """Test that the municipality reloads when a station is added or removed."""
    serve_nothing_for(mock_sources, GONE)
    subentry = ConfigSubentry(
        data=MappingProxyType(GONE_DATA),
        subentry_type=SUBENTRY_STATION,
        title="Gone",
        unique_id="PIE_999",
    )

    hass.config_entries.async_add_subentry(init_integration, subentry)
    await hass.async_block_till_done()

    assert len(init_integration.runtime_data.stations) == 2
    assert entity_id_of(hass, "temperature", "PIE_999")

    hass.config_entries.async_remove_subentry(init_integration, subentry.subentry_id)
    await hass.async_block_till_done()

    assert len(init_integration.runtime_data.stations) == 1
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, "PIE_999-temperature") is None
    assert device_of(hass, init_integration.entry_id, "PIE_999") is None
    assert device_of(hass, init_integration.entry_id) is not None
