# Research notes and roadmap

What was studied, decided and planned for ARPA Piemonte on 2026-11-17, so that
the next person, or the next AI session, starts from here instead of
researching the sources again.

Measured on 2026-11-16 and 17. The numbers are measurements of those days:
measure again, politely, before relying on one. Anything not confirmed is
marked **Unverified**.

The sources themselves are documented in the libraries:

- [Meteo 3R](https://github.com/webysther/aio-meteo3r/blob/main/docs/meteo3r-data.md): the
  registry and the station files, the series of 3 to 4 days, the quantities,
  the daily extremes, the registry facts (278 municipalities, 62 rivers,
  sensor letters).
- [Station files of the website and api_realtime](https://github.com/webysther/aio-arpa-piemonte/blob/main/docs/arpa-data.md):
  `sensors.geojson` and the parameters per station (`baro`, `radd` included),
  `pluv_hh`, the reading guide of Arpa, the OpenAPI of the api_realtime with
  `pie_neve` and `ggd`.
- [Natural-risk products](https://github.com/webysther/aio-arpa-piemonte/blob/main/docs/arpa-risk-products.md):
  the CAP-XML alert bulletin, the per-municipality widget JSON, current
  danger, vigilance, flood forecasts, landslides, snow and avalanches, heat,
  fire, earthquakes, open data, the ISTAT to alert-zone mapping, and the
  comparison with DPC.

## Decisions taken with the user

| Decision | Why |
| --- | --- |
| Municipality first, then station (by river) | 278 municipalities against 62 rivers; 264 of 374 stations have no river |
| Subentries: one entry per municipality | real grouping on the integration page |
| Skip the station step for a municipality with one station | 214 of 278 |
| DPC search model (dropdown with `custom_value`) | the user's choice; the frontend filters |
| Charts: SVG drawn by the integration, from the Meteo 3R series (3–4 days) | the threshold colours; no extra download |
| Dashboard strategy like DPC's (native cards, no build), and a card | the user's choice |
| Top of the level gauge: the highest threshold plus 25 %, or the level when higher; no gauge without thresholds | the user's choice, 2026-11-17 |
| Pressure and solar radiation: keys `pressure`, `solar_radiation`; the stations the website lists; charts too | the user's choices, 2026-11-17 |
| Breaking changes allowed without migrations while nobody uses the integration | the user, 2026-11-17 |
| One risk binary sensor (device class safety) derived from `level_status`, on from pre-alarm (pre_alarm, guard, danger), instead of three binaries per band | the user asked to derive a risk sensor from `sensor.arpa_piemonte_pray_sessera_level_status`; the user confirmed the on-from-pre-alarm rule on 2026-11-17 |
| Marketplace instead of HACS in README, AGENTS, pyproject, release.sh, .github | done |
| Natural risks from the whole widget of the municipality (each risk today and tomorrow, the danger now, the operational phase), although the widget asks to keep its layout unless only its bell is used | the user's choice, 2026-11-17 |
| Risk products: alerts by risk, earthquakes, heat waves, avalanches (EAWS) | the user's choice, 2026-11-17 |
| Risk entities like DPC: a risk device per municipality; per risk and day a level and a safety binary sensor, on from a warning level option (yellow by default); the highest alert; the bulletin as diagnostics | the user's choice, 2026-11-17 |
| Dashboard: a section of the risks at the top of each municipality | the user's choice, 2026-11-17 |
| The library first (aioarpapiemonte 0.2.0, published by the maintainer), then the integration | the user's choice, 2026-11-17 |
| Earthquakes and avalanches: an option for the position, the home or the stations of the municipality; earthquakes within 50 km by default, as DPC | the user's choice, 2026-11-17 |
| Heat waves: an option for the city, the capital of the province or the nearest capital | the user's choice, 2026-11-17 |

## What DPC offers, and what Arpa can feed

The DPC integration (`/code/dpc`, the user's) is the model for the risk side.

| DPC feature | DPC entities | DPC data | Arpa source for Piedmont |
| --- | --- | --- | --- |
| Headline alert | `highest_alert` (enum 1–4, `total_alerts`) | criticality max today and tomorrow | CAP `event`, or widget `allerta` |
| Headline precipitation | `highest_precipitation` (enum 1–5) | vigilance, 3 days | vigilance snippet `EVENT vig_0..4` |
| Zone names | `alert_zone`, `vigilance_zone` | zone name | widget `zone_di_allerta`, alert snippet `w23_data` |
| Bulletin times | `*_bulletin`, `*_valid_until` | id, published, valid_until | CAP `identifier`, `sent`, `expires`; widget `emesso_il`, `prossimo_aggiornamento` |
| Per-risk on/off | `hydraulic/thunderstorm/hydrogeological_risk` (binary SAFETY, `warning_level` option) | per risk | CAP or widget per risk, **plus snow and avalanches** |
| Per-risk level | `*_risk_level` (enum green…red) | per risk | same |
| Day alert | `alert` (enum, `risks`) | max of the day | CAP `_1224` / `_2436` |
| Criticality text | `criticality` (10 states) | "Rappresentata nella mappa" | CAP `EFFETTI SUL TERRITORIO` (free text) |
| National maps | `criticality_map`, `vigilance_map` (PNG) | DPC previews | (Arpa PDFs; no PNG found) |
| Day precipitation | `precipitation` (enum none…very_heavy) | vigilance | vigilance `PIOGGIA` |
| Phenomena near the place | `nearby_phenomena` + `geo_location` | DPC phenomena points | vigilance `icon[]` per zone (no points); earthquakes as points |
| Setup | map/zone → municipality → days/platforms → `warning_level`, radius, interval | point in polygon | ISTAT municipality → widget JSON |
| Dashboard | strategy + 3 cards, palette `#90c985 #f8f865 #f0bf01 #fd6767` | — | same style |

**Arpa only:** current danger, municipal operational phase, flood forecast
per section, landslides, heat, fire, avalanche danger, earthquakes, snow
sectors.

## Roadmap

One phase at a time; the maintainer commits and approves between phases.

0. **Document this study** in the three repositories (done: these files).
1. **Municipality, then station, and subentries** (done, unreleased).
   - The config flow picks the municipality with the DPC search model (a
     dropdown with `custom_value`, matched without accents, apostrophes or
     hyphens: "Mondovì" finds "Mondovi'"), then the station, the rivers
     first, and skips that step when the municipality has one station.
   - One config entry per municipality (`ISTAT_<current ISTAT code>`, the key
     of the widget JSON), one subentry per station (`PIE_<code>`), titled by
     its river or, without one, its name. Devices
     (`(arpa_piemonte, "PIE_<code>")`) and entity unique IDs
     (`PIE_<code>-<key>`) do not change.
   - The migration is one step, in `async_setup`, before the entries load,
     as Home Assistant does for OpenAI: no source is asked, the municipality
     of each station comes from `station_places.py` (the Meteo 3R list of
     2026-11-17, checked against the test fixture). The planned second step
     at setup, with the network, was dropped: the network is often not up
     yet when Home Assistant starts.
   - Checked on Home Assistant 2025.4.0 (the whole test suite, in a scratch
     venv) and 2026.10 (the pinned one): see "Home Assistant, checked" below.
2. **A flood risk binary sensor derived from the level status** (done,
   unreleased; the user's request: "derive a risk sensor" from
   `sensor.arpa_piemonte_pray_sessera_level_status`), like
   `binary_sensor.dpc_*_hydraulic_risk`. `binary_sensor.<station>_flood_risk`,
   device class safety, only on hydrometers with a stored threshold, on from
   pre-alarm (pre-alarm, guard, danger: the rule the user confirmed),
   unavailable without a level.
3. **Charts** (done, unreleased): SVG images drawn by the integration from
   the Meteo 3R series already downloaded (3 to 4 days), one image entity per
   chart the station has: level with the pre-alarm, guard and danger lines in
   yellow, orange and red; the rain of each hour (the `P_1H` readings on the
   hour) with its running total; temperature with 0 °C, humidity, snow, wind
   with the gusts as dots. No words, only units and values; times in the time
   zone of Home Assistant. The state of a chart is the time of its newest
   reading. Home Assistant serves any `image/` type, `image/svg+xml`
   included, from 2025.4 (checked).
4. **A dashboard strategy and a card** like DPC's (done, unreleased): plain
   JavaScript, native cards; a view per municipality (named by
   `config_entries/get`), a section per station, the hydrometers first; the
   flood risk as a badge and the level status as a tile, in the colours of
   the alert maps; a gauge with a band above each threshold, from 0 to the
   highest threshold plus 25 % (the user's choice); the readings and the
   charts. The card is the section of a station, with a visual editor (the
   user asked for it too). The Add dashboard dialog lists custom strategies
   from Home Assistant 2026.5 (frontend 20260429); before, the dashboard is
   added with its YAML.
5. **Pressure and solar radiation** (done, unreleased) from the website files
   `baro` and `radd`, the only source of them: Meteo 3R has no such series
   (checked on all 374 files, and again on 3 B/R stations, 2026-11-17).
   Unique ID keys `pressure` and `solar_radiation` (the user's choice). The
   stations are those `sensors.geojson` lists (45 and 64), stored in the
   subentry as `website_params`: the letters B and R name 47 and 66, the 4
   others with a file that is empty (Mombaldone), stale since 2025-01
   (Torino Reiss Romoli) or 2026-03 (Borgofranco), or missing (Sestriere). No
   migration (the user: nobody uses the integration yet): without
   `website_params`, the letters stand in. Charts of both, from the hourly
   files, over the 76 hours of Meteo 3R. The pressure is at the station, not
   at sea level (Avigliana, 344 m: 952 to 983 hPa).
6. **Natural risks**, in three stages (the user's choices, see the
   decisions above). The CAP alert, `pie_neve`, the snow sectors, the
   seismic class and the JSON embedded in the snippet pages (vigilance,
   floods, landslides, fire) are left out: the widget gives the alerts, the
   danger now and the phase of the municipality.
   - **6a, aioarpapiemonte 0.2.0** (done, released on 2026-11-18):
     `get_municipality_alerts()` (the widget), `get_earthquakes()`,
     `get_heat_forecast()` (the 8 capitals, `HeatCity.capital_of()` and
     `nearest()`), `get_avalanche_bulletin()` (EAWS, by micro-region) and
     `get_micro_region()`, with the 14 micro-regions of EAWS shipped in the
     package (CC0) and their names. Measured on 2026-11-18: the widget, the
     earthquakes and EAWS answer 304; the bulletin of the day comes out
     around 13:00, so in the morning the `day_0` of the widget is yesterday
     and today is `day_1` (`MunicipalityAlerts.level_on(risk, date)`); the
     names of the micro-regions in the EAWS bulletins are those before
     2022-03-04, numbered otherwise, so the names come from EAWS.
   - **6b, the integration** (done, unreleased): a device of the risks per
     municipality entry, `ISTAT_<code>`, in the entry without subentry, named
     "Pray · Natural risks" and linked to the page of the widget
     (`/rischi_naturali/widget/comuni/<ISTAT>/`, the page Arpa shows the
     widget in). Per risk and day (today and tomorrow in Italy) a level enum
     sensor and a safety binary sensor, on from the warning level option
     (yellow by default, orange or red); the highest alert of the two days;
     the danger now; the operational phase; the alert zone and the times of
     the bulletin as diagnostics. The widget is asked every 10 minutes, the
     entities change day at midnight in Italy, and the stations do not wait
     for it at setup. The dashboard has the section of the risks at the top of
     each municipality: the highest alert and the danger now in the colors of
     the alert maps, the phase in the colors of the legend of the widget, and
     the level of each risk on each day, tomorrow hidden until the bulletin
     covers it. aioarpapiemonte 0.2.0 pinned.
   - **6c, the integration**: the earthquakes as `geo_location` within a
     radius (50 km by default), the heat-wave level of the chosen city, and
     the avalanche danger of the micro-region of the chosen position (the
     home, or the stations of the municipality, which then need their
     coordinates in the subentry).
   - **A chore of aioarpapiemonte**, for its next release: read the `ETag`
     and `Last-Modified` of an answer without depending on how aiohttp names
     the headers, as aiometeo3r does. The client turns them into a `dict` and
     looks for `hdrs.ETAG` (`Etag`): the C parser of aiohttp names a known
     header that way, so the `ETag` of Arpa is found; the pure Python parser
     and the mock of the Home Assistant tests keep the name the server sent,
     and lose it (checked on 2026-11-18; the `Last-Modified` still works).

## Still unverified

### Sources

- **Meteo 3R:**
  - the window at midnight;
  - the meaning of the letters G, W, F and S.
- **Website files:**
  - whether ETags change every 15 min without new data;
  - `pluv_hh` and `nivo_v`, which the library does not read.
- **Risk products:**
  - the cadence of current danger: assessed at 06:50 and at 09:51 on
    2026-11-18, about every 3 hours, from two readings only;
  - `vig_2..4` and `PROBABILITA` values;
  - the names of the fire levels;
  - the colours of the widget other than VERDE and BIANCO (GIALLO,
    ARANCIONE and ROSSO are the names of its colour keys), and the phases
    other than "Nessuna Fase Operativa" (the names of its legend);
  - the time zone of earthquake `time_upd`, and `dati_elaborati` of an
    automatic event (all 28 of 2026-11-18 were "rivisti").
- **AINEVA:** the licence of the bulletins, and whether the micro-regions
  match Arpa's sectors.
- **Snippets not opened:** listed in the risk products doc.
- **Avalanches:** which host carries the IT-21 CAAML in season
  (`bollettini.aineva.it` or `static.avalanche.report`), and the bulletin
  licence.
- **Flood stations:** the snippet listed 27 stations in one survey and 28 in
  the other.
- **Weather forecast:** the structure of `meteo.xml` and its metadata file.
- **Open data:** the search API body of `dati.piemonte.it`, and the
  regional operational-phase WMS, which timed out.
- **Licences:** INGV (CC BY 4.0 is assumed); the DPC seismic CSV states none.
- **Snow:** how `pie_neve`, `nivo_v` and Meteo 3R `HS_V` relate (all are
  daily snow depth).

### Home Assistant

- Whether the native chart cards accept a colour per series (the frontend is
  not in the test venv).

### Session history

- The session that created the integration is not on this machine.

## Home Assistant, checked

Read in the source of each version (2026-11-17), and run with the test suite
on 2025.4.0 and 2026.10.

- **Subentries:** 2025.4 has everything the integration uses:
  `ConfigSubentryFlow` with `reconfigure`, `async_add_subentry`,
  `async_update_subentry`, `async_create_entry(subentries=...)`, and
  `config_subentry_id` in `async_add_entities` and both registries. Update
  listeners fire when a subentry is added, changed or removed.
- **Devices before 2026.8:** a device can belong to several entries. Moving
  it takes two calls of `async_update_device`, `add_config_entry_id` then
  `remove_config_entry_id`: in one call, the removal starts from the entries
  the device had and loses the one just added, or removes the device
  (2025.4 to 2026.7).
- **Devices from 2026.8:** a device belongs to one entry and subentry, moved
  with `new_config_entry_id` and `new_config_subentry_id`; `add_` and
  `remove_` are deprecated (alone, `add_` does nothing and `remove_` deletes
  the device). In 2026.10, `DeviceRegistry.async_get_device` and
  `DeviceEntry.config_entries_subentries` are deprecated too, and raise in
  the tests: use `dr.async_entries_for_config_entry`, which every version
  has.
- **Minimum version locally:** `pytest-homeassistant-custom-component==0.13.232`
  pins Home Assistant 2025.4.0 (Python 3.13). There, the diagnostics tests
  fail with `HAFakeDatetime` (freezegun in that harness), as they did before
  this change. Run again for Phase 6b on 2026-11-18, with aiometeo3r 0.1.0 and
  aioarpapiemonte 0.2.0 from PyPI: the rest passes.
- **Frontend of 2025.4** (`home-assistant-frontend==20250401.0`, read on
  2026-11-18): it has every icon of `icons.json` and of the dashboard, the
  `heading_style` subtitle of the heading card, and the `or` condition of the
  visibility of cards, which the section of the risks uses. The `alert` card
  of DPC is not there (Home Assistant 2026.9).
- **The `last_reported` of a state** is updated in place when the state is
  written again unchanged: a test compares the time kept before, after moving
  the clock.

## How this study was made

- Read-only surveys by AI agents on 2026-11-17, with about 190 sequential
  requests in all to arpa.piemonte.it, utility.arpa.piemonte.it,
  webgis.arpa.piemonte.it, bollettini.aineva.it, static.avalanche.report,
  regions.avalanches.org, webservices.ingv.it, dati.gov.it and GitHub, with a
  generic User-Agent. More than planned: keep future checks to a few
  requests, and throttle webgis.
- On 2026-11-18, for Phase 6a, about 26 requests: the samples again, the
  heat-wave widgets of the 8 capitals, the names of the micro-regions, the
  304 checks and the example of the README of the library.
- On 2026-11-18, for Phase 6b, one request: the page of the widget of Pray,
  the link of the device of the risks (it showed the bulletin of 2026-11-17
  for 17/11 and 18/11, and the danger now of 09:51). The frontend of 2025.4
  came from PyPI.
- Measurements on the fixtures of the repositories with throwaway scripts
  outside them.
- Documents read: Arpa's "Formato CAP-XML per allertamento meteoidrologico
  piemontese" v2.0 (2024-10-03, https://www.arpa.piemonte.it/media/5133),
  Arpa's "Dati orari in tempo reale – Guida alla lettura dei dati" v1.0
  (2024-10-03), and the brochure "Rischi naturali – Conoscerli per
  prevenirli" of Regione Piemonte (2019; its reproduction needs
  authorization, so it is only cited).
