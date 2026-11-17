"""Tests of the choice of the readings, and of the models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.arpa_piemonte.const import MAX_CLOCK_SKEW, UNAVAILABLE_AFTER
from custom_components.arpa_piemonte.models import (
    LevelStatus,
    Measurement,
    Quantity,
    Source,
    StationConfig,
    StationSnapshot,
    Thresholds,
)
from custom_components.arpa_piemonte.selection import is_current, newest, select

NOW = datetime(2026, 11, 17, 2, 40, tzinfo=UTC)
TWO = datetime(2026, 11, 17, 2, tzinfo=UTC)
ONE = datetime(2026, 11, 17, 1, tzinfo=UTC)


def reading(value: float, at: datetime, source: Source = Source.METEO3R) -> Measurement:
    """Return a reading."""
    return Measurement(value, at, source)


def test_newest_reading_wins() -> None:
    """Test that the newest reading wins, whatever its source."""
    older = reading(1.0, ONE)
    newer = reading(2.0, TWO, Source.ARPA_REALTIME)

    assert newest([older, newer], NOW) is newer


def test_preferred_source_wins_on_the_same_time() -> None:
    """Test that Meteo 3R wins over the official sources on the same time."""
    website = reading(1.0, TWO, Source.ARPA_WEBSITE)
    meteo3r = reading(1.0, TWO, Source.METEO3R)

    assert newest([website, meteo3r], NOW) is meteo3r
    assert newest([meteo3r, website], NOW) is meteo3r


def test_first_wins_on_the_same_time_and_source() -> None:
    """Test that the first of two equal readings wins: the latest download."""
    corrected = reading(0.9, TWO)
    shown = reading(0.86, TWO)

    assert newest([corrected, shown], NOW) is corrected


@pytest.mark.parametrize(
    ("at", "current"),
    [
        (NOW - UNAVAILABLE_AFTER, True),
        (NOW - UNAVAILABLE_AFTER - timedelta(minutes=1), False),
        (NOW + MAX_CLOCK_SKEW, True),
        (NOW + MAX_CLOCK_SKEW + timedelta(minutes=1), False),
    ],
)
def test_current_readings(at: datetime, current: bool) -> None:
    """Test that readings too old or in the future are not current."""
    assert is_current(reading(1.0, at), NOW) is current


def test_select_never_goes_back_in_time() -> None:
    """Test that a source with an older reading does not replace the one shown."""
    shown = {Quantity.LEVEL: reading(0.86, TWO)}
    sources = [{Quantity.LEVEL: reading(0.80, ONE)}, {}]

    selected = select(sources, shown, [Quantity.LEVEL, Quantity.TEMPERATURE], NOW)

    assert selected == shown


def test_select_leaves_out_what_is_not_current() -> None:
    """Test that a quantity without a current reading is left out."""
    old = NOW - UNAVAILABLE_AFTER - timedelta(hours=1)

    selected = select(
        [{Quantity.LEVEL: reading(1.0, old)}],
        {Quantity.TEMPERATURE: reading(9.0, NOW + timedelta(hours=1))},
        [Quantity.LEVEL, Quantity.TEMPERATURE],
        NOW,
    )

    assert selected == {}


def test_select_only_the_quantities_asked() -> None:
    """Test that readings of quantities the station does not show are dropped."""
    selected = select(
        [{Quantity.LEVEL: reading(1.0, TWO), Quantity.WIND_SPEED: reading(3.0, TWO)}],
        {},
        [Quantity.LEVEL],
        NOW,
    )

    assert list(selected) == [Quantity.LEVEL]


@pytest.mark.parametrize(
    ("thresholds", "level", "status"),
    [
        (Thresholds(2.3, 3.0, 3.8), 0.86, LevelStatus.NORMAL),
        (Thresholds(2.3, 3.0, 3.8), 2.3, LevelStatus.PRE_ALARM),
        (Thresholds(2.3, 3.0, 3.8), 3.1, LevelStatus.GUARD),
        (Thresholds(2.3, 3.0, 3.8), 3.8, LevelStatus.DANGER),
        (Thresholds(None, None, 3.8), 3.1, LevelStatus.NORMAL),
        (Thresholds(), 3.1, None),
    ],
)
def test_level_status(
    thresholds: Thresholds, level: float, status: LevelStatus | None
) -> None:
    """Test the level against the thresholds, some of them missing."""
    assert thresholds.status(level) is status


def test_thresholds_as_entry_data() -> None:
    """Test that the thresholds are stored and read back."""
    thresholds = Thresholds(2.3, None, 3.8)

    assert Thresholds.from_dict(thresholds.as_dict()) == thresholds
    assert Thresholds.from_dict(None) == Thresholds()


def test_snapshot() -> None:
    """Test the slowest source, the newest time and the level status."""
    snapshot = StationSnapshot(
        {
            Quantity.LEVEL: reading(3.1, TWO),
            Quantity.RAIN_1H: reading(0.0, ONE, Source.ARPA_REALTIME),
        },
        Thresholds(2.3, 3.0, 3.8),
    )

    assert snapshot.source is Source.ARPA_REALTIME
    assert snapshot.measured_at == TWO
    assert snapshot.level_status is LevelStatus.GUARD
    empty = StationSnapshot()
    assert empty.source is None
    assert empty.measured_at is None
    assert empty.level_status is None


@pytest.mark.parametrize(
    ("letters", "quantities"),
    [
        (
            "IPT",
            (
                Quantity.LEVEL,
                Quantity.TEMPERATURE,
                Quantity.RAIN_1H,
                Quantity.RAIN_3H,
                Quantity.RAIN_24H,
            ),
        ),
        (
            "tpi",
            (
                Quantity.LEVEL,
                Quantity.TEMPERATURE,
                Quantity.RAIN_1H,
                Quantity.RAIN_3H,
                Quantity.RAIN_24H,
            ),
        ),
        ("BGR", ()),
        (
            "HNV",
            (
                Quantity.HUMIDITY,
                Quantity.WIND_SPEED,
                Quantity.WIND_DIRECTION,
                Quantity.GUST_SPEED,
                Quantity.GUST_DIRECTION,
                Quantity.SNOW_DEPTH,
            ),
        ),
    ],
)
def test_quantities_of_the_sensors(
    letters: str, quantities: tuple[Quantity, ...]
) -> None:
    """Test the quantities of a station, from the letters of its sensors."""
    station = StationConfig("188", "Pray Sessera", None, letters, Thresholds())

    assert station.quantities == quantities
    assert station.has_level is (Quantity.LEVEL in quantities)
    assert StationConfig.from_data(station.as_data()) == station


@pytest.mark.parametrize(
    ("sensor_id", "website_params", "quantities"),
    [
        # The files the website lists
        (
            "001013900",
            ("baro", "radd", "terma"),
            (Quantity.TEMPERATURE, Quantity.PRESSURE, Quantity.SOLAR_RADIATION),
        ),
        # A barometer the website does not list is dead
        (
            "001013900",
            ("radd", "terma"),
            (Quantity.TEMPERATURE, Quantity.SOLAR_RADIATION),
        ),
        # Files unknown: the letters stand in for them
        (
            "001013900",
            None,
            (Quantity.TEMPERATURE, Quantity.PRESSURE, Quantity.SOLAR_RADIATION),
        ),
        # No file on the website at all
        (None, ("baro", "radd"), (Quantity.TEMPERATURE,)),
    ],
)
def test_quantities_only_the_website_gives(
    sensor_id: str | None,
    website_params: tuple[str, ...] | None,
    quantities: tuple[Quantity, ...],
) -> None:
    """Test the pressure and the radiation, by the files of the website."""
    station = StationConfig(
        "142", "Avigliana", sensor_id, "BRT", Thresholds(), website_params
    )

    assert station.quantities == quantities
    assert StationConfig.from_data(station.as_data()) == station


def test_source_leaves_out_what_only_the_website_gives() -> None:
    """Test that the pressure, always from the website, does not hide Meteo 3R."""
    pressure = reading(970.2, ONE, Source.ARPA_WEBSITE)

    assert (
        StationSnapshot(
            {Quantity.TEMPERATURE: reading(1.3, TWO), Quantity.PRESSURE: pressure}
        ).source
        is Source.METEO3R
    )
    assert StationSnapshot({Quantity.PRESSURE: pressure}).source is None
