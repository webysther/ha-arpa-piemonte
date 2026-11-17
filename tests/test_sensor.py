"""Tests of the sensors of a station."""

from __future__ import annotations

from aiometeo3r import Host
from aiometeo3r.urls import station_path
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
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

from . import entity_id_of, fixture_text, setup_integration

COLLE_LOMBARDA = "001"
COLLE_LOMBARDA_ID = f"PIE_{COLLE_LOMBARDA}"


def state_of(hass: HomeAssistant, key: str, unique_id: str = "PIE_188") -> str:
    """Return the state of an entity of a station."""
    state = hass.states.get(entity_id_of(hass, key, unique_id))
    assert state is not None
    return state.state


async def test_sensors_of_a_hydrometer(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the sensors of Pray Sessera: level, rain, temperature, thresholds."""
    del init_integration
    assert state_of(hass, "level") == "0.86"
    assert state_of(hass, "temperature") == "1.1"
    assert state_of(hass, "rain_1h") == "0.0"
    assert state_of(hass, "rain_24h") == "0.0"
    assert state_of(hass, "level_status") == "normal"
    assert state_of(hass, "pre_alarm_threshold") == "2.3"
    assert state_of(hass, "guard_threshold") == "3.0"
    assert state_of(hass, "danger_threshold") == "3.8"
    assert state_of(hass, "data_source") == "meteo3r"
    assert state_of(hass, "last_measurement") == "2026-11-17T02:00:00+00:00"

    level = hass.states.get(entity_id_of(hass, "level"))
    assert level is not None
    assert level.entity_id == "sensor.arpa_piemonte_pray_sessera_level"
    assert level.attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert level.attributes[ATTR_DEVICE_CLASS] == "distance"
    assert level.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert level.attributes[ATTR_ATTRIBUTION].startswith("Fonte: Arpa Piemonte")
    assert hass.states.get("sensor.arpa_piemonte_pray_sessera_wind_speed") is None


async def test_device(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Test the device of the station, linked to its page on the Arpa website."""
    devices = dr.async_entries_for_config_entry(
        dr.async_get(hass), init_integration.entry_id
    )

    assert len(devices) == 1
    device = devices[0]
    assert device.identifiers == {(DOMAIN, "PIE_188")}
    assert device.name == "Pray Sessera"
    assert device.manufacturer == "Arpa Piemonte"
    assert device.model_id == "188"
    assert device.configuration_url is not None
    assert device.configuration_url.endswith("?id=002105900&param=idro")
    entities = er.async_entries_for_config_entry(
        er.async_get(hass), init_integration.entry_id
    )
    assert len(entities) == 11


@pytest.mark.parametrize(
    "entry_data",
    [
        {
            CONF_STATION_CODE: COLLE_LOMBARDA,
            CONF_SENSOR_ID: None,
            CONF_SENSOR_LETTERS: "HNPTV",
            CONF_THRESHOLDS: {},
        }
    ],
)
async def test_sensors_of_a_weather_station(
    hass: HomeAssistant,
    entry_data: dict[str, object],
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the sensors of Colle Lombarda: wind and snow, no level."""
    aioclient_mock.get(
        Host.PRIMARY.url(station_path(COLLE_LOMBARDA)),
        text=fixture_text("misure_PIE_001.json"),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Colle Lombarda",
        unique_id=COLLE_LOMBARDA_ID,
        data=entry_data,
    )

    await setup_integration(hass, entry)

    assert state_of(hass, "wind_speed", COLLE_LOMBARDA_ID) == "4.3"
    assert state_of(hass, "wind_direction", COLLE_LOMBARDA_ID) == "134.0"
    assert state_of(hass, "gust_speed", COLLE_LOMBARDA_ID) == "16.9"
    assert state_of(hass, "snow_depth", COLLE_LOMBARDA_ID) == "5.0"
    assert state_of(hass, "humidity", COLLE_LOMBARDA_ID) == "78.0"
    direction = hass.states.get(entity_id_of(hass, "wind_direction", COLLE_LOMBARDA_ID))
    assert direction is not None
    assert direction.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT_ANGLE
    speed = hass.states.get(entity_id_of(hass, "wind_speed", COLLE_LOMBARDA_ID))
    assert speed is not None
    assert speed.attributes[ATTR_UNIT_OF_MEASUREMENT] == "km/h"
    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{COLLE_LOMBARDA_ID}-level")
        is None
    )
    assert (
        registry.async_get_entity_id(
            "sensor", DOMAIN, f"{COLLE_LOMBARDA_ID}-level_status"
        )
        is None
    )
    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert device.configuration_url is None
