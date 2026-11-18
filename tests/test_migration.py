"""Tests of the migration from one entry per station to one per municipality."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from aiometeo3r import Host
from aiometeo3r.parsers import parse_registry
from aiometeo3r.urls import station_path
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import pytest
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
)
from custom_components.arpa_piemonte.station_places import (
    STATION_PLACES,
    StationPlace,
)

from . import (
    PRAY_DATA,
    PRAY_ENTRY_ID,
    PRAY_MUNICIPALITY,
    UNIQUE_ID,
    device_of,
    fixture_json,
    fixture_text,
    municipality_entry,
    station_subentry,
    subentry_of_device,
)

PRAY_V1_DATA = {
    key: value
    for key, value in PRAY_DATA.items()
    if key not in (CONF_STATION_NAME, CONF_WEBSITE_PARAMS)
}
"""The data of the entry of Pray in version 1: no name, it was the title, and no
files of the website."""
VINADIO = "004248"
COLLE_LOMBARDA = "001"
NERAISSA = "126"


def v1_data(code: str) -> dict[str, Any]:
    """Return the data of version 1 of a weather station."""
    return {
        CONF_STATION_CODE: code,
        CONF_SENSOR_ID: None,
        CONF_SENSOR_LETTERS: "T",
        CONF_THRESHOLDS: {},
    }


def add_v1_station(
    hass: HomeAssistant,
    code: str,
    title: str,
    data: dict[str, Any],
    *,
    disabled: bool = False,
    with_device: bool = True,
) -> MockConfigEntry:
    """Add the entry of a station of version 1, with its registry entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        version=1,
        minor_version=1,
        unique_id=f"PIE_{code}",
        data=data,
        disabled_by=ConfigEntryDisabler.USER if disabled else None,
    )
    entry.add_to_hass(hass)
    device_id = None
    if with_device:
        device_id = (
            dr.async_get(hass)
            .async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, f"PIE_{code}")},
                name=title,
                disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY if disabled else None,
            )
            .id
        )
    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"PIE_{code}-temperature",
        config_entry=entry,
        device_id=device_id,
        disabled_by=er.RegistryEntryDisabler.CONFIG_ENTRY if disabled else None,
    )
    return entry


def serve_station(
    aioclient_mock: AiohttpClientMocker, code: str, fixture: str | None = None
) -> None:
    """Serve the file of a station of Meteo 3R; without one, an error everywhere."""
    if fixture is not None:
        aioclient_mock.get(
            Host.PRIMARY.url(station_path(code)), text=fixture_text(fixture)
        )
        return
    for host in Host:
        aioclient_mock.get(host.url(station_path(code)), status=HTTPStatus.NOT_FOUND)
    aioclient_mock.get(
        f"https://utility.arpa.piemonte.it/api_realtime/data_pie?station_code={code}",
        status=HTTPStatus.SERVICE_UNAVAILABLE,
    )


