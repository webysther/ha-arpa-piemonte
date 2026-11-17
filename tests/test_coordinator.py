"""Tests of the readings of a station: Meteo 3R, then the official sources."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import json
import logging

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.arpa_piemonte.const import (
    CONF_SENSOR_ID,
    UNAVAILABLE_AFTER,
)
from custom_components.arpa_piemonte.coordinator import ArpaPiemonteCoordinator
from custom_components.arpa_piemonte.models import Quantity, Source, Thresholds

from . import (
    LEVEL_URL,
    METEO3R_URL,
    PRAY_DATA,
    RAIN_URL,
    REALTIME_URL,
    TEMPERATURE_URL,
    entity_id_of,
    fixture_json,
    requested,
    serve_meteo3r,
    serve_realtime,
    serve_website,
    setup_integration,
)

ETAG = 'W/"6afbb104-3838"'


def coordinator_of(entry: MockConfigEntry) -> ArpaPiemonteCoordinator:
    """Return the coordinator of the station of an entry."""
    (coordinator,) = entry.runtime_data.stations.values()
    assert isinstance(coordinator, ArpaPiemonteCoordinator)
    return coordinator


def serve_all(aioclient_mock: AiohttpClientMocker, *, meteo3r: bool = True) -> None:
    """Serve every source again, Meteo 3R failing unless asked."""
    aioclient_mock.clear_requests()
    if meteo3r:
        serve_meteo3r(aioclient_mock)
    else:
        serve_meteo3r(aioclient_mock, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    serve_website(aioclient_mock)
    serve_realtime(aioclient_mock)


async def refresh(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Update the readings of a station now."""
    await coordinator_of(entry).async_refresh()
    await hass.async_block_till_done()


def level_state(hass: HomeAssistant) -> str:
    """Return the state of the water level of Pray."""
    state = hass.states.get(entity_id_of(hass, "level"))
    assert state is not None
    return state.state


def source_state(hass: HomeAssistant) -> str:
    """Return the state of the data source of Pray."""
    state = hass.states.get(entity_id_of(hass, "data_source"))
    assert state is not None
    return state.state


async def test_meteo3r_alone_when_it_answers(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_sources: AiohttpClientMocker,
) -> None:
    """Test that the official sources are not asked while Meteo 3R answers."""
    assert requested(mock_sources) == [METEO3R_URL]
    assert level_state(hass) == "0.86"
    assert source_state(hass) == Source.METEO3R


async def test_unchanged_file_writes_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a 304 of Meteo 3R does not write the states again."""
    serve_meteo3r(aioclient_mock, headers={"ETag": ETAG})
    await setup_integration(hass, mock_config_entry)
    before = hass.states.get(entity_id_of(hass, "level"))
    assert before is not None

    aioclient_mock.clear_requests()
    serve_meteo3r(
        aioclient_mock, status=HTTPStatus.NOT_MODIFIED, headers={"ETag": ETAG}
    )
    freezer.tick(timedelta(minutes=10))
    await refresh(hass, mock_config_entry)

    after = hass.states.get(entity_id_of(hass, "level"))
    assert after is not None
    assert after.last_reported == before.last_reported
    assert aioclient_mock.mock_calls[0][3]["If-None-Match"] == ETAG


async def test_official_sources_when_meteo3r_fails_from_the_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test level and temperature from the website, rain from the api_realtime."""
    serve_all(aioclient_mock, meteo3r=False)

    await setup_integration(hass, mock_config_entry)

    data = coordinator_of(mock_config_entry).data
    assert data.measurements[Quantity.LEVEL].source is Source.ARPA_WEBSITE
    assert data.measurements[Quantity.TEMPERATURE].source is Source.ARPA_WEBSITE
    assert data.measurements[Quantity.RAIN_24H].source is Source.ARPA_REALTIME
    assert level_state(hass) == "0.86"
    assert source_state(hass) == Source.ARPA_REALTIME
    assert {LEVEL_URL, TEMPERATURE_URL, REALTIME_URL} <= set(requested(aioclient_mock))
    assert RAIN_URL not in requested(aioclient_mock)
    assert data.thresholds == Thresholds(2.3, 3.0, 3.8)


