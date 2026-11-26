# AGENTS.md: Arpa Piemonte

Guidance for AI coding agents and contributors working on this repository.
`CLAUDE.md` imports this file.

Arpa Piemonte is a Home Assistant custom integration (domain `arpa_piemonte`),
installed from the Marketplace of Home Assistant. It turns a station of the
Piedmont network of Arpa Piemonte into a device with the sensors the station
has: water level, its status against the thresholds and its flood risk, rain,
temperature, humidity, wind, snow. Each municipality is a config entry, and
each of its stations a subentry; the entry has a device of the natural risks
of the municipality too, from its widget on the Arpa website.

Everything that talks to the sources or parses their files lives in two
libraries, maintained alongside this repository:
[aiometeo3r](https://github.com/webysther/aio-meteo3r) (the Meteo 3R app, the
primary source) and
[aioarpapiemonte](https://github.com/webysther/aio-arpa-piemonte) (the files
of the Arpa website and the api_realtime, the fallback, and the natural
risks). This repository holds the Home Assistant side only, and the choice
among the sources.

## Ground rules

- **Do not commit, amend, push, tag, release or move branches** (`reset`,
  `branch -f`, `rebase`). Leave every change uncommitted in the working tree;
  the maintainer reviews and commits it. Read-only git commands are fine.
- Ask before anything that leaves the machine: releases, PRs, issues,
  comments.
- Reply in the language the person writes in. Code, comments, docstrings,
  docs, the changelog and commit messages are in English.
- Check instead of guessing. For Home Assistant behaviour, read its source in
  the test environment (`site-packages/homeassistant`). For data questions,
  measure the live sources with a throwaway script outside the repository,
  politely.
- Parsing and HTTP fixes belong in the libraries. Here, only Home Assistant
  code and the fallback.

## Layout

```text
custom_components/arpa_piemonte/
  __init__.py      setup and unload of a municipality, a coordinator per station
                   and one of its risks
  config_flow.py   a municipality (searched), then its station; the subentry
                   flow adds another; reconfigure reads the stations again; the
                   options of the risks: warning level, position, radius of the
                   earthquakes, heat-wave city
  catalog.py       the stations of the list by municipality, rivers first (pure)
  migration.py     version 1 (an entry per station) merged by municipality, in
                   async_setup; station_places.py is its table, which gives the
                   position of the stations added before it was stored too
  sources.py       the clients of the sources, shared by every station
  coordinator.py   ArpaPiemonteCoordinator, one per station: Meteo 3R at every
                   update, the official sources as a fallback (SourceTracker);
                   RisksCoordinator, a coordinator per risk of a municipality
                   (alerts, earthquakes, heat, avalanches) and the change of
                   day at midnight in Italy; where the risks are taken from
                   (async_risk_place)
  risks.py         the days of the risks in Italy, their keys, states, options,
                   position, heat-wave city and nearby earthquakes (pure)
  selection.py     which reading of the sources a station shows (pure)
  adapters.py      the readings of each source as readings of the integration,
                   and which source gives which quantity (pure)
  models.py        Quantity, Source, Thresholds, Measurement, StationSnapshot,
                   StationConfig, Position (pure)
  entity.py        the device of the station, and of the risks; sensor.py,
                   binary_sensor.py (the flood risk, from the level status, and
                   each risk on each day), geo_location.py (the earthquakes),
                   diagnostics.py
  charts.py        the charts of the Meteo 3R series, drawn as SVG (pure);
                   image.py serves them, one image entity per chart
  dashboard.py     serves frontend/ and has the frontend load its modules
  frontend/        the dashboard strategy (arpa-piemonte-dashboard.js) and the
                   card (arpa-piemonte-card.js): plain JavaScript, no build,
                   native cards only
  const.py         constants, each with the measurement behind it
  strings.json, translations/ (the 13 languages of DPC Alert: en, it, fr,
  de, es, pt-BR, ro, sq, ar, zh-Hans, uk, bn, hi), icons.json,
  quality_scale.yaml, manifest.json, version.py
tests/             pytest-homeassistant-custom-component; the sources served by
                   aioclient_mock with unmodified files in tests/fixtures
tests/frontend/    node:test tests of the dashboard strategy and the card
release.sh         releases, run by the maintainer
docs/research.md   decisions, DPC parity, roadmap and what is still unverified
```

