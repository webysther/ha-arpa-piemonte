"""Fixtures of the ARPA Piemonte tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.arpa_piemonte.const import DOMAIN

from . import (
    NOW,
    PRAY_DATA,
    TITLE,
    UNIQUE_ID,
    serve_meteo3r,
    serve_realtime,
    serve_website,
    setup_integration,
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
def entry_data() -> dict[str, Any]:
    """Return the data of the config entry; parametrize it to change it."""
    return PRAY_DATA


@pytest.fixture
def mock_config_entry(entry_data: dict[str, Any]) -> MockConfigEntry:
    """Return the config entry of Pray Sessera."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        version=1,
        minor_version=1,
        unique_id=UNIQUE_ID,
        data=entry_data,
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
