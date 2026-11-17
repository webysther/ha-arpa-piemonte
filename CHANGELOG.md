# Changelog

All notable changes to ARPA Piemonte are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are
`YEAR.MONTH.PATCH`.

## [Unreleased]

### Added

- A station is found by its municipality: type the name, with or without its
  accent ("Mondovì" finds "Mondovi'"), then choose the station when the
  municipality has several, the rivers first.
- The stations are grouped by municipality: each municipality is an entry,
  with its stations under it. **Add station** on the entry adds another
  station of the same municipality.
- Diagnostics of each station, on its device.
- **Flood risk**, a safety binary sensor of each hydrometer with a threshold:
  on from the pre-alarm threshold (pre-alarm, guard or danger), off below it.
- Charts of the last 3 to 4 days, as images: the level with its thresholds,
  the rain of each hour with its total, temperature, humidity, snow and wind,
  drawn from the readings of Meteo 3R, without another download.
- The ARPA Piemonte dashboard, made of the cards of Home Assistant: a tab per
  municipality and a section per station, with the flood risk and the level
  status in the colors of the alert maps, a gauge of the level with a band
  above each threshold, the readings and the charts. Listed under **Add
  dashboard** from Home Assistant 2026.5; before, added with its YAML.
- The ARPA Piemonte card, in the card picker: the section of a station as a
  single card, with a visual editor that chooses the station and what it
  shows.
- **Atmospheric pressure** and **solar radiation** of the stations with a
  barometer or a radiometer, with their charts, from the files of the Arpa
  website, the only source of them, read every 20 minutes. The barometers and
  radiometers are those the website lists when the station is added: **Read
  the station again** on a station added before finds them.

### Changed

- At the first start, the stations added before move to the entry of their
  municipality, with their devices, entities, entity IDs and history. A
  station disabled with its entry stays disabled. Going back to 2026.11.0
  afterwards needs the stations added again.
- **Reconfigure** on a municipality reads all its stations again; **Read the
  station again** reads one.

### Fixed

- When the list of Meteo 3R did not answer, a station without a river was
  listed and titled "-" instead of by its name (aioarpapiemonte 0.1.1).

## [2026.11.0] - 2026-11-17

First release.

### Added

- A station of Arpa Piemonte per config entry, chosen among the 374 stations
  of Piedmont, with the sensors it has: water level and its status against the
  thresholds, rain over 1, 3 and 24 hours, temperature, humidity, wind, gust
  and snow.
- The readings of Meteo 3R, every 30 minutes; when it does not answer, those
  of the files of the Arpa website and of the api_realtime. The sensors Data
  source and Last measurement say where each reading comes from and when it
  was measured.
- Reconfiguration, which reads the station again; diagnostics.
- The icon of Arpa Piemonte, shown from Home Assistant 2026.3.
- Texts in English, Italian and Brazilian Portuguese.

[Unreleased]: https://github.com/webysther/ha-arpa-piemonte/compare/v2026.11.0...HEAD
[2026.11.0]: https://github.com/webysther/ha-arpa-piemonte/releases/tag/v2026.11.0
