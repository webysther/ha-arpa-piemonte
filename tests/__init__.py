"""Tests of the ARPA Piemonte integration."""

from __future__ import annotations

from http import HTTPStatus
import json
from pathlib import Path
from typing import Any

from aioarpapiemonte import Param
from aioarpapiemonte.urls import data_pie_url, series_url
from aiometeo3r import Host
from aiometeo3r.urls import station_path
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
    CONF_THRESHOLDS,
    DOMAIN,
)

FIXTURES = Path(__file__).parent / "fixtures"
"""Unmodified files of Arpa Piemonte, downloaded on 2026-11-17 at about 02:30 UTC.

The newest readings: Meteo 3R and the Arpa website at 02:00 UTC, the
api_realtime at 23:00 UTC of the day before.
"""

NOW = "2026-11-17 02:40:00+00:00"
"""The time of the tests: 40 minutes after the newest reading."""

PRAY = "188"
PRAY_SENSOR = "002105900"
UNIQUE_ID = f"PIE_{PRAY}"
TITLE = "Pray Sessera"
PRAY_DATA: dict[str, Any] = {
    CONF_STATION_CODE: PRAY,
    CONF_SENSOR_ID: PRAY_SENSOR,
    CONF_SENSOR_LETTERS: "IPT",
    CONF_THRESHOLDS: {"pre_alarm": 2.3, "guard": 3.0, "danger": 3.8},
}

METEO3R_URL = Host.PRIMARY.url(station_path(PRAY))
METEO3R_MIRROR_URL = Host.MIRROR.url(station_path(PRAY))
LEVEL_URL = series_url(Param.LEVEL, PRAY_SENSOR)
TEMPERATURE_URL = series_url(Param.TEMPERATURE, PRAY_SENSOR)
RAIN_URL = series_url(Param.RAIN_10_MIN, PRAY_SENSOR)
REALTIME_URL = data_pie_url(PRAY)


def fixture_text(name: str) -> str:
    """Return a fixture file."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    """Return a fixture file, decoded."""
    return json.loads(fixture_text(name))


def serve_meteo3r(
    aioclient_mock: AiohttpClientMocker,
    *,
    text: str | None = None,
    status: HTTPStatus = HTTPStatus.OK,
    headers: dict[str, str] | None = None,
) -> None:
    """Serve the file of Pray on both hosts of Meteo 3R; an error on both."""
    body = text if text is not None else fixture_text("misure_PIE_188.json")
    for url in (METEO3R_URL, METEO3R_MIRROR_URL):
        if status == HTTPStatus.OK:
            aioclient_mock.get(url, text=body, headers=headers)
        else:
            aioclient_mock.get(url, status=status, headers=headers)


def serve_website(
    aioclient_mock: AiohttpClientMocker, status: HTTPStatus = HTTPStatus.OK
) -> None:
    """Serve the level and temperature files of Pray of the Arpa website."""
    for url, name in (
        (LEVEL_URL, "idro_002105900.geojson"),
        (TEMPERATURE_URL, "terma_002105900.geojson"),
    ):
        if status == HTTPStatus.OK:
            aioclient_mock.get(url, text=fixture_text(name))
        else:
            aioclient_mock.get(url, status=status)


def serve_realtime(
    aioclient_mock: AiohttpClientMocker, status: HTTPStatus = HTTPStatus.OK
) -> None:
    """Serve the records of Pray of the api_realtime."""
    if status == HTTPStatus.OK:
        aioclient_mock.get(REALTIME_URL, text=fixture_text("data_pie_188.json"))
    else:
        aioclient_mock.get(REALTIME_URL, status=status)


def requested(aioclient_mock: AiohttpClientMocker) -> list[str]:
    """Return the URLs requested, in order."""
    return [str(url) for _, url, _, _ in aioclient_mock.mock_calls]


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration with a config entry."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def entity_id_of(hass: HomeAssistant, key: str, unique_id: str = UNIQUE_ID) -> str:
    """Return the entity ID of an entity of a station, by its key."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{unique_id}-{key}"
    )
    assert entity_id is not None
    return entity_id
