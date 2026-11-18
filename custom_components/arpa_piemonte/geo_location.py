"""The earthquakes near a municipality, as geolocation entities.

Each earthquake of the last 30 days within the radius of the position of the
municipality is an entity of the source ``arpa_piemonte``, so the map card
shows them with ``geo_location_sources: [arpa_piemonte]``, and a geolocation
trigger fires when one appears in a zone. The entities come and go with the
list of Arpa: an earthquake older than 30 days leaves it.
"""

from __future__ import annotations

from typing import Final

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import Platform, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ArpaPiemonteConfigEntry, EarthquakesCoordinator
from .entity import MunicipalityRisksEntity, risk_unique_id
from .risks import NearbyEarthquake

# The coordinator updates the entities
PARALLEL_UPDATES = 0

EARTHQUAKE: Final = "earthquake"
"""The translation key of the entities of the earthquakes, and the start of
their keys: earthquake_261117064149."""


def earthquake_key(nearby: NearbyEarthquake) -> str:
    """Return the key of the entity of an earthquake, by its ID at Arpa."""
    return f"{EARTHQUAKE}_{nearby.earthquake.id}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArpaPiemonteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the earthquakes near the municipality, when it has a position."""
    coordinator = entry.runtime_data.risks.earthquakes
    if coordinator is None:
        return
    added: set[str] = set()

    @callback
    def show_the_earthquakes_nearby() -> None:
        """Add the new earthquakes within the radius, and remove those gone.

        The entity registry, not only the entities of this run, tells which are
        gone: the earthquakes of a previous run stay registered until the next.
        """
        nearby = {
            risk_unique_id(coordinator.municipality_code, earthquake_key(item)): item
            for item in coordinator.data or ()
        }
        registry = er.async_get(hass)
        for registry_entry in er.async_entries_for_config_entry(
            registry, entry.entry_id
        ):
            if (
                registry_entry.domain == Platform.GEO_LOCATION
                and registry_entry.unique_id not in nearby
            ):
                # Removing it from the registry removes the entity too
                registry.async_remove(registry_entry.entity_id)
                added.discard(registry_entry.unique_id)
        new = sorted(nearby.keys() - added)
        added.update(new)
        async_add_entities(
            EarthquakeEvent(coordinator, nearby[unique_id]) for unique_id in new
        )

    show_the_earthquakes_nearby()
    entry.async_on_unload(coordinator.async_add_listener(show_the_earthquakes_nearby))


class EarthquakeEvent(
    MunicipalityRisksEntity[EarthquakesCoordinator], GeolocationEvent
):
    """An earthquake within the radius: where its epicentre is, and how far.

    Named after its magnitude; its time, depth and seismic district are
    attributes. It follows the list of Arpa, which may review its magnitude.
    """

    _attr_source = DOMAIN
    # The radius of the options is in km
    _attr_unit_of_measurement = UnitOfLength.KILOMETERS

    def __init__(
        self, coordinator: EarthquakesCoordinator, nearby: NearbyEarthquake
    ) -> None:
        """Initialize the entity of an earthquake near the municipality."""
        self._key = earthquake_key(nearby)
        super().__init__(coordinator, Platform.GEO_LOCATION, self._key, EARTHQUAKE)
        self._nearby: NearbyEarthquake | None = None
        self._show(nearby)

    @property
    def available(self) -> bool:
        """Return whether the list still has the earthquake within the radius."""
        return super().available and self._nearby is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Follow the earthquake in the latest list."""
        self._show(
            next(
                (
                    item
                    for item in self.coordinator.data or ()
                    if earthquake_key(item) == self._key
                ),
                None,
            )
        )
        super()._handle_coordinator_update()

    def _show(self, nearby: NearbyEarthquake | None) -> None:
        """Show where the earthquake is; None while it is being removed."""
        self._nearby = nearby
        if nearby is None:
            return
        earthquake = nearby.earthquake
        self._attr_translation_placeholders = {
            "magnitude": f"{earthquake.magnitude:.1f}"
        }
        self._attr_distance = nearby.distance_km
        self._attr_latitude = earthquake.latitude
        self._attr_longitude = earthquake.longitude
        self._attr_extra_state_attributes = {
            "magnitude": earthquake.magnitude,
            "magnitude_type": earthquake.magnitude_type,
            "time": earthquake.time.isoformat(),
            "depth": earthquake.depth,
            "district": earthquake.district,
            "reviewed": earthquake.reviewed,
        }
