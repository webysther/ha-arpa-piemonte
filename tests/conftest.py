"""Fixtures of the Arpa Piemonte tests."""

from __future__ import annotations

from collections.abc import Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from . import (
    NOW,
    PRAY_DATA,
    PRAY_MUNICIPALITY,
    fixture_json,
    municipality_entry,
    serve_avalanches,
    serve_earthquakes,
    serve_heat,
    serve_meteo3r,
    serve_realtime,
    serve_website,
    serve_widget,
    setup_integration,
    station_subentry,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Freeze the clock 40 minutes after the newest reading of the fixtures."""
    freezer.move_to(NOW)
    return freezer


@pytest.fixture
def widget() -> dict[str, Any] | HTTPStatus:
    """Return the widget of Pray; parametrize it to change it, or with an error."""
    return fixture_json("widget_096050.json")


@pytest.fixture
def earthquakes() -> list[Any] | HTTPStatus:
    """Return the earthquakes of the last 30 days; parametrize it to change it."""
    return fixture_json("sismica_tabella.json")


@pytest.fixture(autouse=True)
def mock_risks(
    aioclient_mock: AiohttpClientMocker,
    widget: dict[str, Any] | HTTPStatus,
    earthquakes: list[Any] | HTTPStatus,
) -> None:
    """Serve the natural risks, as each entry asks for them when it is set up.

    The widget of Pray for every municipality, the earthquakes, the heat
    waves of the 8 capitals, and no avalanche bulletin, as out of season.
    """
    serve_widget(aioclient_mock, widget)
    serve_earthquakes(aioclient_mock, earthquakes)
    serve_heat(aioclient_mock)
    serve_avalanches(aioclient_mock)


@pytest.fixture
def entry_data() -> dict[str, Any]:
    """Return the data of the station of Pray; parametrize it to change it."""
    return PRAY_DATA


@pytest.fixture
def mock_config_entry(entry_data: dict[str, Any]) -> MockConfigEntry:
    """Return the entry of the municipality of Pray, with its station."""
    return municipality_entry(
        PRAY_MUNICIPALITY, "Pray", station_subentry(entry_data, "Sessera")
    )


@pytest.fixture
def mock_sources(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Serve every source of Pray Sessera."""
    serve_meteo3r(aioclient_mock)
    serve_website(aioclient_mock)
    serve_realtime(aioclient_mock)
    return aioclient_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sources: AiohttpClientMocker,
) -> MockConfigEntry:
    """Set up the integration with Pray Sessera, every source answering."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Do not set up the integration when a config flow creates an entry."""
    with patch(
        "custom_components.arpa_piemonte.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
