"""Tests of the config flow: a municipality and its stations."""

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
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arpa_piemonte.const import (
    CONF_MUNICIPALITY,
    CONF_MUNICIPALITY_CODE,
    CONF_SENSOR_ID,
    CONF_SENSOR_LETTERS,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_THRESHOLDS,
    CONF_WEBSITE_PARAMS,
    DOMAIN,
    SUBENTRY_STATION,
)

from . import (
    PRAY,
    PRAY_DATA,
    PRAY_ENTRY_ID,
    PRAY_MUNICIPALITY,
    PRAY_SENSOR,
    UNIQUE_ID,
    fixture_json,
    municipality_entry,
    station_subentry,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

STATIONS: tuple[Station, ...] = parse_registry(fixture_json("misureAnagrafica.json"))
REALTIME: tuple[RealtimeStation, ...] = parse_pie_anag(fixture_json("pie_anag.json"))
PRAY_ON_THE_WEBSITE = Sensor(
    id=PRAY_SENSOR,
    name="PRAY SESSERA",
    latitude=45.67389,
    longitude=8.22167,
    altitude=409.0,
    params=frozenset({Param.LEVEL, Param.RAIN_10_MIN, Param.TEMPERATURE}),
)
DOWN = Meteo3rConnectionError("down")
ARPA_DOWN = ArpaPiemonteConnectionError("down")

MONDOVI = "004130"
MONDOVI_TOWN = "315"
"""The weather station of Mondovi', named after it."""
MONDOVI_ELLERO = "386"
"""The hydrometer of Mondovi', on the Ellero."""
MONDOVI_TOWN_DATA: dict[str, Any] = {
    CONF_STATION_CODE: MONDOVI_TOWN,
    CONF_STATION_NAME: "Mondovi'",
    CONF_SENSOR_ID: None,
    CONF_SENSOR_LETTERS: "PT",
    CONF_THRESHOLDS: {},
}


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
    """Mock the clients: every source answers, Pray Sessera on the website."""
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


async def choose(hass: HomeAssistant, flow_id: str, municipality: str = "Pray") -> Any:
    """Choose or type a municipality in the flow."""
    return await hass.config_entries.flow.async_configure(
        flow_id, {CONF_MUNICIPALITY: municipality}
    )


async def choose_station(hass: HomeAssistant, flow_id: str, code: str) -> Any:
    """Choose a station of the municipality in the flow."""
    return await hass.config_entries.flow.async_configure(
        flow_id, {CONF_STATION_CODE: code}
    )


def options_of(result: Any, field: str) -> list[Any]:
    """Return the options of a field of a form."""
    options: list[Any] = result["data_schema"].schema[field].config["options"]
    return options


def mondovi_entry() -> MockConfigEntry:
    """Return the entry of Mondovi' with its weather station only."""
    return municipality_entry(
        MONDOVI, "Mondovi'", station_subentry(MONDOVI_TOWN_DATA, "Mondovi'")
    )


async def test_add_a_municipality_with_one_station(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test that a municipality with one station is added with it at once."""
    result = await start(hass)
    assert result["type"] is FlowResultType.FORM
    municipalities = options_of(result, CONF_MUNICIPALITY)
    assert len(municipalities) == 278
    assert municipalities[:2] == ["Acceglio", "Acqui Terme"]
    assert "Pray" in municipalities

    result = await choose(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pray"
    assert result["data"] == {CONF_MUNICIPALITY_CODE: PRAY_MUNICIPALITY}
    entry = result["result"]
    assert entry.unique_id == PRAY_ENTRY_ID
    (subentry,) = entry.subentries.values()
    assert subentry.subentry_type == SUBENTRY_STATION
    assert subentry.title == "Sessera"
    assert subentry.unique_id == UNIQUE_ID
    assert dict(subentry.data) == PRAY_DATA
    clients.get_realtime_data.assert_not_called()


async def test_add_a_station_of_a_municipality_with_several(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test a municipality typed by hand, then its station: the rivers first."""
    del clients
    result = await choose(hass, (await start(hass))["flow_id"], " mondovì ")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station"
    assert result["description_placeholders"] == {"municipality": "Mondovi'"}
    assert options_of(result, CONF_STATION_CODE) == [
        {"value": MONDOVI_ELLERO, "label": "Ellero — Mondovi' Ellero"},
        {"value": MONDOVI_TOWN, "label": "Mondovi'"},
    ]

    result = await choose_station(hass, result["flow_id"], MONDOVI_ELLERO)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mondovi'"
    (subentry,) = result["result"].subentries.values()
    assert subentry.title == "Ellero"
    assert subentry.data[CONF_STATION_NAME] == "Mondovi' Ellero"


async def test_municipality_not_listed(hass: HomeAssistant, clients: Clients) -> None:
    """Test that a municipality without a station is refused."""
    del clients
    result = await choose(hass, (await start(hass))["flow_id"], "Roma")

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MUNICIPALITY: "municipality_not_listed"}


async def test_station_list_of_the_api_realtime(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test that the stations come from the api_realtime when Meteo 3R fails."""
    clients.get_stations.side_effect = DOWN
    clients.get_station_data.side_effect = DOWN

    result = await choose(hass, (await start(hass))["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pray"
    (subentry,) = result["result"].subentries.values()
    assert dict(subentry.data) == PRAY_DATA
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
    """Test the error when the only station does not answer, then the retry."""
    clients.get_station_data.side_effect = DOWN
    clients.get_realtime_data.side_effect = ARPA_DOWN
    result = await start(hass)

    result = await choose(hass, result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    clients.get_station_data.side_effect = None
    result = await choose(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_chosen_station_that_does_not_answer(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test the error when the chosen station does not answer, then the retry."""
    clients.get_station_data.side_effect = DOWN
    clients.get_realtime_data.side_effect = ARPA_DOWN
    result = await choose(hass, (await start(hass))["flow_id"], "Mondovi'")

    result = await choose_station(hass, result["flow_id"], MONDOVI_TOWN)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station"
    assert result["errors"] == {"base": "cannot_connect"}

    clients.get_station_data.side_effect = None
    result = await choose_station(hass, result["flow_id"], MONDOVI_TOWN)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_station_added_to_its_municipality(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test that a station of a municipality already added joins it."""
    del clients
    entry = mondovi_entry()
    entry.add_to_hass(hass)

    result = await choose(hass, (await start(hass))["flow_id"], "Mondovi'")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "station_added"
    assert result["description_placeholders"] == {
        "station": "Mondovi' Ellero",
        "municipality": "Mondovi'",
    }
    assert {subentry.title for subentry in entry.subentries.values()} == {
        "Mondovi'",
        "Ellero",
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_every_station_already_added(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test that a municipality with every station added is refused."""
    del clients
    municipality_entry(
        PRAY_MUNICIPALITY, "Pray", station_subentry(PRAY_DATA, "Sessera")
    ).add_to_hass(hass)

    result = await choose(hass, (await start(hass))["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_identifier_by_coordinates(hass: HomeAssistant, clients: Clients) -> None:
    """Test the identifier on the website from the coordinates, without api_realtime."""
    clients.get_realtime_stations.side_effect = ARPA_DOWN

    result = await choose(hass, (await start(hass))["flow_id"])

    (subentry,) = result["result"].subentries.values()
    assert subentry.data[CONF_SENSOR_ID] == PRAY_SENSOR
    assert subentry.data[CONF_WEBSITE_PARAMS] == ["idro", "pluv", "terma"]


async def test_identifier_not_on_the_website(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test that an identifier the website does not list is not kept, nor files."""
    clients.get_sensors.return_value = ()

    result = await choose(hass, (await start(hass))["flow_id"])

    (subentry,) = result["result"].subentries.values()
    assert subentry.data[CONF_SENSOR_ID] is None
    assert subentry.data[CONF_WEBSITE_PARAMS] == []


async def test_identifier_when_the_website_list_fails(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test that the identifier of the api_realtime is kept without the website list.

    Its files are unknown: the letters of its sensors stand in for them.
    """
    clients.get_sensors.side_effect = ARPA_DOWN

    result = await choose(hass, (await start(hass))["flow_id"])

    (subentry,) = result["result"].subentries.values()
    assert subentry.data[CONF_SENSOR_ID] == PRAY_SENSOR
    assert subentry.data[CONF_WEBSITE_PARAMS] is None


async def test_read_a_municipality_again(hass: HomeAssistant, clients: Clients) -> None:
    """Test that reconfiguring reads every station again, keeping its name."""
    del clients
    entry = municipality_entry(
        PRAY_MUNICIPALITY,
        "Pray",
        station_subentry(
            {**PRAY_DATA, CONF_SENSOR_ID: None, CONF_STATION_NAME: "My river"},
            "Sessera",
        ),
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"] == {"municipality": "Pray"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    (subentry,) = entry.subentries.values()
    assert dict(subentry.data) == {**PRAY_DATA, CONF_STATION_NAME: "My river"}


@pytest.mark.parametrize("failure", ["no_list", "no_station", "not_listed"])
async def test_read_a_municipality_again_without_answer(
    hass: HomeAssistant, clients: Clients, failure: str
) -> None:
    """Test the error when a station cannot be read again: none is changed."""
    if failure == "no_list":
        clients.get_stations.side_effect = DOWN
        clients.get_realtime_stations.side_effect = ARPA_DOWN
    elif failure == "no_station":
        clients.get_station_data.side_effect = DOWN
        clients.get_realtime_data.side_effect = ARPA_DOWN
    else:
        clients.get_stations.return_value = ()
    entry = municipality_entry(
        PRAY_MUNICIPALITY,
        "Pray",
        station_subentry({**PRAY_DATA, CONF_SENSOR_ID: None}, "Sessera"),
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    (subentry,) = entry.subentries.values()
    assert subentry.data[CONF_SENSOR_ID] is None


async def start_subentry(hass: HomeAssistant, entry: MockConfigEntry) -> Any:
    """Start the flow of another station of a municipality."""
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_STATION), context={"source": SOURCE_USER}
    )


async def test_add_another_station(hass: HomeAssistant, clients: Clients) -> None:
    """Test that another station is added from the entry of its municipality."""
    del clients
    entry = mondovi_entry()
    entry.add_to_hass(hass)

    result = await start_subentry(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {"municipality": "Mondovi'"}
    assert options_of(result, CONF_STATION_CODE) == [
        {"value": MONDOVI_ELLERO, "label": "Ellero — Mondovi' Ellero"}
    ]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STATION_CODE: MONDOVI_ELLERO}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    added = next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.unique_id == "PIE_386"
    )
    assert added.title == "Ellero"
    assert added.data[CONF_STATION_NAME] == "Mondovi' Ellero"


async def test_another_station_that_does_not_answer(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test the error when the other station does not answer."""
    clients.get_station_data.side_effect = DOWN
    clients.get_realtime_data.side_effect = ARPA_DOWN
    entry = mondovi_entry()
    entry.add_to_hass(hass)

    result = await start_subentry(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STATION_CODE: MONDOVI_ELLERO}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_other_station(hass: HomeAssistant, clients: Clients) -> None:
    """Test that a municipality with every station added offers none."""
    del clients
    entry = municipality_entry(
        PRAY_MUNICIPALITY, "Pray", station_subentry(PRAY_DATA, "Sessera")
    )
    entry.add_to_hass(hass)

    result = await start_subentry(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_other_station"
    assert result["description_placeholders"] == {"municipality": "Pray"}


async def test_no_other_station_list(hass: HomeAssistant, clients: Clients) -> None:
    """Test that the flow of another station stops without a list."""
    clients.get_stations.side_effect = DOWN
    clients.get_realtime_stations.side_effect = ARPA_DOWN
    entry = mondovi_entry()
    entry.add_to_hass(hass)

    result = await start_subentry(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def start_subentry_reconfigure(
    hass: HomeAssistant, entry: MockConfigEntry, subentry_id: str
) -> Any:
    """Start reading a station again, the same way in every version."""
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_STATION),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )


async def test_read_a_station_again(hass: HomeAssistant, clients: Clients) -> None:
    """Test that reconfiguring a station reads it again, keeping its name."""
    del clients
    entry = municipality_entry(
        PRAY_MUNICIPALITY,
        "Pray",
        station_subentry({**PRAY_DATA, CONF_SENSOR_ID: None}, "Sessera"),
    )
    entry.add_to_hass(hass)
    (subentry_id,) = entry.subentries

    result = await start_subentry_reconfigure(hass, entry, subentry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"] == {"station": "Pray Sessera"}
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert dict(entry.subentries[subentry_id].data) == PRAY_DATA


async def test_read_a_station_again_without_answer(
    hass: HomeAssistant, clients: Clients
) -> None:
    """Test the error when a station cannot be read again."""
    clients.get_stations.side_effect = DOWN
    clients.get_realtime_stations.side_effect = ARPA_DOWN
    entry = municipality_entry(
        PRAY_MUNICIPALITY, "Pray", station_subentry(PRAY_DATA, "Sessera")
    )
    entry.add_to_hass(hass)
    (subentry_id,) = entry.subentries

    result = await start_subentry_reconfigure(hass, entry, subentry_id)
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