## Checks

Python 3.14, as required by the pinned `pytest-homeassistant-custom-component`
(which also pins the Home Assistant version of the tests):

```bash
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
ruff format custom_components tests && ruff check custom_components tests
mypy                                   # strict, configured in pyproject.toml
pytest --cov --cov-report=term-missing
node --test "tests/frontend/*.test.mjs"   # the dashboard strategy and the card
npx prettier --check .                    # the JavaScript and the YAML
```

CI runs them (`tests.yaml`, with a `node` job), with hassfest and the checks of the Marketplace
(`hacs/action`, in `validate.yaml`). Keep the coverage of
`custom_components/arpa_piemonte` at 100%.

To check the minimum version, run the tests in a scratch venv (Python 3.13)
with `pytest-homeassistant-custom-component==0.13.232`, which pins Home
Assistant 2025.4.0; the diagnostics tests fail there because of its harness.

## The sources

Read [docs/research.md](docs/research.md) before researching the sources or
planning a feature: the decisions taken with the maintainer, what DPC offers
and what Arpa can feed, the roadmap, and what is still unverified. It links
the studies of the sources in the two libraries
(`aio-meteo3r/docs/meteo3r-data.md`, `aio-arpa-piemonte/docs/arpa-data.md`
and `docs/arpa-risk-products.md`).

Measured on 2026-11-16 and 17, see the libraries for the details:

- Meteo 3R: every 30 minutes, ~40 minutes late, two hosts (the library falls
  back between them). Equal to the api_realtime for every quantity.
- Files of the Arpa website: hourly, ~40 minutes late. Equal to Meteo 3R for
  level, temperature, humidity and snow only: their rain is of 10 minutes and
  their wind in m/s, so neither is read (`WEBSITE_PARAMS`). The only source of
  the pressure (`baro`) and the solar radiation (`radd`): Meteo 3R and the
  api_realtime have neither (`WEBSITE_QUANTITIES`).
- The barometers and radiometers are those the list of stations of the
  website names (45 and 64), stored in the subentry (`website_params`) when a
  station is added or read again; the letters B and R (47 and 66) name dead
  sensors too, and stand in only when the files are unknown (None).
- api_realtime: hourly, ~3 h 40 min late, every quantity in one request.
- A station has two identifiers: its code in the network ("188") and its
  identifier on the website ("002105900"); the config flow stores both.

How a station chooses (`coordinator.py`, `selection.py`):

- Meteo 3R is asked at every update (10 minutes, conditional requests).
- A quantity falls back when Meteo 3R fails or its reading is older than
  `PRIMARY_STALE_AFTER`. An official source is asked only when it could give a
  newer reading than the one shown (`WEBSITE_LAG`, `REALTIME_LAG`), and not
  more often than its pace (`*_MIN_INTERVAL`).
- Each quantity shows the newest current reading of all; on the same time,
  the preferred source. A source never takes a quantity back in time.
- The pressure and the solar radiation, which Meteo 3R never gives, are asked
  of the website at its pace (`WEBSITE_MIN_INTERVAL`); their charts are those
  of its files, over the span of Meteo 3R (`WEBSITE_SERIES_SPAN`). The data
  source leaves them out, so it still says whether Meteo 3R answers.
- The snapshot holds no download time: an update without new readings is
  equal to the previous one and writes nothing (`always_update=False`).

The natural risks of a municipality (`risks.py`, the second coordinator),
measured on 2026-11-17 and 18:

- The widget of the municipality (`/rischi_naturali/widget/comuni/<ISTAT>/`),
  by its current ISTAT code, the code of the entry. Arpa rebuilds it about
  every 10 minutes and answers 304 when it did not change: it is asked every
  10 minutes (`RISKS_UPDATE_INTERVAL`), and an unchanged answer writes
  nothing. Its page is the link of the device of the risks.
