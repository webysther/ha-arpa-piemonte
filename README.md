<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/webysther/ha-arpa-piemonte/main/custom_components/arpa_piemonte/brand/dark_icon@2x.png">
    <img src="https://raw.githubusercontent.com/webysther/ha-arpa-piemonte/main/custom_components/arpa_piemonte/brand/icon@2x.png" alt="" width="128">
  </picture>
</p>

<h1 align="center">ARPA Piemonte</h1>

<p align="center">River levels, rain, temperature, wind and snow of the stations of Arpa Piemonte in Home Assistant</p>

<p align="center">
  <a href="https://github.com/webysther/ha-arpa-piemonte/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/webysther/ha-arpa-piemonte?label=release&color=41BDF5"></a>
  <a href="https://hacs.xyz/"><img alt="HACS custom repository" src="https://img.shields.io/badge/HACS-custom-41BDF5?logo=homeassistantcommunitystore&logoColor=white"></a>
  <a href="https://github.com/webysther/ha-arpa-piemonte/actions/workflows/tests.yaml"><img alt="Tests" src="https://github.com/webysther/ha-arpa-piemonte/actions/workflows/tests.yaml/badge.svg"></a>
  <a href="https://github.com/webysther/ha-arpa-piemonte/blob/main/LICENSE.md"><img alt="License" src="https://img.shields.io/github/license/webysther/ha-arpa-piemonte?color=41BDF5"></a>
</p>

