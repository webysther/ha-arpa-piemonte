"""Tests of the flood risk of a hydrometer."""

from __future__ import annotations

from http import HTTPStatus
import json
from typing import Any

from homeassistant.const import ATTR_ATTRIBUTION, ATTR_DEVICE_CLASS, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.arpa_piemonte.const import CONF_THRESHOLDS, DOMAIN

from . import (
    PRAY_DATA,
    UNIQUE_ID,
    fixture_json,
    serve_meteo3r,
    serve_realtime,
    serve_website,
    setup_integration,
)

FLOOD_RISK = "binary_sensor.arpa_piemonte_pray_sessera_flood_risk"


def serve_level(
    aioclient_mock: AiohttpClientMocker, level: float | None
) -> dict[str, Any]:
    """Serve the file of Pray with its newest level changed; None for no level."""
    data = fixture_json("misure_PIE_188.json")
    levels = data["DATI"]["I"]
    data["DATI"]["I"] = (
        [*levels[:-1], level] if level is not None else [None] * len(levels)
    )
    serve_meteo3r(aioclient_mock, text=json.dumps(data))
    return data


def flood_risk_state(hass: HomeAssistant) -> str:
    """Return the state of the flood risk of Pray."""
    state = hass.states.get(FLOOD_RISK)
    assert state is not None
    return state.state


async def test_flood_risk(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the flood risk of Pray: a safety sensor of its device, off."""
    state = hass.states.get(FLOOD_RISK)

    assert state is not None
    assert state.state == "off"
    assert state.attributes[ATTR_DEVICE_CLASS] == "safety"
    assert state.attributes[ATTR_ATTRIBUTION].startswith("Fonte: Arpa Piemonte")
    entity = er.async_get(hass).async_get(FLOOD_RISK)
    assert entity is not None
    assert entity.unique_id == f"{UNIQUE_ID}-flood_risk"
    (subentry_id,) = init_integration.subentries
    assert entity.config_subentry_id == subentry_id


@pytest.mark.parametrize(
    ("level", "status", "risk"),
    [
        (2.29, "normal", "off"),
        (2.3, "pre_alarm", "on"),
        (2.9, "pre_alarm", "on"),
        (3.0, "guard", "on"),
        (3.8, "danger", "on"),
    ],
)
async def test_flood_risk_from_the_pre_alarm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    level: float,
    status: str,
    risk: str,
) -> None:
    """Test that the risk is on from the pre-alarm threshold (2.3 m at Pray)."""
    serve_level(aioclient_mock, level)
    serve_website(aioclient_mock)
    serve_realtime(aioclient_mock)

    await setup_integration(hass, mock_config_entry)

    level_status = hass.states.get("sensor.arpa_piemonte_pray_sessera_level_status")
    assert level_status is not None
    assert level_status.state == status
    assert flood_risk_state(hass) == risk


async def test_flood_risk_without_a_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the risk is unavailable while no source gives the level."""
    serve_level(aioclient_mock, None)
    serve_website(aioclient_mock, HTTPStatus.SERVICE_UNAVAILABLE)
    serve_realtime(aioclient_mock, HTTPStatus.SERVICE_UNAVAILABLE)

    await setup_integration(hass, mock_config_entry)

    assert flood_risk_state(hass) == STATE_UNAVAILABLE


@pytest.mark.parametrize("entry_data", [{**PRAY_DATA, CONF_THRESHOLDS: {}}])
async def test_no_flood_risk_without_thresholds(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that a hydrometer without thresholds has no flood risk."""
    del init_integration
    registry = er.async_get(hass)

    assert (
        registry.async_get_entity_id("binary_sensor", DOMAIN, f"{UNIQUE_ID}-flood_risk")
        is None
    )
