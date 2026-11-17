# AGENTS.md: ARPA Piemonte

Guidance for AI coding agents and contributors working on this repository.
`CLAUDE.md` imports this file.

ARPA Piemonte is a Home Assistant custom integration (domain `arpa_piemonte`),
installed from the Marketplace of Home Assistant. It turns a station of the Piedmont network of Arpa
Piemonte into a device with the sensors the station has: water level and its
status against the thresholds, rain, temperature, humidity, wind, snow. Each
municipality is a config entry, and each of its stations a subentry.

Everything that talks to the sources or parses their files lives in two
libraries, maintained alongside this repository:
[aiometeo3r](https://github.com/webysther/aio-meteo3r) (the Meteo 3R app, the
primary source) and
[aioarpapiemonte](https://github.com/webysther/aio-arpa-piemonte) (the files
of the Arpa website and the api_realtime, the fallback). This repository holds
the Home Assistant side only, and the choice among the sources.

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
  config_flow.py   a municipality (searched), then its station; the subentry
                   flow adds another; reconfigure reads the stations again
  catalog.py       the stations of the list by municipality, rivers first (pure)
  migration.py     version 1 (an entry per station) merged by municipality, in
                   async_setup; station_places.py is its table
  sources.py       the clients of the sources, shared by every station
  coordinator.py   ArpaPiemonteCoordinator, one per station: Meteo 3R at every
                   update, the official sources as a fallback (SourceTracker)
  selection.py     which reading of the sources a station shows (pure)
  adapters.py      the readings of each source as readings of the integration,
                   and which source gives which quantity (pure)
  models.py        Quantity, Source, Thresholds, Measurement, StationSnapshot,
                   StationConfig (pure)
  entity.py        the device of the station; sensor.py, diagnostics.py
  const.py         constants, each with the measurement behind it
  strings.json, translations/ (en, it, pt-BR), icons.json, quality_scale.yaml,
  manifest.json, version.py
tests/             pytest-homeassistant-custom-component; the sources served by
                   aioclient_mock with unmodified files in tests/fixtures
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
npx prettier --check .                 # the YAML
```

CI runs them (`tests.yaml`), with hassfest and the checks of the Marketplace
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
  their wind in m/s, so neither is read (`WEBSITE_PARAMS`).
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
- The snapshot holds no download time: an update without new readings is
  equal to the previous one and writes nothing (`always_update=False`).

## Compatibility

Users' automations and dashboards depend on what the integration exposes.

- Never change unique IDs: entries are `ISTAT_<municipality code>` (the
  current ISTAT code), stations are subentries `PIE_<station code>`, as their
  devices, and entities `PIE_<station code>-<key>`, with the keys of
  `Quantity` and of `STATION_SENSORS`. Version 1 had an entry `PIE_<station
  code>` per station: `migration.py` moves them.
- Never rename the states of the enum sensors (`LevelStatus`, `Source`).
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
- Credit the data: every entity has the attribution of Arpa Piemonte, and the
  device links to the page of its station.
- `brand/` holds the icon and logo of Arpa Piemonte, as Home Assistant 2026.3
  and newer read them (`icon.png` 256 px, `icon@2x.png` 512 px, transparent;
  `dark_icon*` on a white plate; `logo.png` 256 px high, `logo@2x.png` 512
  px), made from a transparent high-resolution logo of Arpa without changing
  it. The License section of the README
  says the trademarks belong to their owners, as in DPC Alert: keep it.

## Tests

- Never reach the network: serve the fixtures with `aioclient_mock` (the first
  matching route wins: `clear_requests()` before serving again), or patch the
  methods of the clients in the config flow tests.
- Never depend on the clock: the time is frozen at `NOW` (`tests/__init__.py`),
  40 minutes after the newest reading of the fixtures.

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
