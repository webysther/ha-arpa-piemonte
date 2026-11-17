"""From one entry per station (version 1) to one entry per municipality.

The integration is set up before its entries, so the entries of version 1
are merged there: each station becomes a subentry of the entry of its
municipality, with its device, entities, entity IDs and history. It needs no
source: the municipality of each station is in ``STATION_PLACES``.
"""

from __future__ import annotations

import inspect
from types import MappingProxyType
from typing import Final

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import (
    CONF_MUNICIPALITY_CODE,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    DOMAIN,
    LOGGER,
    SUBENTRY_STATION,
)
from .models import StationConfig, municipality_unique_id
from .station_places import STATION_PLACES

MOVES_A_DEVICE_AT_ONCE: Final = (
    "new_config_entry_id"
    in inspect.signature(dr.DeviceRegistry.async_update_device).parameters
)
"""Whether a device belongs to one entry, moved to another in one call.

Home Assistant 2026.8 and newer. Before, a device can belong to several
entries: it is added to the new entry, then removed from the old one.
"""


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Merge the entries of version 1 into one entry per municipality.

    The first entry of a municipality, an enabled one when there is, becomes
    the entry of the municipality; the others are removed once their station
    moved to it. A station missing from ``STATION_PLACES`` keeps its entry of
    version 1, which Home Assistant cannot load: it was added after the list
    was made, and only adding it again helps.
    """
    entries = sorted(
        hass.config_entries.async_entries(DOMAIN),
        key=lambda entry: entry.disabled_by is not None,
    )
    if not any(entry.version == 1 for entry in entries):
        return
    municipalities = {
        entry.unique_id: entry
        for entry in entries
        if entry.version > 1 and entry.unique_id is not None
    }
    for entry in entries:
        if entry.version != 1:
            continue
        place = STATION_PLACES.get(entry.data[CONF_STATION_CODE])
        if place is None:
            LOGGER.error(
                "The station %s is not among those of 2026-11-17 and cannot be "
                "moved to its municipality: remove it and add it again",
                entry.title,
            )
            continue
        unique_id = municipality_unique_id(place.municipality_code)
        municipality = municipalities.setdefault(unique_id, entry)
        station = StationConfig.from_data(
            {**entry.data, CONF_STATION_NAME: entry.title}
        )
        subentry = ConfigSubentry(
            data=MappingProxyType(station.as_data()),
            subentry_type=SUBENTRY_STATION,
            title=place.river or entry.title,
            unique_id=station.unique_id,
        )
        hass.config_entries.async_add_subentry(municipality, subentry)
        _move_station(hass, entry, municipality, subentry)
        if municipality is entry:
            hass.config_entries.async_update_entry(
                entry,
                title=place.municipality,
                unique_id=unique_id,
                data={CONF_MUNICIPALITY_CODE: place.municipality_code},
                version=2,
                minor_version=1,
            )
        else:
            await hass.config_entries.async_remove(entry.entry_id)


def _move_station(
    hass: HomeAssistant,
    entry: ConfigEntry,
    municipality: ConfigEntry,
    subentry: ConfigSubentry,
) -> None:
    """Move the device and entities of the entry of a station to its subentry.

    A station the user disabled with its entry stays disabled in an enabled
    municipality: the registries would enable what the entry disabled.
    """
    keep_disabled = entry.disabled_by is not None and municipality.disabled_by is None
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    # The device of the station, looked up the same way in every version
    device = next(
        (
            device
            for device in dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            )
            if (DOMAIN, subentry.unique_id) in device.identifiers
        ),
        None,
    )
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        entity_disabled_by = entity.disabled_by
        if (
            keep_disabled
            and entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
        ):
            entity_disabled_by = (
                er.RegistryEntryDisabler.DEVICE
                if device is not None
                else er.RegistryEntryDisabler.USER
            )
        entity_registry.async_update_entity(
            entity.entity_id,
            config_entry_id=municipality.entry_id,
            config_subentry_id=subentry.subentry_id,
            disabled_by=entity_disabled_by,
        )
    if device is None:
        return
    device_disabled_by: dr.DeviceEntryDisabler | UndefinedType = UNDEFINED
    if keep_disabled and device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY:
        device_disabled_by = dr.DeviceEntryDisabler.USER
    if MOVES_A_DEVICE_AT_ONCE:
        device_registry.async_update_device(
            device.id,
            disabled_by=device_disabled_by,
            new_config_entry_id=municipality.entry_id,
            new_config_subentry_id=subentry.subentry_id,
        )
    else:  # pragma: no cover - before 2026.8, tested on Home Assistant 2025.4
        _move_device_to_another_entry(
            device_registry, device.id, entry, municipality, subentry
        )
        if device_disabled_by is not UNDEFINED:
            device_registry.async_update_device(
                device.id, disabled_by=device_disabled_by
            )


def _move_device_to_another_entry(  # pragma: no cover - before 2026.8
    device_registry: dr.DeviceRegistry,
    device_id: str,
    entry: ConfigEntry,
    municipality: ConfigEntry,
    subentry: ConfigSubentry,
) -> None:
    """Move a device that can belong to several entries, before 2026.8.

    Two calls: in one, the removal starts from the entries the device had,
    and loses the one just added, or removes the device (2025.4 to 2026.7).
    Adding an enabled entry enables a device its entry disabled.
    """
    device_registry.async_update_device(
        device_id,
        add_config_entry_id=municipality.entry_id,
        add_config_subentry_id=subentry.subentry_id,
    )
    device_registry.async_update_device(
        device_id,
        remove_config_entry_id=entry.entry_id,
        remove_config_subentry_id=None,
    )
