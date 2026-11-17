"""Tests of the config flow: adding and reading again a station."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

from aioarpapiemonte import (
    ArpaPiemonteClient,
    ArpaPiemonteConnectionError,
    Param,
    RealtimeStation,
    Sensor,
)
from aioarpapiemonte.parsers import parse_pie_anag
from aiometeo3r import Meteo3rClient, Meteo3rConnectionError, Station
from aiometeo3r.parsers import parse_registry
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arpa_piemonte.const import (
    CONF_SENSOR_ID,
    CONF_STATION_CODE,
    DOMAIN,
)

from . import PRAY, PRAY_DATA, PRAY_SENSOR, TITLE, UNIQUE_ID, fixture_json

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

STATIONS: tuple[Station, ...] = parse_registry(fixture_json("misureAnagrafica.json"))
REALTIME: tuple[RealtimeStation, ...] = parse_pie_anag(fixture_json("pie_anag.json"))
PRAY_ON_THE_WEBSITE = Sensor(
    id=PRAY_SENSOR,
    name="PRAY SESSERA",
    latitude=45.67389,
    longitude=8.22167,
    altitude=409.0,
    params=frozenset({Param.LEVEL, Param.TEMPERATURE}),
)
DOWN = Meteo3rConnectionError("down")
ARPA_DOWN = ArpaPiemonteConnectionError("down")


@dataclass
class Clients:
    """The mocked methods of the clients of the sources."""

    get_stations: AsyncMock
    get_station_data: AsyncMock
    get_realtime_stations: AsyncMock
    get_realtime_data: AsyncMock
    get_sensors: AsyncMock


@pytest.fixture
def clients() -> Generator[Clients]:
    """Mock the clients: every source answers for Pray Sessera."""
    with (
        patch.object(Meteo3rClient, "get_stations", return_value=STATIONS) as stations,
        patch.object(Meteo3rClient, "get_station_data") as station_data,
        patch.object(
            ArpaPiemonteClient, "get_realtime_stations", return_value=REALTIME
        ) as realtime_stations,
        patch.object(ArpaPiemonteClient, "get_realtime_data") as realtime_data,
        patch.object(
            ArpaPiemonteClient, "get_sensors", return_value=(PRAY_ON_THE_WEBSITE,)
        ) as sensors,
    ):
        yield Clients(stations, station_data, realtime_stations, realtime_data, sensors)


async def start(hass: HomeAssistant) -> Any:
    """Start the flow of a new station."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def choose(hass: HomeAssistant, flow_id: str, code: str = PRAY) -> Any:
    """Choose a station in the flow."""
    return await hass.config_entries.flow.async_configure(
        flow_id, {CONF_STATION_CODE: code}
    )


async def test_add_a_station(hass: HomeAssistant, clients: Clients) -> None:
    """Test that a station is added with its identifiers, sensors and thresholds."""
    result = await start(hass)
    assert result["type"] is FlowResultType.FORM
    options = result["data_schema"].schema[CONF_STATION_CODE].config["options"]
    assert len(options) == 374
    assert {"value": PRAY, "label": "Pray Sessera — Sessera (Pray)"} in options

    result = await choose(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == PRAY_DATA
    assert result["result"].unique_id == UNIQUE_ID
    clients.get_realtime_data.assert_not_called()


async def test_station_list_of_the_api_realtime(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test that the stations come from the api_realtime when Meteo 3R fails."""
    clients.get_stations.side_effect = DOWN
    clients.get_station_data.side_effect = DOWN

    result = await choose(hass, (await start(hass))["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pray Sessera"
    assert result["data"][CONF_SENSOR_ID] == PRAY_SENSOR
    clients.get_realtime_data.assert_awaited_once_with(PRAY)


async def test_no_station_list(hass: HomeAssistant, clients: Clients) -> None:
    """Test that the flow stops when no list of the stations answers."""
    clients.get_stations.side_effect = DOWN
    clients.get_realtime_stations.side_effect = ARPA_DOWN

    result = await start(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_station_that_does_not_answer(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test the error when the station does not answer, then the retry."""
    clients.get_station_data.side_effect = DOWN
    clients.get_realtime_data.side_effect = ARPA_DOWN
    result = await start(hass)

    result = await choose(hass, result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    clients.get_station_data.side_effect = None
    result = await choose(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_station_already_added(hass: HomeAssistant, clients: Clients) -> None:
    """Test that a station can be added once."""
    del clients
    MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE_ID, data=PRAY_DATA).add_to_hass(
        hass
    )

    result = await choose(hass, (await start(hass))["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_identifier_by_coordinates(hass: HomeAssistant, clients: Clients) -> None:
    """Test the identifier on the website from the coordinates, without api_realtime."""
    clients.get_realtime_stations.side_effect = ARPA_DOWN

    result = await choose(hass, (await start(hass))["flow_id"])

    assert result["data"][CONF_SENSOR_ID] == PRAY_SENSOR


async def test_identifier_not_on_the_website(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test that an identifier the website does not list is not kept."""
    clients.get_sensors.return_value = ()

    result = await choose(hass, (await start(hass))["flow_id"])

    assert result["data"][CONF_SENSOR_ID] is None


async def test_identifier_when_the_website_list_fails(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test that the identifier of the api_realtime is kept without the website list."""
    clients.get_sensors.side_effect = ARPA_DOWN

    result = await choose(hass, (await start(hass))["flow_id"])

    assert result["data"][CONF_SENSOR_ID] == PRAY_SENSOR


async def test_read_a_station_again(hass: HomeAssistant, clients: Clients) -> None:
    """Test that reconfiguring reads the station again, under the same ID."""
    del clients
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        title=TITLE,
        data={**PRAY_DATA, CONF_SENSOR_ID: None},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == PRAY_DATA


async def test_read_a_station_again_without_answer(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test the error when the station cannot be read again."""
    clients.get_stations.side_effect = DOWN
    clients.get_realtime_stations.side_effect = ARPA_DOWN
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=UNIQUE_ID, title=TITLE, data=PRAY_DATA
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
