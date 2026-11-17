"""Config flow of ARPA Piemonte: a station of the Piedmont network."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aioarpapiemonte import ArpaPiemonteError, RealtimeStation
from aiometeo3r import Meteo3rError, Station

try:  # Home Assistant 2026.9 and newer validate with probatio
    import probatio as vol
except ImportError:  # pragma: no cover - older versions, back to 2025.4
    import voluptuous as vol  # type: ignore[no-redef]
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_SENSOR_ID,
    CONF_SENSOR_LETTERS,
    CONF_STATION_CODE,
    CONF_THRESHOLDS,
    DOMAIN,
    LOGGER,
)
from .models import Thresholds
from .sources import ArpaSources, async_get_sources


@dataclass(frozen=True, slots=True)
class StationChoice:
    """A station the user can add, from the list of Meteo 3R or of the api_realtime."""

    code: str
    name: str
    river: str | None
    municipality: str
    latitude: float
    longitude: float
    sensor_letters: str
    thresholds: Thresholds
    sensor_id: str | None = None
    """Identifier on the Arpa website, when the list gives it (the api_realtime)."""

    @classmethod
    def of_meteo3r(cls, station: Station) -> StationChoice:
        """Return a station of the list of Meteo 3R."""
        thresholds = station.thresholds
        return cls(
            code=station.code,
            name=station.name,
            river=station.river,
            municipality=station.municipality,
            latitude=station.latitude,
            longitude=station.longitude,
            sensor_letters=station.sensor_letters,
            thresholds=Thresholds(
                thresholds.pre_alarm, thresholds.guard, thresholds.danger
            ),
        )

    @classmethod
    def of_realtime(cls, station: RealtimeStation) -> StationChoice:
        """Return a station of the list of the api_realtime, named in capitals."""
        thresholds = station.thresholds
        return cls(
            code=station.station_code,
            name=station.name.title(),
            river=station.river,
            municipality=station.municipality,
            latitude=station.latitude,
            longitude=station.longitude,
            sensor_letters=station.station_type,
            thresholds=Thresholds(
                thresholds.pre_alarm, thresholds.guard, thresholds.danger
            ),
            sensor_id=station.sensor_id,
        )

    @property
    def label(self) -> str:
        """Return how the station is listed: name, river and municipality."""
        place = self.municipality.title()
        if self.river:
            return f"{self.name} — {self.river.title()} ({place})"
        return f"{self.name} ({place})"


class CannotConnect(Exception):
    """No source of the list of the stations answered."""


async def async_station_choices(sources: ArpaSources) -> dict[str, StationChoice]:
    """Return the stations, from Meteo 3R or else from the api_realtime.

    Raises CannotConnect when neither answers.
    """
    try:
        stations = await sources.meteo3r.get_stations()
    except Meteo3rError as err:
        LOGGER.debug("The stations of Meteo 3R are not available: %s", err)
    else:
        return {station.code: StationChoice.of_meteo3r(station) for station in stations}
    try:
        realtime = await sources.arpa.get_realtime_stations()
    except ArpaPiemonteError as err:
        LOGGER.debug("The stations of the api_realtime are not available: %s", err)
        raise CannotConnect from err
    return {
        station.station_code: StationChoice.of_realtime(station) for station in realtime
    }


async def async_sensor_id(sources: ArpaSources, choice: StationChoice) -> str | None:
    """Return the identifier of the station on the Arpa website; None without one.

    The api_realtime gives it. Without it, the coordinates of Meteo 3R equal
    those of the website exactly (373 of 373 stations, measured on
    2026-11-17). An identifier the website does not list is dropped: one
    station has none.
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
        return candidate
    if candidate is not None:
        return candidate if any(sensor.id == candidate for sensor in sensors) else None
    return next(
        (
            sensor.id
            for sensor in sensors
            if (sensor.latitude, sensor.longitude)
            == (choice.latitude, choice.longitude)
        ),
        None,
    )


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


class ArpaPiemonteFlowHandler(ConfigFlow, domain=DOMAIN):
    """Add a station: one config entry per station."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._choices: dict[str, StationChoice] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a station among those of Piedmont."""
        sources = async_get_sources(self.hass)
        if not self._choices:
            try:
                self._choices = await async_station_choices(sources)
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")

        errors: dict[str, str] = {}
        if user_input is not None:
            choice = self._choices[user_input[CONF_STATION_CODE]]
            await self.async_set_unique_id(f"PIE_{choice.code}")
            self._abort_if_unique_id_configured()
            data = await self._async_entry_data(sources, choice)
            if data is None:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=choice.name, data=data)

        options = [
            SelectOptionDict(value=choice.code, label=choice.label)
            for choice in sorted(self._choices.values(), key=lambda item: item.label)
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_CODE): SelectSelector(
                    SelectSelectorConfig(
                        options=options, mode=SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Read the station again from Arpa: its sensors, thresholds, identifiers."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            sources = async_get_sources(self.hass)
            try:
                choices = await async_station_choices(sources)
            except CannotConnect:
                choices = {}
            choice = choices.get(entry.data[CONF_STATION_CODE])
            data = (
                None
                if choice is None
                else await self._async_entry_data(sources, choice)
            )
            if data is None:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"station": entry.title},
        )

    async def _async_entry_data(
        self, sources: ArpaSources, choice: StationChoice
    ) -> dict[str, Any] | None:
        """Return the data of the entry of a station; None when it does not answer."""
        if not await async_station_answers(sources, choice.code):
            return None
        return {
            CONF_STATION_CODE: choice.code,
            CONF_SENSOR_ID: await async_sensor_id(sources, choice),
            CONF_SENSOR_LETTERS: choice.sensor_letters,
            CONF_THRESHOLDS: choice.thresholds.as_dict(),
        }
