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
| Dashboard strategy like DPC's (native cards, no build) | the user's choice |
| One risk binary sensor (device class safety) derived from `level_status`, on from pre-alarm (pre_alarm, guard, danger), instead of three binaries per band | the user asked to derive a risk sensor from `sensor.arpa_piemonte_pray_sessera_level_status`; the on-from-pre-alarm rule is the default, to confirm |
| Marketplace instead of HACS in README, AGENTS, pyproject, release.sh, .github | done |

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
1. **Municipality, then station, and subentries.**
   - The config flow picks the municipality with the DPC search model (a
     dropdown with `custom_value`, matched without accents or apostrophes:
     "Mondovì" finds "Mondovi'"), then the station, named by its river, and
     skips that step when the municipality has one station.
   - One config entry per municipality (`ISTAT_<current ISTAT code>`, the key
     of the widget JSON), one subentry per station (`PIE_<code>`). Devices
     (`(arpa_piemonte, "PIE_<code>")`) and entity unique IDs
     (`PIE_<code>-<key>`) do not change.
   - A two-step migration: offline into a subentry, then at setup, with the
     station list, into the entry of its municipality (merging entries of the
     same municipality).
   - First check that Home Assistant 2025.4, the minimum, has every subentry
     API used; the device registry moves devices with `new_config_entry_id`
     in recent versions and with `add_`/`remove_` before.
2. **A flood risk binary sensor derived from the level status** (the user's
   request: "derive a risk sensor" from
   `sensor.arpa_piemonte_pray_sessera_level_status`), like
   `binary_sensor.dpc_*_hydraulic_risk`. Device class safety, only on
   hydrometers with thresholds, on from pre-alarm (pre-alarm, guard, danger),
   unavailable without a level. The pre-alarm rule is the default, to be
   confirmed.
3. **Charts:** SVG images drawn by the integration from the Meteo 3R series
   already downloaded (3 to 4 days): level with the pre-alarm, guard and
   danger lines in yellow, orange and red; hourly rain with its cumulative;
   temperature, humidity, snow, wind.
4. **A dashboard strategy** like DPC's: plain JavaScript, native cards; a
   view per municipality, a section per station; tiles coloured by the level
   status; a gauge with the thresholds as segments; the charts.
5. **Pressure and solar radiation** from the website files `baro` and `radd`
   (45 and 64 stations), only where `sensors.geojson` lists them.
6. **Natural risks.** In aioarpapiemonte first the stable machine-readable
   sources (CAP alert, widget JSON per municipality, `pie_neve`, earthquakes,
   heat, EAWS avalanches, snow sectors, seismic class), plus a static ISTAT
   to zones table; the JSON embedded in the snippet pages (current danger,
   vigilance, floods, landslides) only as optional; fire danger last. In the
   integration, a risk device per municipality entry, to be designed with the
   user.

## Still unverified

### Sources

- **Meteo 3R:**
  - the window at midnight;
  - whether B/R stations carry pressure or radiation series;
  - the meaning of the letters G, W, F and S.
- **Website files:**
  - whether ETags change every 15 min without new data;
  - `pluv_hh` and `nivo_v`, which the library does not read.
- **Risk products:**
  - a `304` on the products;
  - the cadence of current danger;
  - `vig_2..4` and `PROBABILITA` values;
  - the names of the fire levels;
  - the JSON of the 7 other heat cities;
  - the time zone of earthquake `time_upd`.
- **AINEVA:** the licence and headers, and whether the micro-regions match
  Arpa's sectors.
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

- Subentries in HA 2025.4, the minimum version.
- Whether the native chart cards accept a colour per series (the frontend is
  not in the test venv).

### Session history

- The session that created the integration is not on this machine.

## How this study was made

- Read-only surveys by AI agents on 2026-11-17, with about 190 sequential
  requests in all to arpa.piemonte.it, utility.arpa.piemonte.it,
  webgis.arpa.piemonte.it, bollettini.aineva.it, static.avalanche.report,
  regions.avalanches.org, webservices.ingv.it, dati.gov.it and GitHub, with a
  generic User-Agent. More than planned: keep future checks to a few
  requests, and throttle webgis.
- Measurements on the fixtures of the repositories with throwaway scripts
  outside them.
- Documents read: Arpa's "Formato CAP-XML per allertamento meteoidrologico
  piemontese" v2.0 (2024-10-03, https://www.arpa.piemonte.it/media/5133),
  Arpa's "Dati orari in tempo reale – Guida alla lettura dei dati" v1.0
  (2024-10-03), and the brochure "Rischi naturali – Conoscerli per
  prevenirli" of Regione Piemonte (2019; its reproduction needs
  authorization, so it is only cited).
