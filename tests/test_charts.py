"""Tests of the charts of a station, drawn as SVG."""

from __future__ import annotations

from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import pytest

from custom_components.arpa_piemonte.charts import (
    DANGER_COLOR,
    GUARD_COLOR,
    PRE_ALARM_COLOR,
    draw,
    humidity_chart,
    level_chart,
    nice_ticks,
    rain_chart,
    snow_chart,
    temperature_chart,
    wind_chart,
)
from custom_components.arpa_piemonte.models import Reading, Series, Thresholds

ROME = ZoneInfo("Europe/Rome")
START = datetime.fromisoformat("2026-11-15T22:00:00+00:00")
"""Midnight of 16 November in Rome."""
SVG = "{http://www.w3.org/2000/svg}"


def series(*values: float, step: timedelta = timedelta(minutes=30)) -> Series:
    """Return readings from START, one every step."""
    return tuple(
        Reading(START + index * step, value) for index, value in enumerate(values)
    )


def texts(svg: str) -> list[str]:
    """Return the texts of an SVG, which must be well formed."""
    return [element.text or "" for element in ET.fromstring(svg).iter(f"{SVG}text")]


def paths(svg: str) -> list[str]:
    """Return the outlines of the lines of an SVG."""
    return [element.get("d", "") for element in ET.fromstring(svg).iter(f"{SVG}path")]


@pytest.mark.parametrize(
    ("low", "high", "ticks"),
    [
        (0.86, 3.8, [0, 1, 2, 3, 4]),
        (0, 1.2, [0, 0.25, 0.5, 0.75, 1, 1.25]),
        (-4.7, 3.8, [-6, -4, -2, 0, 2, 4]),
        (0, 100, [0, 20, 40, 60, 80, 100]),
        (12.5, 13.1, [12.4, 12.6, 12.8, 13, 13.2]),
    ],
)
def test_nice_ticks(low: float, high: float, ticks: list[float]) -> None:
    """Test that the axis goes by round steps around the values."""
    assert nice_ticks(low, high) == ticks


def test_no_chart_without_readings() -> None:
    """Test that a chart needs readings."""
    assert level_chart((), Thresholds(2.3, 3.0, 3.8)) is None
    assert rain_chart(()) is None
    assert rain_chart((Reading(START + timedelta(minutes=30), 0.4),)) is None
    assert temperature_chart(()) is None
    assert humidity_chart(()) is None
    assert snow_chart(()) is None
    assert wind_chart((), ()) is None


def test_level_with_its_thresholds() -> None:
    """Test the level with the thresholds it has, in their colours."""
    chart = level_chart(series(0.86, 0.88, 0.87), Thresholds(2.3, None, 3.8))
    assert chart is not None

    svg = draw(chart, ROME)

    assert chart.end == START + timedelta(hours=1)
    assert {"2.3 m", "3.8 m"} <= set(texts(svg))
    assert PRE_ALARM_COLOR in svg
    assert GUARD_COLOR not in svg
    assert DANGER_COLOR in svg
    assert "m" in texts(svg)


def test_level_without_thresholds() -> None:
    """Test a level that never changes, without thresholds."""
    chart = level_chart(series(0.5, 0.5), None)
    assert chart is not None

    svg = draw(chart, ROME)

    assert chart.rules == ()
    assert len(paths(svg)) == 1


def test_rain_of_each_hour_and_its_total() -> None:
    """Test the bars of the hours on the hour, and their running total."""
    chart = rain_chart(series(1.2, 1.0, 0.8, 0.6, 0.2))
    assert chart is not None

    assert [reading.value for reading in chart.bars] == [1.2, 0.8, 0.2]
    assert [reading.value for reading in chart.total] == pytest.approx(
        [0.0, 1.2, 2.0, 2.2]
    )
    assert chart.start == START - timedelta(hours=1)
    svg = draw(chart, ROME)
    assert "Σ mm" in texts(svg)
    assert len(list(ET.fromstring(svg).iter(f"{SVG}rect"))) == 3


def test_no_rain() -> None:
    """Test an axis of 0 to 1 mm when it did not rain."""
    chart = rain_chart(series(0.0, 0.0, 0.0))
    assert chart is not None

    labels = texts(draw(chart, ROME))

    assert "0" in labels
    assert "1" in labels
    assert "-0.5" not in labels


@pytest.mark.parametrize(
    ("values", "freezing"), [((1.5, -0.5, 2.0), True), ((5.0, 7.5), False)]
)
def test_temperature(values: tuple[float, ...], freezing: bool) -> None:
    """Test the line of 0 °C, drawn when the temperature reaches it."""
    chart = temperature_chart(series(*values))
    assert chart is not None

    assert ("0 °C" in texts(draw(chart, ROME))) is freezing


def test_humidity_from_0_to_100() -> None:
    """Test that the axis of the humidity is 0 to 100 %."""
    chart = humidity_chart(series(78.0, 80.0))
    assert chart is not None

    labels = texts(draw(chart, ROME))

    assert {"0", "100", "%"} <= set(labels)


def test_snow_with_a_gap() -> None:
    """Test that the line breaks where readings miss."""
    readings = (*series(5.0, 6.0), *series(7.0, 8.0, step=timedelta(hours=3))[1:])
    chart = snow_chart(readings)
    assert chart is not None

    (outline,) = paths(draw(chart, ROME))

    assert outline.count("M") == 2


def test_wind_and_gusts() -> None:
    """Test the speed as a line and the gusts as dots, each on its own too."""
    speed = series(4.3, 5.0)
    gust = series(16.9, step=timedelta(hours=1))
    both = wind_chart(speed, gust)
    assert both is not None

    svg = draw(both, ROME)

    assert len(paths(svg)) == 1
    assert len(list(ET.fromstring(svg).iter(f"{SVG}circle"))) == 1
    only_gusts = wind_chart((), gust)
    assert only_gusts is not None
    assert len(only_gusts.lines) == 1
    assert "km/h" in texts(draw(only_gusts, ROME))


def test_time_axis_in_the_time_zone() -> None:
    """Test the days and hours of Rome, the day under the first hour too."""
    chart = temperature_chart(series(*([10.0] * 60), step=timedelta(hours=1))[3:])
    assert chart is not None

    labels = texts(draw(chart, ROME))

    # The chart starts on 16/11 at 02:00 in Rome: the first hour is 06
    assert labels[:2] == ["06", "16/11"]
    assert "17/11" in labels
    assert labels.count("00") == 2
