"""ARPA Piemonte: the readings of the stations of Arpa Piemonte, and the risks.

River levels, rain, temperature, humidity, wind and snow, from the Meteo 3R
app of Arpa Piemonte and, when it fails, from the official sources of Arpa
Piemonte; the natural risks of each municipality, from its widget on the Arpa
website. Not affiliated with Arpa Piemonte.
"""

from __future__ import annotations

from collections.abc import Iterable

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, PLATFORMS, SUBENTRY_STATION
from .coordinator import (
    ArpaPiemonteConfigEntry,
    ArpaPiemonteCoordinator,
    ArpaPiemonteData,
    MunicipalityRisks,
    async_risk_place,
    municipality_risks,
)
from .dashboard import async_offer_the_frontend
from .migration import async_migrate_integration
from .models import StationConfig
from .sources import async_get_sources

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Prepare the integration before its entries are set up.

    Merge the entries of a station of version 1, and offer the dashboard and
    the card to the frontend.
    """
    del config
    await async_migrate_integration(hass)
    await async_offer_the_frontend(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry
) -> bool:
    """Set up the stations of a municipality, and its natural risks.

    Raises ConfigEntryNotReady while no station answers, so that Home Assistant
    tries again soon. A station that does not answer while another does is
    asked again at its next update, as are the risks.
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
    place = await async_risk_place(
        hass,
        entry,
        sources,
        (coordinator.station for coordinator in stations.values()),
    )
    risks = municipality_risks(hass, entry, sources, place)
    await _async_first_refresh_of_the_risks(risks)
    entry.runtime_data = ArpaPiemonteData(stations, risks)
    for coordinator in risks.daily:
        coordinator.async_follow_the_days()
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


async def _async_first_refresh_of_the_risks(risks: MunicipalityRisks) -> None:
    """Read each risk of the municipality once; the stations do not wait for them.

    Without an answer, the entities of a risk are unavailable until its next
    update.
    """
    for coordinator in risks.coordinators:
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            # The failed update, whose message names the municipality and the error
            LOGGER.warning("%s", err.__cause__ or err)


async def _async_reload(hass: HomeAssistant, entry: ArpaPiemonteConfigEntry) -> None:
    """Reload the municipality when a station or an option changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry
) -> bool:
    """Unload the stations of a municipality."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
