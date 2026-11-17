"""Tests of the diagnostics of a municipality and of a station."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from . import device_of


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

    assert diagnostics["entry"]["unique_id"] == "ISTAT_096050"
    station = diagnostics["stations"]["188"]
    assert station["station"]["name"] == "Pray Sessera"
    assert station["shown"]["level"] == {
        "value": 0.86,
        "measured_at": "2026-11-17T02:00:00+00:00",
        "source": "meteo3r",
    }
    assert station["sources"]["meteo3r"]["error"] is None
    assert station["sources"]["arpa_website"]["attempted_at"] is None
    assert station["thresholds"] == {"pre_alarm": 2.3, "guard": 3.0, "danger": 3.8}
    assert station["series"]["level"] == 153
    assert diagnostics["meteo3r_host"].startswith("https://staticm3r.")


async def test_diagnostics_of_a_station(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the diagnostics of the device of a station."""
    device = device_of(hass, init_integration.entry_id)
    assert device is not None

    diagnostics = await get_diagnostics_for_device(
        hass, hass_client, init_integration, device
    )

    assert diagnostics["station"]["station"]["station_code"] == "188"
    assert diagnostics["station"]["last_update_success"] is True
    assert diagnostics["meteo3r_host"].startswith("https://staticm3r.")
