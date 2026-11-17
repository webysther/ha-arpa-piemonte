"""Constants of the ARPA Piemonte integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

from .version import __version__

VERSION: Final = __version__
"""Version of the integration: the release tag, written by the release workflow."""

DOMAIN: Final = "arpa_piemonte"
LOGGER = logging.getLogger(__package__)
PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.SENSOR]

ATTRIBUTION: Final = "Fonte: Arpa Piemonte - www.arpa.piemonte.it"
"""Credit the data needs (CC BY 4.0, https://www.arpa.piemonte.it/note-legali)."""

MANUFACTURER: Final = "Arpa Piemonte"
"""The body that runs the stations: the data is theirs, the integration is not."""

ISSUE_URL: Final = "https://github.com/webysther/ha-arpa-piemonte/issues"

# Config entry data: a municipality
CONF_MUNICIPALITY_CODE: Final = "municipality_code"
"""ISTAT code of the municipality of the entry ("096050"), the current one, as
Meteo 3R and the api_realtime give it: the widget of the municipality on the
Arpa website uses the same code."""
CONF_MUNICIPALITY: Final = "municipality"
"""The field of the config flow where the municipality is chosen or typed."""

# Config subentry data: a station of the municipality
SUBENTRY_STATION: Final = "station"
"""The type of the subentry of a station."""
CONF_STATION_CODE: Final = "station_code"
"""Code of the station in the network ("188"), as Meteo 3R and the api_realtime."""
CONF_SENSOR_ID: Final = "sensor_id"
"""Identifier of the station on the Arpa website ("002105900"); None without one."""
CONF_SENSOR_LETTERS: Final = "sensor_letters"
"""The letters of the sensors of the station ("IPT"): they give its entities."""
CONF_THRESHOLDS: Final = "thresholds"
"""Thresholds of the level when the station was added: used when no source
answered with them."""
CONF_STATION_NAME: Final = "name"
"""Name of the station ("Pray Sessera"): the name of its device, and of its
entity IDs."""

MUNICIPALITY_ID_PREFIX: Final = "ISTAT_"
"""Unique ID of the entry of a municipality: this prefix and its ISTAT code."""
STATION_ID_PREFIX: Final = "PIE_"
"""Unique ID of a station: the network of Piedmont and its code, as Meteo 3R
names it ("PIE_188"). Its device and entities keep it."""

UPDATE_INTERVAL: Final = timedelta(minutes=10)
"""How often Meteo 3R is asked for the station.

Meteo 3R writes the files every 30 minutes, 30 to 45 minutes after the
measurement (measured on 2026-11-17): asking every 10 minutes shows a new
reading at most 10 minutes late, and the answers in between are a
``304 Not Modified``.
"""

PRIMARY_STALE_AFTER: Final = timedelta(hours=2)
"""Age after which a reading of Meteo 3R is too old, and the official sources
are asked for a newer one.

A reading of Meteo 3R is normally at most 75 minutes old: 45 minutes late,
then 30 minutes until the next one. Two hours mean two readings are missing.
"""

WEBSITE_LAG: Final = timedelta(minutes=30)
"""The newest reading of the Arpa website is at least this old: hourly, about
40 minutes after the hour (measured on 2026-11-17). Asking it for a reading
younger than this cannot give a newer one."""

REALTIME_LAG: Final = timedelta(hours=3, minutes=30)
"""The newest record of the api_realtime is at least this old: it advances an
hour at a time, 3 h 40 min after it (measured on 2026-11-16 and 17)."""

WEBSITE_MIN_INTERVAL: Final = timedelta(minutes=20)
"""Least time between two requests to the Arpa website for a station: its
readings are hourly."""

REALTIME_MIN_INTERVAL: Final = timedelta(minutes=30)
"""Least time between two requests to the api_realtime for a station: it has
no cache headers, and its records change once an hour."""

UNAVAILABLE_AFTER: Final = timedelta(hours=6)
"""Age after which a reading is not shown: older than the oldest reading the
slowest source gives normally (4 h 40 min, the api_realtime)."""

MAX_CLOCK_SKEW: Final = timedelta(minutes=10)
"""A reading later than now by more than this is wrong, and not shown."""
