"""Tests of the earthquakes near a municipality: geolocation entities and a count."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_FRIENDLY_NAME,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
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

from custom_components.arpa_piemonte.const import CONF_POSITION, CONF_RADIUS, DOMAIN

from . import (
    PRAY_DATA,
    PRAY_ENTRY_ID,
    PRAY_MUNICIPALITY,
    device_of,
    fixture_json,
    municipality_entry,
    serve_earthquakes,
    setup_integration,
    station_subentry,
)

NEAREST = "261117023254"
"""The earthquake nearest to Pray Sessera: 59.5 km, magnitude 1.1."""
WITHIN_100_KM = ("261117023254", "261107134627", "261111171618")
"""The earthquakes within 100 km of Pray Sessera: 59.5, 94.5 and 96.6 km."""
COUNT = "sensor.arpa_piemonte_pray_nearby_earthquakes"


def earthquake_entity(event: str) -> str:
    """Return the entity ID of an earthquake near Pray."""
    return f"geo_location.arpa_piemonte_pray_earthquake_{event}"


def pray(**options: Any) -> MockConfigEntry:
    """Return the entry of Pray with its station and options."""
    return municipality_entry(
        PRAY_MUNICIPALITY,
        "Pray",
        station_subentry(PRAY_DATA, "Sessera"),
        options=options,
    )


def earthquakes_of_the_registry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> set[str]:
    """Return the entity IDs of the earthquakes an entry has registered."""
    return {
        entity.entity_id
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if entity.domain == "geo_location"
    }


async def test_none_within_the_radius(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test Pray Sessera: no earthquake within 50 km, the nearest is 59.5 km away."""
    count = hass.states.get(COUNT)

    assert count is not None
    assert count.state == "0"
    assert earthquakes_of_the_registry(hass, init_integration) == set()


async def test_earthquakes_within_the_radius(
    hass: HomeAssistant, mock_sources: AiohttpClientMocker
) -> None:
    """Test the earthquakes within 100 km: where, how far, and on the device."""
    del mock_sources
    entry = pray(**{CONF_RADIUS: 100.0})

    await setup_integration(hass, entry)

    count = hass.states.get(COUNT)
    assert count is not None
    assert count.state == "3"
    assert earthquakes_of_the_registry(hass, entry) == {
        earthquake_entity(event) for event in WITHIN_100_KM
    }
    nearest = hass.states.get(earthquake_entity(NEAREST))
    assert nearest is not None
    assert nearest.state == "59.5"
    assert nearest.attributes[ATTR_UNIT_OF_MEASUREMENT] == "km"
    assert nearest.attributes[ATTR_LATITUDE] == 46.0729
    assert nearest.attributes[ATTR_LONGITUDE] == 7.7091
    assert nearest.attributes["source"] == DOMAIN
    assert nearest.attributes["magnitude"] == 1.1
    assert nearest.attributes["magnitude_type"] == "ML"
    assert nearest.attributes["time"] == "2026-11-17T02:33:18+00:00"
    assert nearest.attributes["depth"] == 4.3
    assert nearest.attributes["district"] == "Alpi Pennine"
    assert nearest.attributes["reviewed"] is True
    assert nearest.attributes[ATTR_ATTRIBUTION].startswith("Fonte: Arpa Piemonte")
    assert nearest.attributes[ATTR_FRIENDLY_NAME] == (
        "Pray · Natural risks Earthquake M 1.1"
    )
    device = device_of(hass, entry.entry_id, PRAY_ENTRY_ID)
    assert device is not None
    registry_entry = er.async_get(hass).async_get(earthquake_entity(NEAREST))
    assert registry_entry is not None
    assert registry_entry.device_id == device.id
    assert registry_entry.unique_id == f"{PRAY_ENTRY_ID}-earthquake_{NEAREST}"


async def test_earthquakes_come_and_go(
    hass: HomeAssistant,
    mock_sources: AiohttpClientMocker,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the entities follow the list: one leaves, one is reviewed."""
    del mock_sources
    entry = pray(**{CONF_RADIUS: 100.0})
    await setup_integration(hass, entry)
    earthquakes = fixture_json("sismica_tabella.json")
    # The oldest of the three leaves the list, the nearest is reviewed
    listed = [event for event in earthquakes if event["ID evento"] != WITHIN_100_KM[1]]
    nearest = next(event for event in listed if event["ID evento"] == NEAREST)
    nearest["valore"] = 1.6

    aioclient_mock.clear_requests()
    serve_earthquakes(aioclient_mock, listed)
    await entry.runtime_data.risks.earthquakes.async_refresh()
    await hass.async_block_till_done()

    assert earthquakes_of_the_registry(hass, entry) == {
        earthquake_entity(NEAREST),
        earthquake_entity(WITHIN_100_KM[2]),
    }
    assert hass.states.get(earthquake_entity(WITHIN_100_KM[1])) is None
    reviewed = hass.states.get(earthquake_entity(NEAREST))
    assert reviewed is not None
    assert reviewed.attributes["magnitude"] == 1.6
    count = hass.states.get(COUNT)
    assert count is not None
    assert count.state == "2"


async def test_earthquakes_near_the_home(
    hass: HomeAssistant, mock_sources: AiohttpClientMocker
) -> None:
    """Test the earthquakes near the home: Bardonecchia, 32.8 km from one in France."""
    del mock_sources
    hass.config.latitude, hass.config.longitude = 45.0786, 6.7036
    entry = pray(**{CONF_POSITION: "home"})

    await setup_integration(hass, entry)

    (event,) = earthquakes_of_the_registry(hass, entry)
    state = hass.states.get(event)
    assert state is not None
    assert state.state == "32.8"
    assert state.attributes["district"] == "Francia"


@pytest.mark.parametrize("earthquakes", [HTTPStatus.SERVICE_UNAVAILABLE])
async def test_earthquakes_unavailable(
    hass: HomeAssistant,
    mock_sources: AiohttpClientMocker,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the list is asked again, and the earthquakes shown once it answers."""
    del mock_sources
    entry = pray(**{CONF_RADIUS: 100.0})
    await setup_integration(hass, entry)

    count = hass.states.get(COUNT)
    assert count is not None
    assert count.state == STATE_UNAVAILABLE
    assert earthquakes_of_the_registry(hass, entry) == set()
    assert "sismica_tabella.json" in caplog.text

    aioclient_mock.clear_requests()
    serve_earthquakes(aioclient_mock, fixture_json("sismica_tabella.json"))
    await entry.runtime_data.risks.earthquakes.async_refresh()
    await hass.async_block_till_done()

    assert len(earthquakes_of_the_registry(hass, entry)) == 3