The readings of the stations of [Arpa Piemonte](https://www.arpa.piemonte.it)
in Home Assistant: **river levels**, with the alert thresholds of each
hydrometer, **rain**, temperature, humidity, wind and snow, for any of the 374
stations of the Piedmont network.

> Not an official app of Arpa Piemonte, and not endorsed by it. The data is
> validated automatically only. Do not rely on it for safety: for alerts,
> follow the official bulletins and the civil protection.

## Features

- One device per station, with the sensors it has: a hydrometer gets its water
  level and its status against the thresholds (normal, pre-alarm, guard,
  danger); a weather station its rain, temperature, humidity, wind and snow.
- The freshest readings: those of the Meteo 3R app of Arpa Piemonte, every 30
  minutes.
- When Meteo 3R does not answer, or a reading of it is too old, the official
  sources of Arpa Piemonte take over: the files of its website, then its
  api_realtime. The sensor **Data source** says which one is shown.
- The time of the measurement, not of the download: **Last measurement**.

## Use cases

- Be warned when the river near home reaches the pre-alarm threshold, before
  the official bulletins.
- Follow the rain of the last 24 hours upstream of a river.
- Close the shutters when the wind gusts, cover the plants when it freezes.

## Installation

With [HACS](https://hacs.xyz):

1. **HACS → ⋮ → Custom repositories**: add
   `https://github.com/webysther/ha-arpa-piemonte`, type **Integration**.
2. Search **ARPA Piemonte**, **Download**, and restart Home Assistant.

Home Assistant 2025.4 or newer.

## Configuration

**Settings → Devices & services → Add integration → ARPA Piemonte**, then
choose the station: they are listed by name, river and municipality. Choose
the point of the river that matters to you, not necessarily the nearest one.

Add the integration again for each station. To read the sensors and
thresholds of a station again from Arpa Piemonte, choose **Reconfigure** on
its entry.

The integration has no options.

## Removal

**Settings → Devices & services → ARPA Piemonte**, the three dots of the
station, **Delete**. To remove the integration, delete every station, then
remove it from HACS.

## How the data is updated

Every 10 minutes, the integration asks Meteo 3R whether the file of the
station changed; most of the time it did not, and nothing is downloaded.
Meteo 3R publishes a reading every 30 minutes, about 30 to 45 minutes after it
was measured.

| Source | Readings | Late by | Asked |
| --- | --- | --- | --- |
| Meteo 3R | every 30 min | ~40 min | every 10 min |
| Files of the Arpa website (level, temperature, humidity, snow) | hourly | ~40 min | only as a fallback, every 20 min at most |
| api_realtime of Arpa Piemonte (everything) | hourly | ~3 h 40 min | only as a fallback, every 30 min at most |

Each sensor shows the newest reading of all the sources; on the same time,
Meteo 3R. A reading older than 6 hours is not shown: the sensor becomes
unavailable.

## Known limitations

- The history of Home Assistant records a reading when it is downloaded,
  30 to 45 minutes after it was measured. **Last measurement** gives the time
  of the measurement.
- Only the stations of Piedmont. Meteo 3R also shows those of Liguria and
  Valle d'Aosta, which belong to other bodies, under other terms.
- When only the api_realtime answers, the readings are about 4 hours old.
- Before Home Assistant 2026.3, the integration shows no icon: it ships its
  icon in its own folder, which older versions do not read.
- The data is validated automatically only, and Arpa Piemonte may correct it
  later. A sensor of a station can stop answering for days.
- The thresholds are those of Arpa Piemonte; not every hydrometer has all
  three (26 of 110 lack at least one).

## Troubleshooting

- **A sensor is unavailable**: the station has not measured it for 6 hours,
  or no source answers. Check the station on the
  [website of Arpa Piemonte](https://www.arpa.piemonte.it/rischi_naturali/snippets_arpa_graphs/dettaglio_stazione/)
  (the device links to its page).
- **Data source is not Meteo 3R**: Meteo 3R did not answer; the integration
  goes back to it as soon as it does.
- **The station cannot be added**: Arpa Piemonte did not answer; try again
  later.
- Otherwise, download the diagnostics (the three dots of the station on the
  page of the integration) and open an
  [issue](https://github.com/webysther/ha-arpa-piemonte/issues) with them and a
  debug log.

## Entities

Of each station, those of its sensors:

| Entity | Unit | Of a station with |
| --- | --- | --- |
| Water level | m above the hydrometric zero | hydrometer |
| Level status: normal, pre-alarm, guard, danger | | hydrometer |
| Pre-alarm, guard and danger threshold (diagnostic) | m | hydrometer |
| Rain 1 hour, 3 hours, 24 hours | mm | rain gauge |
| Temperature | °C | thermometer |
| Humidity | % | hygrometer |
| Wind speed, gust speed | km/h | anemometer |
| Wind direction, gust direction | ° | anemometer |
| Snow depth | cm | snow gauge |
| Data source (diagnostic): Meteo 3R, Arpa website, Arpa api_realtime | | every station |
| Last measurement (diagnostic) | | every station |

The entity IDs are in English: `sensor.arpa_piemonte_pray_sessera_level`.

## Automation examples

Be warned when the river reaches a threshold:

```yaml
automation:
  - alias: "Sessera above a threshold"
    triggers:
      - trigger: state
        entity_id: sensor.arpa_piemonte_pray_sessera_level_status
        to: ["pre_alarm", "guard", "danger"]
    actions:
      - action: notify.notify
        data:
          title: "Sessera at Pray"
          message: >-
            Level {{ states('sensor.arpa_piemonte_pray_sessera_level') }} m:
            {{ states('sensor.arpa_piemonte_pray_sessera_level_status') }}
```

Be warned when the river rises fast:

```yaml
automation:
  - alias: "Sessera rising"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.arpa_piemonte_pray_sessera_level
        above: 1.5
    actions:
      - action: notify.notify
        data:
          message: "The Sessera at Pray is above 1.5 m"
```

## Data source and attribution

The data is by **Arpa Piemonte**, under the
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
license ([legal notes](https://www.arpa.piemonte.it/note-legali)): "Fonte: Arpa
Piemonte - www.arpa.piemonte.it". Every entity carries this attribution, and
each device links to the page of its station.

The integration reads Meteo 3R with
[aiometeo3r](https://github.com/webysther/aio-meteo3r) and the official
sources with [aioarpapiemonte](https://github.com/webysther/aio-arpa-piemonte).

## Contributing

See [CONTRIBUTING.md](https://github.com/webysther/ha-arpa-piemonte/blob/main/CONTRIBUTING.md).

## License

The code of ARPA Piemonte is under the
[MIT License](https://github.com/webysther/ha-arpa-piemonte/blob/main/LICENSE.md).
The readings are data of Arpa Piemonte, under the
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) license: every entity
carries this attribution.

The names, logos and trademarks in this repository, such as those of Arpa
Piemonte, Meteo 3R and Home Assistant, belong to their owners and are used to
identify them only, without implying their endorsement. They are not covered
by the license of the code nor by the CC BY 4.0 license of the data.
