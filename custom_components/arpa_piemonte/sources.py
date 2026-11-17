"""The clients of the sources, shared by every station."""

from __future__ import annotations

from dataclasses import dataclass

from aioarpapiemonte import ArpaPiemonteClient
from aiometeo3r import Meteo3rClient
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, VERSION


@dataclass(frozen=True, slots=True)
class ArpaSources:
    """The clients of Meteo 3R and of the official sources of Arpa Piemonte.

    They are shared, so that a host of Meteo 3R that failed for one station is
    asked last for all of them.
    """

    meteo3r: Meteo3rClient
    arpa: ArpaPiemonteClient


DATA_SOURCES: HassKey[ArpaSources] = HassKey(f"{DOMAIN}_sources")


@callback
def async_get_sources(hass: HomeAssistant) -> ArpaSources:
    """Return the clients of the sources, created on first use.

    They use the session of Home Assistant, and name the integration in their
    requests, as the terms of use of open data ask.
    """
    if (sources := hass.data.get(DATA_SOURCES)) is None:
        session = async_get_clientsession(hass)
        user_agent = f"{SERVER_SOFTWARE} {DOMAIN}/{VERSION}"
        sources = hass.data[DATA_SOURCES] = ArpaSources(
            meteo3r=Meteo3rClient(session, user_agent=user_agent),
            arpa=ArpaPiemonteClient(session, user_agent=user_agent),
        )
    return sources
