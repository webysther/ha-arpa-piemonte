"""Config flow of ARPA Piemonte: a municipality of Piedmont and its stations.

An entry is a municipality, and each of its stations is a subentry: the
integration page groups the stations by municipality. A station is added by
choosing its municipality, then the station when the municipality has
several, or from the entry of its municipality. The options of the entry
choose those of the risks of the municipality: the warning level, the
position, the radius of the earthquakes and the heat-wave city.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import Any

from aioarpapiemonte import ArpaPiemonteError, Sensor
from aiometeo3r import Meteo3rError

try:  # Home Assistant 2026.9 and newer validate with probatio
    import probatio as vol
except ImportError:  # pragma: no cover - older versions, back to 2025.4
    import voluptuous as vol  # type: ignore[no-redef]
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .catalog import Municipality, StationCatalog, StationChoice
from .const import (
    CONF_HEAT_CITY,
    CONF_MUNICIPALITY,
    CONF_MUNICIPALITY_CODE,
    CONF_POSITION,
    CONF_RADIUS,
    CONF_STATION_CODE,
    CONF_WARNING_LEVEL,
    DOMAIN,
    LOGGER,
    SUBENTRY_STATION,
)
from .models import Position, StationConfig, municipality_unique_id
from .risks import (
    MAX_RADIUS,
    WARNING_LEVELS,
    HeatCityChoice,
    PositionChoice,
    heat_city_choice,
    position_choice,
    radius_km,
    warning_level,
)
from .sources import ArpaSources, async_get_sources


class CannotConnect(Exception):
    """No source of the list of the stations answered."""


async def async_station_catalog(sources: ArpaSources) -> StationCatalog:
    """Return the stations, from Meteo 3R or else from the api_realtime.

    Raises CannotConnect when neither answers.
    """
    try:
        stations = await sources.meteo3r.get_stations()
    except Meteo3rError as err:
        LOGGER.debug("The stations of Meteo 3R are not available: %s", err)
    else:
        return StationCatalog(StationChoice.of_meteo3r(station) for station in stations)
    try:
        realtime = await sources.arpa.get_realtime_stations()
    except ArpaPiemonteError as err:
        LOGGER.debug("The stations of the api_realtime are not available: %s", err)
        raise CannotConnect from err
    return StationCatalog(StationChoice.of_realtime(station) for station in realtime)


async def async_website_station(
    sources: ArpaSources, choice: StationChoice
) -> tuple[str | None, tuple[str, ...] | None]:
    """Return the identifier of the station on the Arpa website, and its files.

    The api_realtime gives the identifier. Without it, the coordinates of
    Meteo 3R equal those of the website exactly (373 of 373 stations, measured
    on 2026-11-17). The list of stations of the website names the files of the
    station ("baro", "radd"...); an identifier it does not list is dropped:
    one station has none. Without the list, the files are unknown (None).
    """
    candidate = choice.sensor_id
    if candidate is None:
        try:
            realtime = await sources.arpa.get_realtime_stations()
        except ArpaPiemonteError as err:
            LOGGER.debug("The api_realtime is not available: %s", err)
        else:
            candidate = next(
                (
                    station.sensor_id
                    for station in realtime
                    if station.station_code == choice.code
                ),
                None,
            )
    try:
        sensors = await sources.arpa.get_sensors()
    except ArpaPiemonteError as err:
        LOGGER.debug("The stations of the Arpa website are not available: %s", err)
        return candidate, None
    sensor = next(
        (
            sensor
            for sensor in sensors
            if sensor.id == candidate
            or (
                candidate is None
                and (sensor.latitude, sensor.longitude)
                == (choice.latitude, choice.longitude)
            )
        ),
        None,
    )
    if sensor is None:
        return None, ()
    return sensor.id, _files_of(sensor)


def _files_of(sensor: Sensor) -> tuple[str, ...]:
    """Return the files of a station of the website, by name, sorted."""
    return tuple(sorted(param.value for param in sensor.params))


async def async_station_answers(sources: ArpaSources, code: str) -> bool:
    """Return whether Meteo 3R or the api_realtime answer for the station."""
    try:
        await sources.meteo3r.get_station_data(code)
    except Meteo3rError as err:
        LOGGER.debug("Meteo 3R does not answer for %s: %s", code, err)
    else:
        return True
    try:
        await sources.arpa.get_realtime_data(code)
    except ArpaPiemonteError as err:
        LOGGER.debug("The api_realtime does not answer for %s: %s", code, err)
        return False
    return True


async def async_station_config(
    sources: ArpaSources, choice: StationChoice
) -> StationConfig | None:
    """Return a station to store, read from Arpa; None when it does not answer."""
    if not await async_station_answers(sources, choice.code):
        return None
    sensor_id, website_params = await async_website_station(sources, choice)
    return StationConfig(
        station_code=choice.code,
        name=choice.name,
        sensor_id=sensor_id,
        sensor_letters=choice.sensor_letters,
        thresholds=choice.thresholds,
        website_params=website_params,
        position=Position(choice.latitude, choice.longitude),
    )


async def async_read_again(
    sources: ArpaSources, stations: Sequence[StationConfig]
) -> list[StationConfig] | None:
    """Return stations read again from Arpa; None when one does not answer.

    Each keeps its name: it names the device and entity IDs the user knows.
    """
    try:
        catalog = await async_station_catalog(sources)
    except CannotConnect:
        return None
    read: list[StationConfig] = []
    for station in stations:
        choice = catalog.stations.get(station.station_code)
        again = None if choice is None else await async_station_config(sources, choice)
        if again is None:
            return None
        read.append(replace(again, name=station.name))
    return read


@callback
def added_station_codes(hass: HomeAssistant) -> set[str]:
    """Return the codes of the stations already added, in any municipality."""
    return {
        subentry.data[CONF_STATION_CODE]
        for entry in hass.config_entries.async_entries(DOMAIN)
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_STATION
    }


def station_subentries(entry: ConfigEntry) -> list[ConfigSubentry]:
    """Return the subentries of the stations of an entry."""
    return [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_STATION
    ]


def municipality_selector(municipalities: Iterable[Municipality]) -> SelectSelector:
    """Return a picker of the municipalities, with a search.

    It accepts typed text too, which the flow looks up in the list: the
    search needs it ("mondovì" finds "Mondovi'").
    """
    return SelectSelector(
        SelectSelectorConfig(
            options=[municipality.name for municipality in municipalities],
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
            sort=False,
        )
    )


def station_schema(stations: Iterable[StationChoice]) -> vol.Schema:
    """Return the form of a station among those of a municipality."""
    return vol.Schema(
        {
            vol.Required(CONF_STATION_CODE): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=station.code, label=station.label)
                        for station in stations
                    ],
                    mode=SelectSelectorMode.LIST,
                )
            )
        }
    )


def options_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return the form of the options of a municipality: those of its risks.

    The warning level of the alerts; where the earthquakes, the avalanches
    and the nearest heat-wave city are taken from; the radius of the
    earthquakes; and which capital gives the heat waves.
    """
    return vol.Schema(
        {
            vol.Required(
                CONF_WARNING_LEVEL, default=str(warning_level(options))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=WARNING_LEVELS,
                    translation_key=CONF_WARNING_LEVEL,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_POSITION, default=str(position_choice(options))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[str(choice) for choice in PositionChoice],
                    translation_key=CONF_POSITION,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Required(CONF_RADIUS, default=radius_km(options)): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=MAX_RADIUS,
                    step=1,
                    unit_of_measurement=UnitOfLength.KILOMETERS,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_HEAT_CITY, default=str(heat_city_choice(options))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[str(choice) for choice in HeatCityChoice],
                    translation_key=CONF_HEAT_CITY,
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }
    )


def station_subentry_data(
    choice: StationChoice, station: StationConfig
) -> ConfigSubentryData:
    """Return the subentry of a station: its river (or name) as title."""
    return ConfigSubentryData(
        data=station.as_data(),
        subentry_type=SUBENTRY_STATION,
        title=choice.title,
        unique_id=station.unique_id,
    )


class ArpaPiemonteFlowHandler(ConfigFlow, domain=DOMAIN):
    """Add a station: one entry per municipality, one subentry per station."""

    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._catalog: StationCatalog | None = None
        self._municipality: Municipality | None = None

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentries of a municipality: its stations."""
        del config_entry
        return {SUBENTRY_STATION: StationFlowHandler}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ArpaPiemonteOptionsFlow:
        """Return the options of a municipality: those of its risks."""
        del config_entry
        return ArpaPiemonteOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a municipality of Piedmont, with a search."""
        if self._catalog is None:
            try:
                self._catalog = await async_station_catalog(
                    async_get_sources(self.hass)
                )
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")

        errors: dict[str, str] = {}
        if user_input is not None:
            municipality = self._catalog.municipality(user_input[CONF_MUNICIPALITY])
            if municipality is None:
                errors[CONF_MUNICIPALITY] = "municipality_not_listed"
            else:
                self._municipality = municipality
                stations = self._stations_to_add()
                if not stations:
                    return self.async_abort(reason="already_configured")
                if len(stations) > 1:
                    return await self.async_step_station()
                # A municipality with one station needs no second step
                if (result := await self._async_add(stations[0])) is not None:
                    return result
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_MUNICIPALITY): municipality_selector(
                    self._catalog.municipalities
                )
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a station of the municipality: the rivers first."""
        assert self._catalog is not None
        assert self._municipality is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            choice = self._catalog.stations[user_input[CONF_STATION_CODE]]
            if (result := await self._async_add(choice)) is not None:
                return result
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="station",
            data_schema=self.add_suggested_values_to_schema(
                station_schema(self._stations_to_add()), user_input
            ),
            errors=errors,
            description_placeholders={"municipality": self._municipality.name},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Read every station of the municipality again from Arpa."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            subentries = station_subentries(entry)
            read = await async_read_again(
                async_get_sources(self.hass),
                [StationConfig.from_data(subentry.data) for subentry in subentries],
            )
            if read is None:
                errors["base"] = "cannot_connect"
            else:
                for subentry, station in zip(subentries, read, strict=True):
                    self.hass.config_entries.async_update_subentry(
                        entry, subentry, data=station.as_data()
                    )
                return self.async_abort(reason="reconfigure_successful")
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"municipality": entry.title},
        )

    def _stations_to_add(self) -> list[StationChoice]:
        """Return the stations of the municipality not added yet."""
        assert self._catalog is not None
        assert self._municipality is not None
        return self._catalog.stations_of(
            self._municipality.code, added=added_station_codes(self.hass)
        )

    async def _async_add(self, choice: StationChoice) -> ConfigFlowResult | None:
        """Add a station to its municipality; None when it does not answer.

        A municipality already added gets the station as a subentry, and the
        flow ends there; otherwise its entry is created with the station.
        """
        assert self._municipality is not None
        station = await async_station_config(async_get_sources(self.hass), choice)
        if station is None:
            return None
        unique_id = municipality_unique_id(self._municipality.code)
        subentry = station_subentry_data(choice, station)
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, unique_id
        )
        if entry is not None:
            self.hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(subentry["data"]),
                    subentry_type=subentry["subentry_type"],
                    title=subentry["title"],
                    unique_id=subentry["unique_id"],
                ),
            )
            return self.async_abort(
                reason="station_added",
                description_placeholders={
                    "station": station.name,
                    "municipality": entry.title,
                },
            )
        await self.async_set_unique_id(unique_id)
        return self.async_create_entry(
            title=self._municipality.name,
            data={CONF_MUNICIPALITY_CODE: self._municipality.code},
            subentries=[subentry],
        )


class ArpaPiemonteOptionsFlow(OptionsFlow):
    """Choose the options of the risks of a municipality.

    The entry reloads with the new options, as when a station changes.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the warning level, the position, the radius and the heat city."""
        if user_input is not None:
            return self.async_create_entry(
                data={**self.config_entry.options, **user_input}
            )
        return self.async_show_form(
            step_id="init",
            data_schema=options_schema(self.config_entry.options),
            description_placeholders={"municipality": self.config_entry.title},
        )


class StationFlowHandler(ConfigSubentryFlow):
    """Add another station of a municipality, or read a station again."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._catalog: StationCatalog | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose another station of the municipality."""
        entry = self._get_entry()
        sources = async_get_sources(self.hass)
        if self._catalog is None:
            try:
                self._catalog = await async_station_catalog(sources)
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")
        placeholders = {"municipality": entry.title}
        stations = self._catalog.stations_of(
            entry.data[CONF_MUNICIPALITY_CODE], added=added_station_codes(self.hass)
        )
        if not stations:
            return self.async_abort(
                reason="no_other_station", description_placeholders=placeholders
            )

        errors: dict[str, str] = {}
        if user_input is not None:
            choice = self._catalog.stations[user_input[CONF_STATION_CODE]]
            station = await async_station_config(sources, choice)
            if station is None:
                errors["base"] = "cannot_connect"
            else:
                subentry = station_subentry_data(choice, station)
                return self.async_create_entry(
                    title=subentry["title"],
                    data=subentry["data"],
                    unique_id=subentry["unique_id"],
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                station_schema(stations), user_input
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Read the station again from Arpa: its sensors, thresholds, identifiers."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            read = await async_read_again(
                async_get_sources(self.hass), [StationConfig.from_data(subentry.data)]
            )
            if read is None:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_and_abort(
                    self._get_entry(), subentry, data=read[0].as_data()
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "station": StationConfig.from_data(subentry.data).name
            },
        )
