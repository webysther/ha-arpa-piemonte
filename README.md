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
  <a href="https://www.home-assistant.io/integrations/marketplace/"><img alt="Marketplace custom repository" src="https://img.shields.io/badge/Marketplace-custom-41BDF5?logo=homeassistant&logoColor=white"></a>
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
  level, its status against the thresholds (normal, pre-alarm, guard, danger)
  and a flood risk, on from the pre-alarm threshold; a weather station its
  rain, temperature, humidity, wind and snow.
- The stations grouped by municipality: one entry per municipality, with its
  stations under it.
- The freshest readings: those of the Meteo 3R app of Arpa Piemonte, every 30
  minutes.
- When Meteo 3R does not answer, or a reading of it is too old, the official
  sources of Arpa Piemonte take over: the files of its website, then its
  api_realtime. The sensor **Data source** says which one is shown.
- The time of the measurement, not of the download: **Last measurement**.
- Charts of the last 3 to 4 days, as images: the level with its thresholds,
  the rain of each hour with its total, temperature, humidity, snow and wind.
  The integration draws them from the readings of Meteo 3R it already has.
- A [dashboard](#dashboard): a tab per municipality, a section per station,
  with the level in the colors of the alert maps and a gauge with its
  thresholds; and a [card](#card) of a station, in the card picker.

## Use cases

- Be warned when the river near home reaches the pre-alarm threshold, before
  the official bulletins.
- Follow the rain of the last 24 hours upstream of a river.
- Close the shutters when the wind gusts, cover the plants when it freezes.

## Installation

From the [Marketplace](https://www.home-assistant.io/integrations/marketplace/)
of Home Assistant:

[![Open your Home Assistant instance and open ARPA Piemonte in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=webysther&repository=ha-arpa-piemonte&category=integration)

1. Open the link above, or **Settings → Marketplace → Add from link**, and
   add `https://github.com/webysther/ha-arpa-piemonte`.
2. Open **ARPA Piemonte** and install it.

Home Assistant 2025.4 or newer.

## Configuration

**Settings → Devices & services → Add integration → ARPA Piemonte**, then
type the municipality of the station: the list has the 278 municipalities of
Piedmont with a station, and finds "Mondovì" as Arpa Piemonte writes it,
"Mondovi'". When the municipality has several stations, choose one: the
rivers first, then the weather stations. Choose the point of the river that
matters to you, not necessarily the nearest one.

Each municipality is an entry, with its stations under it. To add another
station of a municipality, choose **Add station** on its entry, or add the
integration again and choose the same municipality.

To read the sensors and thresholds of a station again from Arpa Piemonte,
choose **Read the station again** on the station. **Reconfigure** on the
entry of a municipality reads all its stations again.

The integration has no options.

## Removal

**Settings → Devices & services → ARPA Piemonte**: **Delete** in the three
dots of a station removes it; in those of a municipality, it removes the
municipality with its stations. To remove the integration, delete every
municipality, then uninstall it from the Marketplace.

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
- The charts show the readings of Meteo 3R only: while it does not answer,
  they keep its last readings. Their text is grey, darker or lighter when the
  browser says the page is light or dark, whatever the theme of Home
  Assistant.
- Before Home Assistant 2026.5, the dashboard is not listed under **Add
  dashboard**: add it with its YAML (see [Dashboard](#dashboard)).
- The dashboard reads the thresholds when it opens: the gauge of a station
  that had not answered yet appears after reloading the page.

## Troubleshooting

- **A sensor is unavailable**: the station has not measured it for 6 hours,
  or no source answers. Check the station on the
  [website of Arpa Piemonte](https://www.arpa.piemonte.it/rischi_naturali/snippets_arpa_graphs/dettaglio_stazione/)
  (the device links to its page).
- **Data source is not Meteo 3R**: Meteo 3R did not answer; the integration
  goes back to it as soon as it does.
- **The station cannot be added**: Arpa Piemonte did not answer; try again
  later.
- Otherwise, download the diagnostics (the three dots of the municipality on
  the page of the integration, or the page of the device of the station) and
  open an
  [issue](https://github.com/webysther/ha-arpa-piemonte/issues) with them and a
  debug log.

## Entities

Of each station, those of its sensors:

| Entity | Unit | Of a station with |
| --- | --- | --- |
| Water level | m above the hydrometric zero | hydrometer |
| Level status: normal, pre-alarm, guard, danger | | hydrometer |
| Flood risk (safety): on from the pre-alarm threshold | | hydrometer with a threshold |
| Pre-alarm, guard and danger threshold (diagnostic) | m | hydrometer |
| Rain 1 hour, 3 hours, 24 hours | mm | rain gauge |
| Temperature | °C | thermometer |
| Humidity | % | hygrometer |
| Wind speed, gust speed | km/h | anemometer |
| Wind direction, gust direction | ° | anemometer |
| Snow depth | cm | snow gauge |
| Data source (diagnostic): Meteo 3R, Arpa website, Arpa api_realtime | | every station |
| Last measurement (diagnostic) | | every station |
| Level, rain, temperature, humidity, snow, wind chart (image) | | the sensor it shows |

The entity IDs are in English: `sensor.arpa_piemonte_pray_sessera_level`,
`binary_sensor.arpa_piemonte_pray_sessera_flood_risk`,
`image.arpa_piemonte_pray_sessera_level_chart`.

The state of a chart is the time of its newest reading. The charts carry no
words, only units and values: the dashed lines of the level are the
pre-alarm (yellow), guard (orange) and danger (red) thresholds, the bars of
the rain are the rain of each hour, and the line its total over the chart
(right axis, Σ mm); the dots of the wind are the gusts.

## Automation examples

Be warned when the river reaches a threshold:

```yaml
automation:
  - alias: "Sessera above a threshold"
    triggers:
      - trigger: state
        entity_id: binary_sensor.arpa_piemonte_pray_sessera_flood_risk
        to: "on"
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

## Dashboard

The integration comes with a dashboard made of the cards of Home Assistant,
with the names of the entities in the language of each user. It has a tab for
each municipality and a section for each station, the hydrometers first:

- **The heading**: the name of the station, its flood risk in the color of its
  level, the time of its last measurement and, while it is not Meteo 3R, the
  source of its readings.
- **The level** of a hydrometer: its status in the colors of the alert maps,
  green, yellow, orange and red, and a gauge with a band above each threshold,
  from 0 to the highest threshold and a quarter more (Pray Sessera, with 2.3,
  3.0 and 3.8 m, goes to 4.75 m). A hydrometer without thresholds shows its
  level.
- **The readings**: temperature, humidity, the three rains, wind, gust and snow,
  as the station measures them.
- **The charts**, once Meteo 3R has given the readings of the station.

To add it, from Home Assistant 2026.5:

1. Go to **Settings → Dashboards → Add dashboard**.
2. Choose **ARPA Piemonte**. If it is not listed, reload the page.

Before Home Assistant 2026.5:

1. Go to **Settings → Dashboards → Add dashboard → New dashboard from scratch**,
   and open it.
2. Choose **⋮ → Edit dashboard**, then **⋮ → Raw configuration editor**.
3. Replace its content with:

   ```yaml
   strategy:
     type: custom:arpa-piemonte
   ```

The dashboard follows your stations and the names you give their devices:
from Home Assistant 2026.7 it changes by itself when you add or remove one;
before, when you reload the page. To show the stations
of a municipality in another dashboard, add a view with the strategy and the
ID of the entry of the municipality (`entry_id`, in its diagnostics):

```yaml
views:
  - title: Pray
    strategy:
      type: custom:arpa-piemonte
      entry_id: 01JCQK3Z5T3K8W6B2V4M9H7XNE
```

## Card

The card of a station, in the card picker as soon as the integration is
installed: search for **ARPA Piemonte** (`custom:arpa-piemonte-card`). It is
the section of the station in the dashboard, as a single card made of the
cards of Home Assistant: it finds the entities of the station even after you
rename them, colors the level status and the flood risk as the level is, and
shows the charts that have data.

The visual editor chooses the station and what the card shows. In YAML, an
option left out shows everything:

| Option | Without it |
| --- | --- |
| `device_id` | The first station. The ID of the device of the station, the end of the address of its device page. |
| `show_title: false` | The name of the station, above the rest. Without it, the badges move to the start. |
| `show_flood_risk: false` | The flood risk, in the color of the level, beside the name. |
| `show_last_measurement: false` | The time of the last measurement, beside the name. |
| `show_level: false` | The status of the level and its gauge. |
| `show_readings: false` | The readings. |
| `show_charts: false` | The charts. |
| `columns: 1` | The readings in two columns. |

```yaml
# The level of Pray Sessera and its charts, without the readings
type: custom:arpa-piemonte-card
device_id: 0123456789abcdef0123456789abcdef
show_readings: false
```

A chart alone, with the cards of Home Assistant:

```yaml
type: picture-entity
entity: image.arpa_piemonte_pray_sessera_level_chart
show_name: false
show_state: false
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
