"""Tests of the avalanche danger of the micro-region of a municipality (EAWS)."""

from __future__ import annotations

from http import HTTPStatus

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import ATTR_OPTIONS
from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.arpa_piemonte.const import (
    AVALANCHES_OFF_SEASON_INTERVAL,
    AVALANCHES_UPDATE_INTERVAL,
    CONF_POSITION,
)
from custom_components.arpa_piemonte.coordinator import AvalanchesCoordinator

from . import (
    AVALANCHE_DAY,
    fixture_json,
    municipality_entry,
    serve_the_risks,
    setup_integration,
)

VINADIO = "004248"
COLLE_LOMBARDA = (44.20778, 7.14778)
"""The station of Colle Lombarda, at 2305 m in Vinadio: micro-region
IT-21-CN-03, Valle Stura, moderate on 2026-04-18."""
MORNING = "2026-04-18 06:00:00+00:00"
"""08:00 in Italy on the day of the bulletins of the fixture."""
DANGER_TODAY = "sensor.arpa_piemonte_vinadio_avalanche_danger_today"
DANGER_TOMORROW = "sensor.arpa_piemonte_vinadio_avalanche_danger_tomorrow"


def state(hass: HomeAssistant, entity_id: str) -> str:
    """Return the state of an entity."""
    entity = hass.states.get(entity_id)
    assert entity is not None
    return entity.state


def vinadio() -> MockConfigEntry:
    """Return the entry of Vinadio, its risks taken from a home at Colle Lombarda.

    Without stations: the risks need none.
    """
    return municipality_entry(VINADIO, "Vinadio", options={CONF_POSITION: "home"})


def avalanches_of(entry: MockConfigEntry) -> AvalanchesCoordinator:
    """Return the coordinator of the avalanches of an entry."""
    coordinator = entry.runtime_data.risks.avalanches
    assert coordinator is not None
    return coordinator


async def test_avalanche_danger_in_season(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the danger of today in Valle Stura, tomorrow not published yet."""
    freezer.move_to(MORNING)
    hass.config.latitude, hass.config.longitude = COLLE_LOMBARDA
    aioclient_mock.clear_requests()
    serve_the_risks(
        aioclient_mock,
        avalanches={AVALANCHE_DAY: fixture_json(f"{AVALANCHE_DAY}-IT-21.json")},
    )
    entry = vinadio()

    await setup_integration(hass, entry)

    today = hass.states.get(DANGER_TODAY)
    assert today is not None
    assert today.state == "moderate"
    assert today.attributes[ATTR_OPTIONS] == [
        "no_snow",
        "low",
        "moderate",
        "considerable",
        "high",
        "very_high",
    ]
    assert today.attributes[ATTR_ATTRIBUTION] == (
        "Fonte: AINEVA Piemonte - bollettini.aineva.it"
    )
    assert state(hass, DANGER_TOMORROW) == STATE_UNKNOWN
    assert state(hass, "sensor.arpa_piemonte_vinadio_avalanche_region") == "Valle Stura"
    assert avalanches_of(entry).update_interval == AVALANCHES_UPDATE_INTERVAL


async def test_tomorrow_becomes_today_at_midnight(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the bulletin of tomorrow is that of today after midnight."""
    freezer.move_to("2026-04-17 21:30:00+00:00")  # 23:30 in Italy
    hass.config.latitude, hass.config.longitude = COLLE_LOMBARDA
    aioclient_mock.clear_requests()
    serve_the_risks(
        aioclient_mock,
        avalanches={AVALANCHE_DAY: fixture_json(f"{AVALANCHE_DAY}-IT-21.json")},
    )
    entry = vinadio()
    await setup_integration(hass, entry)
    assert state(hass, DANGER_TODAY) == STATE_UNKNOWN
    assert state(hass, DANGER_TOMORROW) == "moderate"
    # No bulletin today: asked again in 6 hours, as out of season
    assert avalanches_of(entry).update_interval == AVALANCHES_OFF_SEASON_INTERVAL

    freezer.move_to("2026-04-17 22:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert state(hass, DANGER_TODAY) == "moderate"
    assert state(hass, DANGER_TOMORROW) == STATE_UNKNOWN


async def test_avalanches_out_of_season(
    hass: HomeAssistant, mock_sources: AiohttpClientMocker
) -> None:
    """Test that out of season, in November, there is no bulletin to show."""
    del mock_sources
    hass.config.latitude, hass.config.longitude = COLLE_LOMBARDA
    entry = vinadio()

    await setup_integration(hass, entry)

    assert state(hass, DANGER_TODAY) == STATE_UNKNOWN
    assert state(hass, DANGER_TOMORROW) == STATE_UNKNOWN
    assert avalanches_of(entry).update_interval == AVALANCHES_OFF_SEASON_INTERVAL


async def test_avalanches_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the danger is unavailable while EAWS fails."""
    hass.config.latitude, hass.config.longitude = COLLE_LOMBARDA
    aioclient_mock.clear_requests()
    serve_the_risks(
        aioclient_mock,
        avalanches={"2026-11-17": HTTPStatus.SERVICE_UNAVAILABLE},
    )

    await setup_integration(hass, vinadio())

    assert state(hass, DANGER_TODAY) == STATE_UNAVAILABLE


async def test_no_avalanches_out_of_the_micro_regions(hass: HomeAssistant) -> None:
    """Test that Pray, in no micro-region, has no avalanche danger."""
    hass.config.latitude, hass.config.longitude = 45.67389, 8.22167

    await setup_integration(
        hass, municipality_entry("096050", "Pray", options={CONF_POSITION: "home"})
    )

    assert hass.states.get("sensor.arpa_piemonte_pray_avalanche_danger_today") is None


async def test_bulletin_without_the_micro_region(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a bulletin of today that leaves out the micro-region: in season."""
    freezer.move_to(MORNING)
    hass.config.latitude, hass.config.longitude = COLLE_LOMBARDA
    bulletin = fixture_json(f"{AVALANCHE_DAY}-IT-21.json")
    for item in bulletin["bulletins"]:
        item["regions"] = [
            region for region in item["regions"] if region["regionID"] != "IT-21-CN-03"
        ]
    aioclient_mock.clear_requests()
    serve_the_risks(aioclient_mock, avalanches={AVALANCHE_DAY: bulletin})
    entry = vinadio()

    await setup_integration(hass, entry)

    assert state(hass, DANGER_TODAY) == STATE_UNKNOWN
    assert avalanches_of(entry).update_interval == AVALANCHES_UPDATE_INTERVAL
