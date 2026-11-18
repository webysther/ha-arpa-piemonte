"""Tests of the diagnostics of a municipality and of a station."""

from __future__ import annotations

from http import HTTPStatus

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.arpa_piemonte.const import CONF_HEAT_CITY, CONF_POSITION

from . import (
    PRAY_DATA,
    PRAY_ENTRY_ID,
    PRAY_MUNICIPALITY,
    device_of,
    municipality_entry,
    setup_integration,
    station_subentry,
)

BARDONECCHIA = (45.0786, 6.7036)
"""A home in the micro-region IT-21-TO-03, whose nearest capital is Torino."""


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
    risks = diagnostics["risks"]
    # Pray Sessera is in no micro-region, and its capital is Biella
    assert risks["place"] == {
        "position": "stations",
        "located": True,
        "micro_region": None,
        "heat_city": "biella",
    }
    assert risks["alerts"]["last_update_success"] is True
    assert risks["alerts"]["error"] is None
    alerts = risks["alerts"]["data"]
    assert alerts["risks"]["idraulico_next_day"] == "green"
    assert alerts["risks"]["valanghe_issue_day"] == "not_evaluated"
    assert alerts["phase"] == "none"
    assert alerts["phase_text"] == "Nessuna Fase Operativa"
    assert alerts["issued"] == "2026-11-17T10:57:30+00:00"
    assert alerts["issue_day"] == "2026-11-17"
    assert alerts["zones"] == ["Piem-B"]
    # None within 50 km of Pray
    assert risks["earthquakes"]["data"] == []
    heat = risks["heat"]["data"]
    assert heat["city"] == "biella"
    assert heat["days"]["2026-09-30"] == "green"
    assert risks["avalanches"] is None


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


async def test_diagnostics_of_the_risks(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the diagnostics of the device of the risks of the municipality."""
    device = device_of(hass, init_integration.entry_id, PRAY_ENTRY_ID)
    assert device is not None

    diagnostics = await get_diagnostics_for_device(
        hass, hass_client, init_integration, device
    )

    alerts = diagnostics["risks"]["alerts"]["data"]
    assert alerts["bulletin"] == "334/2026"
    assert alerts["current_danger"] == "green"


@pytest.mark.parametrize("widget", [HTTPStatus.SERVICE_UNAVAILABLE])
async def test_diagnostics_without_the_risks(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the diagnostics of the risks while the widget does not answer."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    alerts = diagnostics["risks"]["alerts"]
    assert alerts["last_update_success"] is False
    assert "The natural risks of Pray are not available" in alerts["error"]
    assert alerts["data"] is None


async def test_diagnostics_from_the_home(
    hass: HomeAssistant,
    mock_sources: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that what would locate the home is redacted, and no distance given.

    The home is at Bardonecchia, in a micro-region, 32.8 km from an earthquake
    in France, the only one within 50 km.
    """
    del mock_sources
    hass.config.latitude, hass.config.longitude = BARDONECCHIA
    entry = municipality_entry(
        PRAY_MUNICIPALITY,
        "Pray",
        station_subentry(PRAY_DATA, "Sessera"),
        options={CONF_POSITION: "home", CONF_HEAT_CITY: "nearest"},
    )
    await setup_integration(hass, entry)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    risks = diagnostics["risks"]
    assert risks["place"] == {
        "position": "home",
        "located": True,
        "micro_region": REDACTED,
        "heat_city": REDACTED,
    }
    assert risks["heat"]["data"]["city"] == REDACTED
    assert risks["avalanches"]["data"] == {"region": REDACTED, "bulletins": {}}
    (earthquake,) = risks["earthquakes"]["data"]
    assert earthquake["district"] == "Francia"
    assert "distance" not in str(diagnostics)
