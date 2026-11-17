"""Tests of the setup and unload of a station."""

from __future__ import annotations

from http import HTTPStatus

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.arpa_piemonte.coordinator import ArpaPiemonteCoordinator

from . import serve_meteo3r, serve_realtime, serve_website, setup_integration


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that a station is set up and unloaded."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert isinstance(init_integration.runtime_data, ArpaPiemonteCoordinator)

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
