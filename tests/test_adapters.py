"""Tests of the readings of each source, as readings of the integration."""

from __future__ import annotations

from datetime import UTC, datetime

from aioarpapiemonte import Param, ParamReading, ParamSeries, Validation

from custom_components.arpa_piemonte.adapters import (
    from_website,
    thresholds_of_website,
)
from custom_components.arpa_piemonte.models import Measurement, Quantity, Source

TWO = datetime(2026, 11, 17, 2, tzinfo=UTC)


def series(*readings: ParamReading, param: Param = Param.LEVEL) -> ParamSeries:
    """Return a file of the Arpa website with the given readings."""
    return ParamSeries(
        sensor_id="002105900", param=param, name="PRAY", readings=readings
    )


def test_website_reading_is_the_latest_valid() -> None:
    """Test that an invalid reading is skipped, and a file without any too."""
    files = [
        (
            Quantity.LEVEL,
            series(
                ParamReading(TWO, 1, Validation.SUSPECT),
                ParamReading(TWO.replace(hour=3), 9.0, Validation.INVALID),
            ),
        ),
        (Quantity.TEMPERATURE, series(param=Param.TEMPERATURE)),
    ]

    assert from_website(files) == {
        Quantity.LEVEL: Measurement(1.0, TWO, Source.ARPA_WEBSITE)
    }


def test_website_thresholds_of_other_quantities() -> None:
    """Test that a file without thresholds gives none."""
    assert thresholds_of_website(series(param=Param.TEMPERATURE)) is None
