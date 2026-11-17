# Changelog

All notable changes to ARPA Piemonte are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are
`YEAR.MONTH.PATCH`.

## [Unreleased]

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
