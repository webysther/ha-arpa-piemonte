"""Tests of the natural risks of a municipality, from its widget on the Arpa website."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from typing import Any

from aioarpapiemonte import AlertLevel, MunicipalityAlerts, OperationalPhase
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import ATTR_OPTIONS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.arpa_piemonte.const import CONF_WARNING_LEVEL
from custom_components.arpa_piemonte.risks import (
    RiskDay,
    highest_alert,
    italian_date,
    warning_level,
    widget_page_url,
)

from . import (
    PRAY_DATA,
    PRAY_ENTRY_ID,
    PRAY_MUNICIPALITY,
    WIDGETS,
    device_of,
    entity_id_of,
    fixture_json,
    municipality_entry,
    serve_meteo3r,
    serve_widget,
    setup_integration,
    station_subentry,
    subentry_of_device,
)

AFTERNOON = "2026-11-17 12:00:00+00:00"
"""13:00 in Italy on 2026-11-17, after the bulletin of the widgets: its first
day is today, its second tomorrow."""

MORNING = "2026-11-18 06:04:00+00:00"
"""07:04 in Italy on 2026-11-18, when the widgets were downloaded: the second
day of their bulletin is today, and tomorrow is not known yet."""

ETAG = '"9dd-6648a29b4a6e0"'
"""The ETag of a widget, as the header aiohttp names "Etag" when it parses an
answer of the Arpa website (which sends "ETag"): the mock keeps the name as
given, and aioarpapiemonte looks for the name of aiohttp."""


def widget_with(**changes: str) -> dict[str, Any]:
    """Return the widget of Pray with some of its texts changed."""
    return {**fixture_json("widget_096050.json"), **changes}


ALERTS = widget_with(
    temporali_day_0="GIALLO", idraulico_day_1="ARANCIONE", neve_day_1="ROSSA"
)
"""The widget of Pray with alerts: storms on its first day; the river orange
and the snow red on its second."""


def state(hass: HomeAssistant, key: str, platform: str = "sensor") -> str:
    """Return the state of an entity of the risks of Pray, by its key."""
    entity = hass.states.get(entity_id_of(hass, key, PRAY_ENTRY_ID, platform))
    assert entity is not None
    return entity.state


async def test_device_of_the_risks(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the device of the risks: of the entry, linked to the widget page."""
    device = device_of(hass, init_integration.entry_id, PRAY_ENTRY_ID)

    assert device is not None
    assert subentry_of_device(device) is None
    assert device.name == "Pray · Natural risks"
    assert device.manufacturer == "Arpa Piemonte"
    assert device.model_id == PRAY_MUNICIPALITY
    assert device.configuration_url == (
        "https://www.arpa.piemonte.it/rischi_naturali/widget/comuni/096050/"
    )
    entities = er.async_entries_for_device(er.async_get(hass), device.id)
    assert len(entities) == 26
    assert {entity.config_subentry_id for entity in entities} == {None}
    highest = hass.states.get("sensor.arpa_piemonte_pray_highest_alert")
    assert highest is not None
    assert highest.attributes[ATTR_ATTRIBUTION].startswith("Fonte: Arpa Piemonte")
    assert highest.attributes[ATTR_OPTIONS] == [
        "not_evaluated",
        "green",
        "yellow",
        "orange",
        "red",
    ]
    risk = hass.states.get("binary_sensor.arpa_piemonte_pray_hydraulic_risk_tomorrow")
    assert risk is not None
    assert risk.attributes[ATTR_DEVICE_CLASS] == "safety"


@pytest.mark.parametrize("widget", [ALERTS])
async def test_risks_of_today_and_tomorrow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sources: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the risks in the afternoon: the two days of the bulletin."""
    del mock_sources
    freezer.move_to(AFTERNOON)

    await setup_integration(hass, mock_config_entry)

    assert state(hass, "thunderstorm_risk_level_today") == "yellow"
    assert state(hass, "hydraulic_risk_level_today") == "green"
    assert state(hass, "hydraulic_risk_level_tomorrow") == "orange"
    assert state(hass, "snow_risk_level_tomorrow") == "red"
    assert state(hass, "avalanche_risk_level_today") == "not_evaluated"
    assert state(hass, "thunderstorm_risk_today", "binary_sensor") == "on"
    assert state(hass, "hydraulic_risk_today", "binary_sensor") == "off"
    assert state(hass, "hydraulic_risk_tomorrow", "binary_sensor") == "on"
    assert state(hass, "avalanche_risk_tomorrow", "binary_sensor") == "off"
    assert state(hass, "highest_alert") == "red"
    assert state(hass, "current_danger") == "green"
    assert state(hass, "operational_phase") == "none"
    assert state(hass, "alert_zone") == "Piem-B"
    assert state(hass, "alert_bulletin") == "2026-11-17T10:57:30+00:00"
    assert state(hass, "next_alert_bulletin") == "2026-11-18T12:00:00+00:00"


@pytest.mark.parametrize("widget", [ALERTS])
async def test_risks_in_the_morning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sources: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that before the bulletin of the day, tomorrow is not known."""
    del mock_sources
    freezer.move_to(MORNING)

    await setup_integration(hass, mock_config_entry)

    assert state(hass, "hydraulic_risk_level_today") == "orange"
    assert state(hass, "thunderstorm_risk_level_today") == "green"
    assert state(hass, "snow_risk_today", "binary_sensor") == "on"
    assert state(hass, "hydraulic_risk_level_tomorrow") == STATE_UNKNOWN
    assert state(hass, "hydraulic_risk_tomorrow", "binary_sensor") == STATE_UNKNOWN
    assert state(hass, "highest_alert") == "red"


