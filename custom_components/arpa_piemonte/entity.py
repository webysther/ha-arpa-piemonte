"""The base entities of a station, and of the natural risks of a municipality."""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from aioarpapiemonte import Param, station_page_url
from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, VERSION
from .coordinator import ArpaPiemonteCoordinator, RisksCoordinator
from .models import municipality_unique_id
from .risks import has_alerts, italian_date, widget_page_url

RISKS_DEVICE: Final = "risks"
"""The translation key of the device of the natural risks of a municipality."""

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

    def __init__(
        self, coordinator: ArpaPiemonteCoordinator, platform: Platform, key: str
    ) -> None:
        """Initialize an entity of the station, of a platform, with its key."""
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
        self.entity_id = f"{platform}.{DOMAIN}_{slugify(station.name)}_{key}"


def _page_url(sensor_id: str | None, letters: str) -> str | None:
    """Return the page of the station on the Arpa website: the source to credit."""
    if sensor_id is None:
        return None
    param = next(
        (param for letter, param in PAGE_PARAMS if letter in letters.upper()),
        Param.LEVEL,
    )
    return station_page_url(sensor_id, param)


def risk_unique_id(municipality_code: str, key: str) -> str:
    """Return the unique ID of an entity of the risks of a municipality.

    The ID of the entry of the municipality and the key of the entity:
    ``ISTAT_096050-highest_alert``.
    """
    return f"{municipality_unique_id(municipality_code)}-{key}"


class MunicipalityRisksEntity[CoordinatorT: RisksCoordinator[Any]](
    CoordinatorEntity[CoordinatorT]
):
    """An entity of the natural risks of a municipality, on their own device.

    The device is that of the entry of the municipality, beside its stations,
    named after it ("Pray · Natural risks"), and links to the page of its
    widget on the Arpa website, the source to credit, when Arpa has one.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CoordinatorT,
        platform: Platform,
        key: str,
        translation_key: str | None = None,
    ) -> None:
        """Initialize an entity of the risks, of a platform, with its key.

        The translation key is the key, unless given: the entities of the
        earthquakes share theirs.
        """
        super().__init__(coordinator)
        municipality = coordinator.config_entry.title
        code = coordinator.municipality_code
        unique_id = municipality_unique_id(code)
        # The credit the license of the data requires: Arpa, or AINEVA
        self._attr_attribution = coordinator.attribution
        self._attr_unique_id = risk_unique_id(code, key)
        self._attr_translation_key = translation_key or key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            translation_key=RISKS_DEVICE,
            translation_placeholders={"municipality": municipality},
            manufacturer=MANUFACTURER,
            model_id=code,
            entry_type=DeviceEntryType.SERVICE,
            sw_version=VERSION,
            configuration_url=widget_page_url(code) if has_alerts(code) else None,
        )
        # English IDs whatever the language: sensor.arpa_piemonte_pray_highest_alert
        self.entity_id = f"{platform}.{DOMAIN}_{slugify(municipality)}_{key}"

    @property
    def available(self) -> bool:
        """Return whether the source of the risk has answered."""
        return super().available and self.coordinator.data is not None

    @property
    def today(self) -> date:
        """Return the date of today in Italy, the first day the entities show."""
        return italian_date(dt_util.utcnow())
