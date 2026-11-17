"""Tests of the readings of each source, as readings of the integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aioarpapiemonte import Param, ParamReading, ParamSeries, Validation

from custom_components.arpa_piemonte.adapters import (
    WEBSITE_PARAMS,
    from_website,
    series_of_website,
    thresholds_of_website,
)
from custom_components.arpa_piemonte.models import (
    Measurement,
    Quantity,
    Reading,
    Source,
)

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


def test_website_series_of_pressure_and_radiation() -> None:
    """Test the series of the quantities only the website gives, for the charts.

    Over the span before the newest reading; invalid readings are left out;
    the other quantities have the series of Meteo 3R.
    """
    hour = timedelta(hours=1)
    files = [
        (
            Quantity.PRESSURE,
            series(
                ParamReading(TWO - 3 * hour, 969.0, Validation.OK),
                ParamReading(TWO - 2 * hour, 969.5, Validation.OK),
                ParamReading(TWO - hour, 1500.0, Validation.INVALID),
                ParamReading(TWO, 970.2, Validation.TO_VERIFY),
                param=Param.PRESSURE,
            ),
        ),
        (Quantity.SOLAR_RADIATION, series(param=Param.RADIATION)),
        (Quantity.LEVEL, series(ParamReading(TWO, 0.86, Validation.OK))),
    ]

    assert series_of_website(files, span=2 * hour) == {
        Quantity.PRESSURE: (Reading(TWO - 2 * hour, 969.5), Reading(TWO, 970.2)),
    }


def test_website_files_of_pressure_and_radiation() -> None:
    """Test that the files read are the barometer and the radiometer."""
    assert WEBSITE_PARAMS[Quantity.PRESSURE] is Param.PRESSURE
    assert WEBSITE_PARAMS[Quantity.SOLAR_RADIATION] is Param.RADIATION