@pytest.mark.parametrize("widget", [ALERTS])
async def test_tomorrow_becomes_today_at_midnight(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sources: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the days move at midnight in Italy, without a new bulletin."""
    del mock_sources
    freezer.move_to("2026-11-17 22:59:00+00:00")  # 23:59 in Italy
    await setup_integration(hass, mock_config_entry)
    assert state(hass, "hydraulic_risk_level_today") == "green"
    assert state(hass, "hydraulic_risk_level_tomorrow") == "orange"

    freezer.move_to("2026-11-17 23:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert state(hass, "hydraulic_risk_level_today") == "orange"
    assert state(hass, "hydraulic_risk_level_tomorrow") == STATE_UNKNOWN

    # A day later, the bulletin no longer covers today
    freezer.move_to("2026-11-18 23:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert state(hass, "hydraulic_risk_level_today") == STATE_UNKNOWN
    assert state(hass, "hydraulic_risk_today", "binary_sensor") == STATE_UNKNOWN
    assert state(hass, "highest_alert") == STATE_UNKNOWN


@pytest.mark.parametrize("widget", [ALERTS])
@pytest.mark.parametrize(
    ("level", "storms_today", "river_tomorrow", "snow_tomorrow"),
    [
        ("yellow", "on", "on", "on"),
        ("orange", "off", "on", "on"),
        ("red", "off", "off", "on"),
    ],
)
async def test_warning_level(
    hass: HomeAssistant,
    mock_sources: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    level: str,
    storms_today: str,
    river_tomorrow: str,
    snow_tomorrow: str,
) -> None:
    """Test that the risks are on from the warning level of the options."""
    del mock_sources
    freezer.move_to(AFTERNOON)
    entry = municipality_entry(
        PRAY_MUNICIPALITY,
        "Pray",
        station_subentry(PRAY_DATA, "Sessera"),
        options={CONF_WARNING_LEVEL: level},
    )

    await setup_integration(hass, entry)

    assert state(hass, "thunderstorm_risk_today", "binary_sensor") == storms_today
    assert state(hass, "hydraulic_risk_tomorrow", "binary_sensor") == river_tomorrow
    assert state(hass, "snow_risk_tomorrow", "binary_sensor") == snow_tomorrow


@pytest.mark.parametrize(
    ("widget", "danger", "phase"),
    [
        (
            widget_with(
                pericolo_attuale="ARANCIONE", fase_operativa_comunale_attuata="Allarme"
            ),
            "orange",
            "alarm",
        ),
        (
            widget_with(
                pericolo_attuale="GIALLO",
                fase_operativa_comunale_attuata="Preallarme",
            ),
            "yellow",
            "pre_alarm",
        ),
        (
            widget_with(
                pericolo_attuale="VIOLA", fase_operativa_comunale_attuata="Fase nuova"
            ),
            STATE_UNKNOWN,
            STATE_UNKNOWN,
        ),
    ],
)
async def test_danger_now_and_operational_phase(
    hass: HomeAssistant, init_integration: MockConfigEntry, danger: str, phase: str
) -> None:
    """Test the danger now and the phase; unknown for a text the library lacks."""
    del init_integration
    assert state(hass, "current_danger") == danger
    assert state(hass, "operational_phase") == phase


@pytest.mark.parametrize("widget", [widget_with(zone_di_allerta="")])
async def test_no_alert_zone(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that the zone is unknown when the widget gives none."""
    del init_integration
    assert state(hass, "alert_zone") == STATE_UNKNOWN


@pytest.mark.parametrize("widget", [fixture_json("widget_005005.json")])
async def test_municipality_in_two_zones_without_stations(hass: HomeAssistant) -> None:
    """Test Asti, in two alert zones: a municipality without stations has its risks."""
    entry = municipality_entry("005005", "Asti")

    await setup_integration(hass, entry)

    zone = hass.states.get("sensor.arpa_piemonte_asti_alert_zone")
    assert zone is not None
    assert zone.state == "Piem-G, Piem-L"
    assert entry.runtime_data.stations == {}


@pytest.mark.parametrize("widget", [HTTPStatus.SERVICE_UNAVAILABLE])
async def test_risks_unavailable_at_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sources: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the stations do not wait for the risks, asked again later."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "The natural risks of Pray are not available" in caplog.text
    assert state(hass, "highest_alert") == STATE_UNAVAILABLE
    assert state(hass, "hydraulic_risk_today", "binary_sensor") == STATE_UNAVAILABLE
    level = hass.states.get("sensor.arpa_piemonte_pray_sessera_level")
    assert level is not None
    assert level.state == "0.86"

    mock_sources.clear_requests()
    serve_widget(mock_sources, fixture_json("widget_096050.json"))
    await mock_config_entry.runtime_data.risks.async_refresh()
    await hass.async_block_till_done()

    # At 03:40 in Italy on 2026-11-17, the first day of the bulletin
    assert state(hass, "highest_alert") == "green"


async def test_unchanged_widget_writes_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a 304 of the widget writes nothing, asked with its ETag."""
    aioclient_mock.clear_requests()
    serve_meteo3r(aioclient_mock)
    serve_widget(aioclient_mock, fixture_json("widget_096050.json"), {"Etag": ETAG})
    await setup_integration(hass, mock_config_entry)
    before = hass.states.get("sensor.arpa_piemonte_pray_highest_alert")
    assert before is not None
    # Home Assistant updates the time of the state it has, when written again
    reported = before.last_reported

    aioclient_mock.clear_requests()
    serve_widget(aioclient_mock, HTTPStatus.NOT_MODIFIED, {"Etag": ETAG})
    freezer.tick(timedelta(minutes=10))
    await mock_config_entry.runtime_data.risks.async_refresh()
    await hass.async_block_till_done()

    after = hass.states.get("sensor.arpa_piemonte_pray_highest_alert")
    assert after is not None
    assert after.state == "green"
    assert after.last_reported == reported
    ((_, url, _, headers),) = aioclient_mock.mock_calls
    assert WIDGETS.search(str(url))
    assert headers["If-None-Match"] == ETAG


async def test_failed_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the risks are unavailable while the widget does not answer."""
    aioclient_mock.clear_requests()
    serve_widget(aioclient_mock, HTTPStatus.INTERNAL_SERVER_ERROR)

    await init_integration.runtime_data.risks.async_refresh()
    await hass.async_block_till_done()

    assert state(hass, "current_danger") == STATE_UNAVAILABLE
    assert "The natural risks of Pray are not available" in caplog.text


async def test_unload_stops_the_days(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an unloaded municipality no longer follows the days.

    A change of day left behind would fire, then wait for the next midnight:
    a timer that the harness finds lingering after the test.
    """
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    freezer.move_to("2026-11-17 23:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


def test_days() -> None:
    """Test the dates of the days, in Italy whatever the time zone."""
    today = date(2026, 11, 17)

    assert RiskDay.TODAY.date(today) == today
    assert RiskDay.TOMORROW.date(today) == date(2026, 11, 18)
    # 23:30 UTC is already the next day in Italy, in winter and in summer
    assert italian_date(datetime(2026, 11, 17, 23, 30, tzinfo=UTC)) == date(
        2026, 11, 18
    )
    assert italian_date(datetime(2026, 7, 17, 22, 30, tzinfo=UTC)) == date(2026, 7, 18)


@pytest.mark.parametrize(
    ("options", "level"),
    [
        ({}, AlertLevel.YELLOW),
        ({CONF_WARNING_LEVEL: "orange"}, AlertLevel.ORANGE),
        ({CONF_WARNING_LEVEL: "red"}, AlertLevel.RED),
        ({CONF_WARNING_LEVEL: "green"}, AlertLevel.YELLOW),
    ],
)
def test_warning_level_of_the_options(
    options: dict[str, Any], level: AlertLevel
) -> None:
    """Test the warning level of the options: yellow without one, or a wrong one."""
    assert warning_level(options) is level


def test_highest_alert_without_the_days() -> None:
    """Test that the highest alert is unknown when the bulletin covers neither day."""
    alerts = MunicipalityAlerts(
        municipality_code=PRAY_MUNICIPALITY,
        name="Pray",
        alert=AlertLevel.GREEN,
        risks=(),
        current_danger=AlertLevel.GREEN,
        current_danger_time=None,
        phase=OperationalPhase.UNKNOWN,
        phase_text=None,
        phase_time=None,
        bulletin=None,
        issued=None,
        issue_day=None,
        next_update=None,
        zones=(),
    )

    assert highest_alert(alerts, date(2026, 11, 17)) is AlertLevel.UNKNOWN


def test_widget_page() -> None:
    """Test the page of the widget of a municipality, linked from its device."""
    assert widget_page_url("001272") == (
        "https://www.arpa.piemonte.it/rischi_naturali/widget/comuni/001272/"
    )
