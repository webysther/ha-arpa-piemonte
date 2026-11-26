# Contributing to Arpa Piemonte

Thank you for helping! Problems and ideas go in the
[issues](https://github.com/webysther/ha-arpa-piemonte/issues): for a problem,
attach the diagnostics of the station and a debug log.

## Where things are

- This repository holds the Home Assistant side only: the config flow, the
  coordinator that chooses among the sources, the sensors.
- Reading Meteo 3R is in [aiometeo3r](https://github.com/webysther/aio-meteo3r);
  reading the official sources of Arpa Piemonte in
  [aioarpapiemonte](https://github.com/webysther/aio-arpa-piemonte). A problem
  with the data of a source is fixed there.

## Set up and run the checks

Python 3.14, as the pinned `pytest-homeassistant-custom-component` requires:

```bash
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
ruff format custom_components tests && ruff check custom_components tests
mypy
pytest --cov --cov-report=term-missing
```

The tests never reach Arpa Piemonte: they serve unmodified files of it, in
`tests/fixtures`, with `aioclient_mock`, at a frozen time. Keep the coverage of
`custom_components/arpa_piemonte` at 100%.

## Rules that protect the users

- Never change the unique IDs of the entries (`PIE_<station code>`) or of the
  entities (`<entry unique ID>-<key>`).
- A change to the data of the config entries needs a migration step.
- The texts are in `strings.json`, equal to `translations/en.json`, and in
  every language of `translations/`.
- The README is translated: a change to `README.md` changes `README.it.md`,
  `README.fr.md`, `README.es.md` and `README.de.md` too.

## Using AI

AI tools are welcome. This project follows the
[AI policy of Home Assistant](https://contributors.home-assistant.io/start/ai-policy/):
you are responsible for what you submit, and you have read and tested it.
