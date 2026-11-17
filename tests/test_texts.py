"""Tests of the texts and icons: every entity has both, in every language."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.arpa_piemonte.binary_sensor import FLOOD_RISK
from custom_components.arpa_piemonte.image import CHARTS
from custom_components.arpa_piemonte.models import LevelStatus, Quantity, Source
from custom_components.arpa_piemonte.sensor import MEASUREMENTS, STATION_SENSORS

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "arpa_piemonte"
STRINGS = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
ICONS = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))
LANGUAGES = sorted(path.stem for path in (INTEGRATION / "translations").glob("*.json"))
KEYS = [description.key for description in (*MEASUREMENTS, *STATION_SENSORS)]


def paths(data: Any, prefix: str = "") -> set[str]:
    """Return the paths of the texts of a translation."""
    if isinstance(data, dict):
        return {
            path
            for key, value in data.items()
            for path in paths(value, f"{prefix}/{key}")
        }
    return {prefix}


def test_english_is_the_strings() -> None:
    """Test that the English translation is strings.json."""
    english = json.loads((INTEGRATION / "translations" / "en.json").read_text("utf-8"))

    assert english == STRINGS
    assert LANGUAGES == ["en", "it", "pt-BR"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_text_in_every_language(language: str) -> None:
    """Test that every language has the same texts."""
    translation = json.loads(
        (INTEGRATION / "translations" / f"{language}.json").read_text("utf-8")
    )

    assert paths(translation) == paths(STRINGS)


def test_every_entity_has_a_name_and_an_icon() -> None:
    """Test the names, states and icons of every entity."""
    sensors = STRINGS["entity"]["sensor"]
    icons = ICONS["entity"]["sensor"]

    assert (
        set(STRINGS["entity"])
        == set(ICONS["entity"])
        == {
            "binary_sensor",
            "image",
            "sensor",
        }
    )
    assert set(sensors) == set(KEYS) == set(icons)
    assert (
        set(STRINGS["entity"]["binary_sensor"])
        == {FLOOD_RISK.key}
        == set(ICONS["entity"]["binary_sensor"])
    )
    assert (
        set(STRINGS["entity"]["image"])
        == {chart.key for chart in CHARTS}
        == set(ICONS["entity"]["image"])
    )
    assert {quantity.value for quantity in Quantity} <= set(KEYS)
    assert set(sensors["level_status"]["state"]) == {
        status.value for status in LevelStatus
    }
    assert set(icons["level_status"]["state"]) == {
        status.value for status in LevelStatus
    }
    assert set(sensors["data_source"]["state"]) == {source.value for source in Source}