- The alert bulletin is issued around 13:00 for that day and the next: in the
  morning, its first day is yesterday. The entities show today and tomorrow
  in Italy (`ROME_TZ`), with `MunicipalityAlerts.level_on`, and change day at
  midnight in Italy without a download (`async_follow_the_days`).
- The danger now is assessed every few hours (06:50 and 09:51 on 2026-11-18),
  from the rain and the river levels of the last 24 hours.
- The risks do not stop the stations: without the widget at setup, their
  entities are unavailable until it answers.
- The widget covers the municipalities of Piedmont only (`PIEDMONT_PROVINCES`):
  Palestro, in the province of Pavia, has a station but no widget (404).
- Each risk has its coordinator, created only when the municipality has it:
  the earthquakes (every 10 minutes, the list of 30 days of Arpa, within the
  radius of the position), the heat waves (every 30 minutes, the bulletin of
  one of the 8 capitals, 15 May to about 30 September), the avalanches (every
  hour, every 6 out of season, the bulletins of EAWS of today and tomorrow for
  the micro-region of the position, December to May).
- The position is the mean of the stations, or the home (`CONF_POSITION`).
  The micro-region is that of the position or, when the mean of the stations
  is in none, of the first station in one (6 of 106 municipalities). The
  diagnostics redact what locates the home, and never give the distances of
  the earthquakes.

## Compatibility

Users' automations and dashboards depend on what the integration exposes.

- Never change unique IDs: entries are `ISTAT_<municipality code>` (the
  current ISTAT code), stations are subentries `PIE_<station code>`, as their
  devices, and entities `PIE_<station code>-<key>`, with the keys of
  `Quantity`, of `STATION_SENSORS`, of `CHARTS` and `flood_risk`. The device
  of the risks of a municipality is `ISTAT_<municipality code>`, in its entry
  without subentry, and its entities `ISTAT_<municipality code>-<key>`, with
  the keys of `RISK_SENSORS` and of `RISKS` (binary_sensor.py), and
  `earthquake_<ID of Arpa>` for the earthquakes. Version 1 had an entry
  `PIE_<station code>` per station: `migration.py` moves them.
- Never rename the states of the enum sensors (`LevelStatus`, `Source`, and of
  the risks: `ALERT_LEVELS`, `PHASES`, `HEAT_LEVELS`, `AVALANCHE_DANGERS`), nor
  the values of the options (`warning_level`: yellow, orange, red; `position`:
  stations, home; `heat_city`: province, nearest).
- Changing the shape of entry or subentry data needs a migration and a new
  `MINOR_VERSION` (or `VERSION` when older releases cannot load it). Merging
  or splitting entries happens in `async_setup`, before they load, as
  `migration.py` does.
- Supported Home Assistant: from the `homeassistant` version in `hacs.json`
  (the file the Marketplace reads, under that name; 2025.4.0, the first with
  `MEASUREMENT_ANGLE`) to the latest. Import the
  validation library both ways (`probatio` from 2026.9, `voluptuous` before).
  The device registry changed in 2026.8 (a device in one entry); see
  "Home Assistant, checked" in `docs/research.md`.

## Home Assistant conventions

- `strings.json` is the source of the texts and `translations/en.json` is
  identical to it; every key exists in each language (`tests/test_texts.py`).
- Data is an entity, not an attribute: the measurement sensors have no
  attributes, which would change at every download and be recorded again.
- Every entity has an icon in `icons.json`, and the enum states have theirs.
- `quality_scale.yaml` states each rule of the integration quality scale. Keep
  it true when a change affects a rule.
- The README is the page users install from, through the Marketplace, and
  holds the sections the quality scale asks for: keep them current.
