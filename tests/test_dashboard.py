"""Tests of the Arpa Piemonte dashboard and card, served to the frontend."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import call, patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.arpa_piemonte.const import FRONTEND_URL, VERSION

from . import setup_integration

ADD_EXTRA_JS_URL = "custom_components.arpa_piemonte.dashboard.frontend.add_extra_js_url"


async def test_dashboard_is_offered_with_the_frontend(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sources: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that the strategy and the card are served, and loaded by the frontend."""
    assert await async_setup_component(hass, "http", {})
    # The frontend itself needs its package, absent from the tests
    hass.config.components.add("frontend")

    with patch(ADD_EXTRA_JS_URL) as add_extra_js_url:
        await setup_integration(hass, mock_config_entry)

    # The version in the path makes the browsers load them again after an update
    expected = f"/arpa_piemonte/frontend/{VERSION}"
    assert expected == FRONTEND_URL
    assert add_extra_js_url.call_args_list == [
        call(hass, f"{FRONTEND_URL}/arpa-piemonte-dashboard.js"),
        call(hass, f"{FRONTEND_URL}/arpa-piemonte-card.js"),
    ]
    client = await hass_client()
    response = await client.get(f"{FRONTEND_URL}/arpa-piemonte-dashboard.js")
    assert response.status == HTTPStatus.OK
    # Listed in the Add dashboard dialog
    assert "window).customStrategies" in await response.text()
    response = await client.get(f"{FRONTEND_URL}/arpa-piemonte-card.js")
    assert response.status == HTTPStatus.OK
    # Listed in the card picker, importing the strategy with the same version
    text = await response.text()
    assert "window).customCards" in text
    assert 'from "./arpa-piemonte-dashboard.js"' in text


async def test_no_dashboard_without_the_frontend(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sources: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that nothing is served when the frontend does not run."""
    assert await async_setup_component(hass, "http", {})

    with patch(ADD_EXTRA_JS_URL) as add_extra_js_url:
        await setup_integration(hass, mock_config_entry)

    add_extra_js_url.assert_not_called()
    client = await hass_client()
    response = await client.get(f"{FRONTEND_URL}/arpa-piemonte-dashboard.js")
    assert response.status == HTTPStatus.NOT_FOUND
