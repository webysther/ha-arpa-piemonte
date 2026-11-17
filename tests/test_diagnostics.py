"""Tests of the diagnostics of a station."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    # Requested after init_integration, so its access token is issued after the
    # clock is moved to the frozen time and does not expire
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that diagnostics show what each source answered and what is shown."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    assert diagnostics["station"]["station_code"] == "188"
    assert diagnostics["shown"]["level"] == {
        "value": 0.86,
        "measured_at": "2026-11-17T02:00:00+00:00",
        "source": "meteo3r",
    }
    assert diagnostics["sources"]["meteo3r"]["error"] is None
    assert diagnostics["sources"]["arpa_website"]["attempted_at"] is None
    assert diagnostics["meteo3r_host"].startswith("https://staticm3r.")
    assert diagnostics["thresholds"] == {"pre_alarm": 2.3, "guard": 3.0, "danger": 3.8}
