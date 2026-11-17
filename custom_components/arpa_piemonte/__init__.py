"""ARPA Piemonte: the readings of the stations of Arpa Piemonte.

River levels, rain, temperature, humidity, wind and snow, from the Meteo 3R
app of Arpa Piemonte and, when it fails, from the official sources of Arpa
Piemonte. Not affiliated with Arpa Piemonte.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import ArpaPiemonteConfigEntry, ArpaPiemonteCoordinator
from .sources import async_get_sources


async def async_setup_entry(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry
) -> bool:
    """Set up a station.

    Raises ConfigEntryNotReady while no source answers, so that Home Assistant
    tries again soon.
    """
    coordinator = ArpaPiemonteCoordinator(hass, entry, async_get_sources(hass))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ArpaPiemonteConfigEntry
) -> bool:
    """Unload a station."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