async def setup(hass: HomeAssistant) -> None:
    """Set up the integration, which migrates the entries, then sets them up."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


def test_station_places_are_the_list_of_meteo3r() -> None:
    """Test that the table is the list the entries of version 1 were chosen from."""
    stations = parse_registry(fixture_json("misureAnagrafica.json"))
    places = {
        station.code: StationPlace(
            station.municipality_code,
            station.municipality,
            station.latitude,
            station.longitude,
            station.river.title() if station.river else None,
        )
        for station in stations
    }

    assert places == STATION_PLACES


async def test_migrate_a_station(
    hass: HomeAssistant, mock_sources: AiohttpClientMocker
) -> None:
    """Test that a station becomes a subentry of its municipality, as it was."""
    del mock_sources
    entry = add_v1_station(hass, "188", "Pray Sessera", PRAY_V1_DATA)
    entity_registry = er.async_get(hass)
    (entity,) = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    entity_registry.async_update_entity(
        entity.entity_id, new_entity_id="sensor.sessera_at_pray"
    )
    device = device_of(hass, entry.entry_id)
    assert device is not None

    await setup(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.unique_id == PRAY_ENTRY_ID
    assert entry.title == "Pray"
    assert dict(entry.data) == {CONF_MUNICIPALITY_CODE: PRAY_MUNICIPALITY}
    (subentry,) = entry.subentries.values()
    assert subentry.title == "Sessera"
    assert subentry.unique_id == UNIQUE_ID
    # Its files on the website are unknown until it is read again
    # The position of the station comes from the list of 2026-11-17
    assert dict(subentry.data) == {
        **PRAY_DATA,
        CONF_WEBSITE_PARAMS: None,
        CONF_LATITUDE: 45.67389,
        CONF_LONGITUDE: 8.22167,
    }
    moved = entity_registry.async_get("sensor.sessera_at_pray")
    assert moved is not None
    assert moved.unique_id == f"{UNIQUE_ID}-temperature"
    assert moved.config_subentry_id == subentry.subentry_id
    state = hass.states.get("sensor.sessera_at_pray")
    assert state is not None
    assert state.state == "1.1"
    moved_device = device_of(hass, entry.entry_id)
    assert moved_device is not None
    assert moved_device.id == device.id
    assert subentry_of_device(moved_device) == subentry.subentry_id


async def test_merge_the_stations_of_a_municipality(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the stations of a municipality join the entry of an enabled one."""
    serve_station(aioclient_mock, COLLE_LOMBARDA, "misure_PIE_001.json")
    serve_station(aioclient_mock, NERAISSA)
    neraissa = add_v1_station(
        hass, NERAISSA, "Neraissa", v1_data(NERAISSA), disabled=True
    )
    colle = add_v1_station(
        hass,
        COLLE_LOMBARDA,
        "Colle Lombarda",
        v1_data(COLLE_LOMBARDA),
        with_device=False,
    )

    await setup(hass)

    assert hass.config_entries.async_entries(DOMAIN) == [colle]
    assert colle.state is ConfigEntryState.LOADED
    assert colle.unique_id == f"ISTAT_{VINADIO}"
    assert colle.title == "Vinadio"
    assert {subentry.title for subentry in colle.subentries.values()} == {
        "Colle Lombarda",
        "Neraissa",
    }
    # The station the user had disabled stays disabled
    device = device_of(hass, colle.entry_id, "PIE_126")
    assert device is not None
    assert device.disabled_by is dr.DeviceEntryDisabler.USER
    entities = er.async_entries_for_config_entry(er.async_get(hass), colle.entry_id)
    assert {
        entity.unique_id: entity.disabled_by
        for entity in entities
        if entity.unique_id.endswith("-temperature")
    } == {
        "PIE_001-temperature": None,
        "PIE_126-temperature": er.RegistryEntryDisabler.DEVICE,
    }
    assert neraissa.entry_id not in {
        entry.entry_id for entry in hass.config_entries.async_entries()
    }


async def test_merge_into_a_municipality_added_since(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a station joining the entry of its municipality, added since."""
    serve_station(aioclient_mock, COLLE_LOMBARDA, "misure_PIE_001.json")
    serve_station(aioclient_mock, NERAISSA)
    vinadio = municipality_entry(
        VINADIO,
        "Vinadio",
        station_subentry(
            {**v1_data(COLLE_LOMBARDA), CONF_STATION_NAME: "Colle Lombarda"}
        ),
    )
    vinadio.add_to_hass(hass)
    add_v1_station(hass, NERAISSA, "Neraissa", v1_data(NERAISSA))

    await setup(hass)

    assert hass.config_entries.async_entries(DOMAIN) == [vinadio]
    neraissa = next(
        subentry
        for subentry in vinadio.subentries.values()
        if subentry.unique_id == "PIE_126"
    )
    device = device_of(hass, vinadio.entry_id, "PIE_126")
    assert device is not None
    assert subentry_of_device(device) == neraissa.subentry_id


async def test_station_missing_from_the_list(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a station unknown in 2026-11-17 keeps its entry, not loaded."""
    entry = add_v1_station(hass, "999", "New station", v1_data("999"))

    await setup(hass)

    assert entry.version == 1
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert "New station is not among those of 2026-11-17" in caplog.text
