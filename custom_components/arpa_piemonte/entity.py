"""The base entity of a station."""

from __future__ import annotations

from typing import Final

from aioarpapiemonte import Param, station_page_url
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, VERSION
from .coordinator import ArpaPiemonteCoordinator

PAGE_PARAMS: Final = (
    ("I", Param.LEVEL),
    ("T", Param.TEMPERATURE),
    ("P", Param.RAIN_10_MIN),
    ("H", Param.HUMIDITY),
    ("N", Param.SNOW_DEPTH),
    ("V", Param.WIND_SPEED),
)
"""The quantity the page of a station opens on, by its first sensor in this order."""


class ArpaPiemonteEntity(CoordinatorEntity[ArpaPiemonteCoordinator]):
    """An entity of a station, named after the station and its translation key."""

    # The credit the CC BY 4.0 license of the data requires
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: ArpaPiemonteCoordinator, key: str) -> None:
        """Initialize an entity of the station, with its key."""
        super().__init__(coordinator)
        station = coordinator.station
        self._attr_unique_id = f"{station.unique_id}-{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, station.unique_id)},
            name=station.name,
            manufacturer=MANUFACTURER,
            model=station.sensor_letters or None,
            model_id=station.station_code,
            entry_type=DeviceEntryType.SERVICE,
            sw_version=VERSION,
            configuration_url=_page_url(station.sensor_id, station.sensor_letters),
        )
        # English IDs whatever the language: sensor.arpa_piemonte_pray_sessera_level
        self.entity_id = f"sensor.{DOMAIN}_{slugify(station.name)}_{key}"


def _page_url(sensor_id: str | None, letters: str) -> str | None:
    """Return the page of the station on the Arpa website: the source to credit."""
    if sensor_id is None:
        return None
    param = next(
        (param for letter, param in PAGE_PARAMS if letter in letters.upper()),
        Param.LEVEL,
    )
    return station_page_url(sensor_id, param)
