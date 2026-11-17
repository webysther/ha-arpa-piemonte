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
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.arpa_piemonte.const import (
    CONF_MUNICIPALITY_CODE,
    CONF_SENSOR_ID,
    CONF_SENSOR_LETTERS,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_THRESHOLDS,
    CONF_WEBSITE_PARAMS,
    DOMAIN,
    SUBENTRY_STATION,
)
from custom_components.arpa_piemonte.models import (
    municipality_unique_id,
    station_unique_id,
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
"""Unique ID of the station of Pray, of its device and subentry."""
TITLE = "Pray Sessera"
"""Name of the station of Pray, of its device."""
PRAY_DATA: dict[str, Any] = {
    CONF_STATION_CODE: PRAY,
    CONF_STATION_NAME: TITLE,
    CONF_SENSOR_ID: PRAY_SENSOR,
    CONF_SENSOR_LETTERS: "IPT",
    CONF_THRESHOLDS: {"pre_alarm": 2.3, "guard": 3.0, "danger": 3.8},
    CONF_WEBSITE_PARAMS: ["idro", "pluv", "terma"],
}
"""The data of the subentry of the station of Pray: its files on the website as
the list of stations of the website names them."""
PRAY_MUNICIPALITY = "096050"
PRAY_ENTRY_ID = f"ISTAT_{PRAY_MUNICIPALITY}"
"""Unique ID of the entry of the municipality of Pray."""

AVIGLIANA = "142"
AVIGLIANA_SENSOR = "001013900"
AVIGLIANA_UNIQUE_ID = f"PIE_{AVIGLIANA}"
AVIGLIANA_MUNICIPALITY = "001013"
AVIGLIANA_DATA: dict[str, Any] = {
    CONF_STATION_CODE: AVIGLIANA,
    CONF_STATION_NAME: "Avigliana",
    CONF_SENSOR_ID: AVIGLIANA_SENSOR,
    CONF_SENSOR_LETTERS: "BHPRTV",
    CONF_THRESHOLDS: {"pre_alarm": None, "guard": None, "danger": None},
    CONF_WEBSITE_PARAMS: [
        "baro",
        "dirv",
        "igro",
        "pluv",
        "radd",
        "terma",
        "velr",
        "vels",
        "velv",
    ],
}
"""The data of the subentry of the station of Avigliana: a weather station
with a barometer and a radiometer, whose files the website lists."""

METEO3R_URL = Host.PRIMARY.url(station_path(PRAY))
METEO3R_MIRROR_URL = Host.MIRROR.url(station_path(PRAY))
LEVEL_URL = series_url(Param.LEVEL, PRAY_SENSOR)
TEMPERATURE_URL = series_url(Param.TEMPERATURE, PRAY_SENSOR)
RAIN_URL = series_url(Param.RAIN_10_MIN, PRAY_SENSOR)
REALTIME_URL = data_pie_url(PRAY)
PRESSURE_URL = series_url(Param.PRESSURE, AVIGLIANA_SENSOR)
RADIATION_URL = series_url(Param.RADIATION, AVIGLIANA_SENSOR)


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


def serve_avigliana(
    aioclient_mock: AiohttpClientMocker, status: HTTPStatus = HTTPStatus.OK
) -> None:
    """Serve Avigliana: its file of Meteo 3R, its pressure and its radiation.

    With an error status, the website answers it for both files.
    """
    meteo3r = fixture_text("misure_PIE_142.json")
    for host in Host:
        aioclient_mock.get(host.url(station_path(AVIGLIANA)), text=meteo3r)
    for url, name in (
        (PRESSURE_URL, "baro_001013900.geojson"),
        (RADIATION_URL, "radd_001013900.geojson"),
    ):
        if status == HTTPStatus.OK:
            aioclient_mock.get(url, text=fixture_text(name))
        else:
            aioclient_mock.get(url, status=status)


def requested(aioclient_mock: AiohttpClientMocker) -> list[str]:
    """Return the URLs requested, in order."""
    return [str(url) for _, url, _, _ in aioclient_mock.mock_calls]


def station_subentry(
    data: dict[str, Any], title: str | None = None
) -> ConfigSubentryData:
    """Return the subentry of a station, titled by its name unless given."""
    return ConfigSubentryData(
        data=data,
        subentry_type=SUBENTRY_STATION,
        title=title or data[CONF_STATION_NAME],
        unique_id=station_unique_id(data[CONF_STATION_CODE]),
    )


def municipality_entry(
    code: str, title: str, *stations: ConfigSubentryData
) -> MockConfigEntry:
    """Return the entry of a municipality with its stations."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=title,
        version=2,
        minor_version=1,
        unique_id=municipality_unique_id(code),
        data={CONF_MUNICIPALITY_CODE: code},
        subentries_data=stations,
    )


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration with a config entry."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def device_of(
    hass: HomeAssistant, entry_id: str, unique_id: str = UNIQUE_ID
) -> dr.DeviceEntry | None:
    """Return the device of a station in an entry; None when it has none."""
    return next(
        (
            device
            for device in dr.async_entries_for_config_entry(
                dr.async_get(hass), entry_id
            )
            if (DOMAIN, unique_id) in device.identifiers
        ),
        None,
    )


def subentry_of_device(device: dr.DeviceEntry) -> str | None:
    """Return the subentry of a device, as each version of Home Assistant has it."""
    if hasattr(device, "config_subentry_id"):  # 2026.8 and newer: one entry
        subentry_id: str | None = device.config_subentry_id
        return subentry_id
    (subentry_ids,) = device.config_entries_subentries.values()
    (subentry_id,) = subentry_ids
    return subentry_id


def entity_id_of(
    hass: HomeAssistant, key: str, unique_id: str = UNIQUE_ID, platform: str = "sensor"
) -> str:
    """Return the entity ID of an entity of a station, by its key."""
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{unique_id}-{key}"
    )
    assert entity_id is not None
    return entity_id
