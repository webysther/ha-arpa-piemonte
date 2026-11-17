"""ARPA Piemonte: the readings of the stations of Arpa Piemonte.

River levels, rain, temperature, humidity, wind and snow, from the Meteo 3R
app of Arpa Piemonte and, when it fails, from the official sources of Arpa
Piemonte. Not affiliated with Arpa Piemonte.
"""

from __future__ import annotations

from collections.abc import Iterable

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS, SUBENTRY_STATION
from .coordinator import (
    ArpaPiemonteConfigEntry,
    ArpaPiemonteCoordinator,
    ArpaPiemonteData,
)
from .migration import async_migrate_integration
from .models import StationConfig
from .sources import async_get_sources

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Merge the entries of a station of version 1 before they are set up."""
    del config
    await async_migrate_integration(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry
) -> bool:
    """Set up the stations of a municipality.

    Raises ConfigEntryNotReady while no station answers, so that Home Assistant
    tries again soon. A station that does not answer while another does is
    asked again at its next update.
    """
    sources = async_get_sources(hass)
    stations = {
        subentry_id: ArpaPiemonteCoordinator(
            hass, entry, StationConfig.from_data(subentry.data), sources
        )
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_STATION
    }
    await _async_first_refresh(stations.values())
    entry.runtime_data = ArpaPiemonteData(stations)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_first_refresh(
    coordinators: Iterable[ArpaPiemonteCoordinator],
) -> None:
    """Read each station once; raise ConfigEntryNotReady when none answers."""
    not_ready: ConfigEntryNotReady | None = None
    answered = False
    for coordinator in coordinators:
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            not_ready = err
        else:
            answered = True
    if not_ready is not None and not answered:
        raise not_ready


async def _async_reload(hass: HomeAssistant, entry: ArpaPiemonteConfigEntry) -> None:
    """Reload the municipality when a station is added, read again or removed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry
) -> bool:
    """Unload the stations of a municipality."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
