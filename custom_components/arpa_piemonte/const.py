"""Constants of the ARPA Piemonte integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final
from zoneinfo import ZoneInfo

from homeassistant.const import Platform

from .version import __version__

VERSION: Final = __version__
"""Version of the integration: the release tag, written by the release workflow."""

DOMAIN: Final = "arpa_piemonte"
LOGGER = logging.getLogger(__package__)
PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.IMAGE, Platform.SENSOR]

ATTRIBUTION: Final = "Fonte: Arpa Piemonte - www.arpa.piemonte.it"
"""Credit the data needs (CC BY 4.0, https://www.arpa.piemonte.it/note-legali)."""

MANUFACTURER: Final = "Arpa Piemonte"
"""The body that runs the stations: the data is theirs, the integration is not."""

ISSUE_URL: Final = "https://github.com/webysther/ha-arpa-piemonte/issues"

FRONTEND_URL: Final = f"/{DOMAIN}/frontend/{VERSION}"
"""URL of the modules of the frontend, loaded by the frontend of every user.

The browsers keep the modules in their cache: the version in the path makes
them load the modules again when the integration is updated, and the card
imports the dashboard strategy by a relative path, which keeps the version.
"""

FRONTEND_MODULES: Final = ("arpa-piemonte-dashboard.js", "arpa-piemonte-card.js")
"""The modules of the frontend: the dashboard strategy and the card."""

# Config entry data: a municipality
CONF_MUNICIPALITY_CODE: Final = "municipality_code"
"""ISTAT code of the municipality of the entry ("096050"), the current one, as
Meteo 3R and the api_realtime give it: the widget of the municipality on the
Arpa website uses the same code."""
CONF_MUNICIPALITY: Final = "municipality"
"""The field of the config flow where the municipality is chosen or typed."""

# Config entry options: the natural risks of the municipality
CONF_WARNING_LEVEL: Final = "warning_level"
"""The lowest level of a risk that turns its binary sensor on: "yellow",
"orange" or "red", as the levels of aioarpapiemonte name them."""
DEFAULT_WARNING_LEVEL: Final = "yellow"
"""A risk is on from the yellow alert, the first alert of the bulletin, as in
DPC."""

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
CONF_WEBSITE_PARAMS: Final = "website_params"
"""The files of the station on the Arpa website ("baro", "radd"...), as its list
of stations gives them when the station is added or read again. None when the
list did not answer: the letters of the sensors stand in for it."""

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
readings are hourly. It is the pace of the pressure and the solar radiation,
which only the website gives."""

WEBSITE_SERIES_SPAN: Final = timedelta(hours=76)
"""How far back the charts of the files of the website go: as those of Meteo
3R, whose files hold 3 days and 4 hours of readings (measured on 2026-11-17),
while those of the website hold about 6 days."""

REALTIME_MIN_INTERVAL: Final = timedelta(minutes=30)
"""Least time between two requests to the api_realtime for a station: it has
no cache headers, and its records change once an hour."""

UNAVAILABLE_AFTER: Final = timedelta(hours=6)
"""Age after which a reading is not shown: older than the oldest reading the
slowest source gives normally (4 h 40 min, the api_realtime)."""

MAX_CLOCK_SKEW: Final = timedelta(minutes=10)
"""A reading later than now by more than this is wrong, and not shown."""

RISKS_UPDATE_INTERVAL: Final = timedelta(minutes=10)
"""How often the widget of the municipality is asked for its natural risks.

Arpa rebuilds the widget about every 10 minutes, and answers ``304 Not
Modified`` when it did not change (measured on 2026-11-17 and 18). Its parts
change less often: the alert bulletin once a day, around 12:00 to 13:00; the
danger now every few hours (assessed at 06:50 and at 09:51 on 2026-11-18); the
operational phase when the municipality declares one.
"""

ROME_TZ: Final = ZoneInfo("Europe/Rome")
"""The time zone of the days of the alert bulletin: today and tomorrow are
those of Italy, whatever the time zone of Home Assistant."""