- The README is translated: `README.<language>.md` at the root, with the tag
  Home Assistant names the language with (`README.it.md`, `README.fr.md`,
  `README.es.md`, `README.de.md`), and the same line of language links at the
  top of each. A change to `README.md` changes every translation, in the same
  commit. The translations name what the integration shows with its texts in
  their language (`translations/<language>.json`), and the menus of Home
  Assistant as its frontend does in that language; they keep the entity IDs,
  the YAML keys, the URLs and the images of `README.md`. The Marketplace
  shows `README.md`;
  [home-assistant/core#189842](https://github.com/home-assistant/core/pull/189842),
  merged on 2026-11-26, shows the translation of the language of the user, by
  these names, once released.
- Credit the data: every entity has the attribution of Arpa Piemonte, and the
  device links to the page of its station.
- `brand/` holds the icon and logo of Arpa Piemonte, as Home Assistant 2026.3
  and newer read them (`icon.png` 256 px, `icon@2x.png` 512 px, transparent;
  `dark_icon*` on a white plate; `logo.png` 256 px high, `logo@2x.png` 512
  px), made from a transparent high-resolution logo of Arpa without changing
  it. The License section of the README
  says the trademarks belong to their owners, as in DPC Alert: keep it.
- The dashboard and the card find the stations by the identifier of their
  device (`["arpa_piemonte", "PIE_<code>"]`), the risks by that of theirs
  (`["arpa_piemonte", "ISTAT_<code>"]`), and the entities by their
  translation key, never by entity ID; the municipalities are the entries,
  named by `config_entries/get`, which needs no admin. They color the level
  status, the flood risk and the levels of the risks with the colors of the
  alert maps (`LEVEL_STATUS_COLORS`, `ALERT_COLORS`), the operational phase
  with those of the legend of the widget (`PHASE_COLORS`), name the entities
  in the language of the user (`withTexts`), and gate what newer versions of
  Home Assistant have with `isAtLeast`: check each card option against the
  frontend of 2025.4 (`home-assistant-frontend==20250401.0`). The Add
  dashboard dialog lists custom strategies from 2026.5 only, and a strategy is
  generated again when its `registryDependencies` change from 2026.7; before,
  when the page loads.
- The card draws nothing of its own: an `ha-card` with native cards inside,
  created with `loadCardHelpers`, without their own background. Its visual
  editor is an `ha-form`, which the frontend defines only with the editor of
  one of its cards: the card loads the editor of a tile first. The editor
  writes only the options that differ from what the card shows without them.
- The frontend is served at `/arpa_piemonte/frontend/<version>/`
  (`FRONTEND_URL`), so that browsers load it again after an update, and the
  card imports the strategy by relative path. A new module goes in
  `FRONTEND_MODULES`.

## Tests

- Never reach the network: serve the fixtures with `aioclient_mock` (the first
  matching route wins: `clear_requests()` before serving again), or patch the
  methods of the clients in the config flow tests.
- Never depend on the clock: the time is frozen at `NOW` (`tests/__init__.py`),
  40 minutes after the newest reading of the fixtures. The tests of the risks
  move it to the morning or the afternoon of the bulletin of the widgets.
- Every entry asks for its risks as it is set up: the fixture `mock_risks`
  serves the widget of Pray for every municipality (parametrize `widget`), the
  earthquakes (parametrize `earthquakes`), the heat waves of the 8 capitals and
  no avalanche bulletin, as in November; `serve_the_risks()` serves them again
  after `clear_requests()`, and `requested()` leaves the risks out.
- Home Assistant updates the `last_reported` of the state it has when it is
  written again: keep the value before, and move the clock, to check that
  nothing was written.

## The libraries

Their versions are pinned exactly in `manifest.json` (`requirements`) and in
`requirements_test.txt`. Bump both together, and only once the release is on
PyPI.

## Changelog and releases

- `CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/):
  entries under `## [Unreleased]`, written for the users of the integration.
- Versions are CalVer, `YEAR.MONTH.PATCH`. A beta `YEAR.MONTH.PATCHbN` is a
  GitHub pre-release.
- The maintainer releases with `./release.sh VERSION [--dry-run]`. The version
  lives in the git tag only: leave `"version": "0.0.0"` in `manifest.json` and
  `"develop"` in `version.py`; the release workflow writes them and attaches
  `arpa_piemonte.zip`, the file the Marketplace installs.

## Code style

- Readable, descriptive code over clever code: descriptive names, typed models
  and enums instead of raw dicts, small focused helpers, docstrings that say
  what and why.
- No magic numbers: a `Final` constant whose docstring says where its value
  comes from (see `PRIMARY_STALE_AFTER`).
- mypy strict. A `# type: ignore[code]` needs a comment saying why.
- Comments explain why, not what.