async def test_readings_of_meteo3r_are_kept_when_it_fails(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that an official reading of the same hour does not replace Meteo 3R."""
    serve_all(aioclient_mock, meteo3r=False)
    freezer.tick(timedelta(minutes=10))

    await refresh(hass, init_integration)

    # Asked for a newer level and temperature, but its readings are as old
    assert LEVEL_URL in requested(aioclient_mock)
    assert REALTIME_URL not in requested(aioclient_mock)
    assert source_state(hass) == Source.METEO3R
    assert "meteo3r did not answer" in caplog.text

    # Hours later, the api_realtime is asked too: its readings are older still
    serve_all(aioclient_mock, meteo3r=False)
    freezer.tick(timedelta(hours=3))
    await refresh(hass, init_integration)

    assert REALTIME_URL in requested(aioclient_mock)
    data = coordinator_of(init_integration).data
    assert data.measurements[Quantity.RAIN_24H].source is Source.METEO3R
    assert data.measurements[Quantity.LEVEL].source is Source.METEO3R


async def test_only_the_quantity_too_old_is_asked(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a level missing for hours in Meteo 3R is read on the website."""
    data = fixture_json("misure_PIE_188.json")
    levels = data["DATI"]["I"]
    data["DATI"]["I"] = [*levels[:-8], *[None] * 8]  # the last 4 hours
    serve_meteo3r(aioclient_mock, text=json.dumps(data))
    serve_website(aioclient_mock)
    serve_realtime(aioclient_mock)

    await setup_integration(hass, mock_config_entry)

    assert requested(aioclient_mock) == [METEO3R_URL, LEVEL_URL]
    snapshot = coordinator_of(mock_config_entry).data
    assert snapshot.measurements[Quantity.LEVEL].source is Source.ARPA_WEBSITE
    assert snapshot.measurements[Quantity.TEMPERATURE].source is Source.METEO3R


async def test_back_to_meteo3r(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that Meteo 3R is shown again as soon as it answers."""
    serve_all(aioclient_mock, meteo3r=False)
    await setup_integration(hass, mock_config_entry)
    assert source_state(hass) == Source.ARPA_REALTIME

    serve_all(aioclient_mock)
    freezer.tick(timedelta(minutes=10))
    caplog.set_level(logging.INFO)
    await refresh(hass, mock_config_entry)

    assert requested(aioclient_mock) == [METEO3R_URL]
    assert source_state(hass) == Source.METEO3R
    assert "answers again" in caplog.text


async def test_official_sources_are_not_asked_too_often(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the least time between two requests, even when they failed."""
    serve_meteo3r(aioclient_mock, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    serve_website(aioclient_mock, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    serve_realtime(aioclient_mock)
    await setup_integration(hass, mock_config_entry)

    # Every 10 minutes: the website every 20, the api_realtime every 30
    for website, realtime in ((False, False), (True, False), (False, True)):
        aioclient_mock.clear_requests()
        serve_meteo3r(aioclient_mock, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        serve_website(aioclient_mock, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        serve_realtime(aioclient_mock)
        freezer.tick(timedelta(minutes=10))
        await refresh(hass, mock_config_entry)
        urls = requested(aioclient_mock)
        assert (LEVEL_URL in urls) is website
        assert (REALTIME_URL in urls) is realtime


async def test_old_readings_are_not_shown(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a station whose readings are all too old shows nothing."""
    serve_all(aioclient_mock)
    freezer.tick(UNAVAILABLE_AFTER)

    await refresh(hass, init_integration)

    assert level_state(hass) == STATE_UNAVAILABLE
    coordinator = coordinator_of(init_integration)
    assert coordinator.last_update_success
    assert coordinator.data.measurements == {}


async def test_failure_without_readings(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the update fails when no source answers and nothing is left."""
    aioclient_mock.clear_requests()
    serve_meteo3r(aioclient_mock, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    serve_website(aioclient_mock, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    serve_realtime(aioclient_mock, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    freezer.tick(UNAVAILABLE_AFTER)

    await refresh(hass, init_integration)

    assert not coordinator_of(init_integration).last_update_success
    assert level_state(hass) == STATE_UNAVAILABLE


@pytest.mark.parametrize("entry_data", [{**PRAY_DATA, CONF_SENSOR_ID: None}])
async def test_station_without_website_file(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a station without a file on the website reads the api_realtime."""
    serve_all(aioclient_mock, meteo3r=False)

    await setup_integration(hass, mock_config_entry)

    assert LEVEL_URL not in requested(aioclient_mock)
    data = coordinator_of(mock_config_entry).data
    assert data.measurements[Quantity.LEVEL].source is Source.ARPA_REALTIME
    # The thresholds stored when the station was added
    assert data.thresholds == Thresholds(2.3, 3.0, 3.8)


async def test_part_of_the_website_answers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the files that answer are used when others fail."""
    serve_meteo3r(aioclient_mock, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    aioclient_mock.get(TEMPERATURE_URL, status=HTTPStatus.NOT_FOUND)
    serve_website(aioclient_mock)
    serve_realtime(aioclient_mock)

    await setup_integration(hass, mock_config_entry)

    data = coordinator_of(mock_config_entry).data
    assert data.measurements[Quantity.LEVEL].source is Source.ARPA_WEBSITE
    assert data.measurements[Quantity.TEMPERATURE].source is Source.ARPA_REALTIME
    assert "arpa_website did not answer" in caplog.text
    assert coordinator_of(mock_config_entry).website.error is not None


async def test_meteo3r_answers_without_thresholds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the thresholds stored are used when no source gives them."""
    data = fixture_json("misure_PIE_188.json")
    for key in ("SOGLIA_PRE", "SOGLIA_GUARDIA", "SOGLIA_PERICOLO"):
        data["ANAGRAFICA"][key] = ""
    serve_meteo3r(aioclient_mock, text=json.dumps(data))

    await setup_integration(hass, mock_config_entry)

    assert coordinator_of(mock_config_entry).data.thresholds == Thresholds(
        2.3, 3.0, 3.8
    )
