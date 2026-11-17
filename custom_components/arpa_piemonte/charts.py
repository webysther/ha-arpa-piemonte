"""Charts of the recent readings of a station, drawn as SVG (pure).

As the charts of the Arpa website: the level with its thresholds, the rain of
each hour with its total, temperature, humidity, snow, wind, pressure and
solar radiation. They carry no words, only units and values, so they read the
same in every language, and their colours read on a light or a dark
background.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from itertools import accumulate, pairwise
import math
from typing import Final
from xml.sax.saxutils import escape

from .models import Reading, Series, Thresholds

WIDTH: Final = 640
"""Width of the drawing, in SVG units; it scales to the card."""
HEIGHT: Final = 240
"""Height of the drawing, in SVG units."""
LEFT: Final = 48
"""Room on the left of the plot, for the values of the axis."""
RIGHT: Final = 52
"""Room on the right of the plot, for the thresholds or the total of rain."""
TOP: Final = 22
"""Room above the plot, for the units."""
BOTTOM: Final = 28
"""Room under the plot, for the days and hours."""
FONT_SIZE: Final = 11
FLAT_SPAN: Final = 1.0
"""Span of an axis whose values are all the same: 0 to 1 mm without rain."""

GAP: Final = timedelta(minutes=90)
"""A step longer than this misses readings, and the line breaks there.

Meteo 3R gives a reading every 30 minutes, the gusts every hour, and leaves
out the readings it has not; the files of the website give one every hour
(measured on 2026-11-17).
"""
HOUR: Final = timedelta(hours=1)
"""What a rain bar covers: the hour that ends at its time."""
HOURS_BETWEEN_TICKS: Final = 6
"""Hours between two ticks of the time axis: 4 a day."""
VALUE_TICKS: Final = 5
"""About how many values the vertical axis shows."""

# Colours that read on a light and on a dark background
LEVEL_COLOR: Final = "#1e88e5"
RAIN_COLOR: Final = "#64b5f6"
RAIN_TOTAL_COLOR: Final = "#26a69a"
TEMPERATURE_COLOR: Final = "#ef6c00"
FREEZING_COLOR: Final = "#4fc3f7"
HUMIDITY_COLOR: Final = "#29b6f6"
SNOW_COLOR: Final = "#7e57c2"
WIND_COLOR: Final = "#43a047"
GUST_COLOR: Final = "#8e24aa"
PRESSURE_COLOR: Final = "#5c6bc0"
RADIATION_COLOR: Final = "#f9a825"
PRE_ALARM_COLOR: Final = "#e6b800"
"""The yellow of the pre-alarm threshold, as on the charts of Arpa."""
GUARD_COLOR: Final = "#f08c00"
"""The orange of the guard threshold."""
DANGER_COLOR: Final = "#e03131"
"""The red of the danger threshold."""

STYLE: Final = (
    "text{fill:#888}.grid{stroke:#888;stroke-opacity:.25}"
    "@media (prefers-color-scheme:light){text{fill:#555}}"
    "@media (prefers-color-scheme:dark){text{fill:#bbb}}"
)
"""Grey text, darker on a light background and lighter on a dark one when the
viewer says which."""


@dataclass(frozen=True, slots=True)
class Line:
    """A series drawn as a line, or as dots."""

    readings: Series
    color: str
    dots: bool = False


@dataclass(frozen=True, slots=True)
class Rule:
    """A value drawn across the chart, such as a threshold."""

    value: float
    color: str
    label: str


@dataclass(frozen=True, slots=True)
class Chart:
    """What a chart shows, before it is drawn."""

    unit: str
    lines: tuple[Line, ...] = ()
    bars: Series = ()
    """Totals of the hour that ends at their time, drawn as bars."""
    rules: tuple[Rule, ...] = ()
    floor: float | None = None
    """The lowest value of the axis, when the quantity has one (0 mm)."""
    ceiling: float | None = None
    """The highest value of the axis, when the quantity has one (100 %)."""
    total: Series = ()
    """A running total of the bars, drawn as a line on its own axis."""
    total_unit: str = ""

    @property
    def start(self) -> datetime:
        """Return the time where the chart starts: a bar starts an hour early."""
        return min(
            [
                *(line.readings[0].time for line in self.lines),
                *(reading.time - HOUR for reading in self.bars[:1]),
            ]
        )

    @property
    def end(self) -> datetime:
        """Return the time of the newest reading: the chart changes with it."""
        return max(
            [
                *(line.readings[-1].time for line in self.lines),
                *(reading.time for reading in self.bars[-1:]),
            ]
        )

    @property
    def values(self) -> list[float]:
        """Return every value of the left axis, rules included."""
        values = [reading.value for line in self.lines for reading in line.readings]
        values.extend(reading.value for reading in self.bars)
        values.extend(rule.value for rule in self.rules)
        return values


def level_chart(readings: Series, thresholds: Thresholds | None) -> Chart | None:
    """Return the chart of the level, with its thresholds; None without readings."""
    if not readings:
        return None
    rules = []
    if thresholds is not None:
        for value, color in (
            (thresholds.pre_alarm, PRE_ALARM_COLOR),
            (thresholds.guard, GUARD_COLOR),
            (thresholds.danger, DANGER_COLOR),
        ):
            if value is not None:
                rules.append(Rule(value, color, f"{_number(value)} m"))
    return Chart("m", lines=(Line(readings, LEVEL_COLOR),), rules=tuple(rules))


def rain_chart(readings: Series) -> Chart | None:
    """Return the chart of the rain of each hour and its total; None without any.

    The rain of 1 hour of Meteo 3R is given every 30 minutes over the last
    60: only the readings on the hour are hours of their own, which add up to
    the rain of 3 and 24 hours (measured on 2026-11-17).
    """
    hours = tuple(reading for reading in readings if reading.time.minute == 0)
    if not hours:
        return None
    totals = accumulate(reading.value for reading in hours)
    total = (
        Reading(hours[0].time - HOUR, 0.0),
        *(Reading(hour.time, value) for hour, value in zip(hours, totals, strict=True)),
    )
    return Chart("mm", bars=hours, floor=0.0, total=total, total_unit="Σ mm")


def temperature_chart(readings: Series) -> Chart | None:
    """Return the chart of the temperature, with 0 °C when the axis reaches it."""
    if not readings:
        return None
    rules: tuple[Rule, ...] = ()
    if min(reading.value for reading in readings) <= 0:
        rules = (Rule(0.0, FREEZING_COLOR, "0 °C"),)
    return Chart("°C", lines=(Line(readings, TEMPERATURE_COLOR),), rules=rules)


def humidity_chart(readings: Series) -> Chart | None:
    """Return the chart of the humidity, from 0 to 100 %."""
    if not readings:
        return None
    return Chart("%", lines=(Line(readings, HUMIDITY_COLOR),), floor=0.0, ceiling=100.0)


def snow_chart(readings: Series) -> Chart | None:
    """Return the chart of the snow depth."""
    if not readings:
        return None
    return Chart("cm", lines=(Line(readings, SNOW_COLOR),), floor=0.0)


def wind_chart(speed: Series, gust: Series) -> Chart | None:
    """Return the chart of the wind: its speed as a line, the gusts as dots."""
    lines = tuple(
        line
        for line in (Line(speed, WIND_COLOR), Line(gust, GUST_COLOR, dots=True))
        if line.readings
    )
    if not lines:
        return None
    return Chart("km/h", lines=lines, floor=0.0)


def pressure_chart(readings: Series) -> Chart | None:
    """Return the chart of the pressure at the station."""
    if not readings:
        return None
    return Chart("hPa", lines=(Line(readings, PRESSURE_COLOR),))


def radiation_chart(readings: Series) -> Chart | None:
    """Return the chart of the solar radiation, from 0 W/m²."""
    if not readings:
        return None
    return Chart("W/m²", lines=(Line(readings, RADIATION_COLOR),), floor=0.0)


def draw(chart: Chart, zone: tzinfo) -> str:
    """Return the SVG of a chart, its times in a time zone."""
    plot = _Plot(chart, zone)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" font-family="sans-serif" '
        f'font-size="{FONT_SIZE}">',
        f"<style>{STYLE}</style>",
        *plot.time_axis(),
        *plot.value_axis(),
        *plot.bars(chart.bars),
        *(plot.rule(rule) for rule in chart.rules),
        *(plot.line(line) for line in chart.lines),
        *plot.total(chart.total, chart.total_unit),
        _text(4, TOP - 8, chart.unit),
        "</svg>",
    ]
    return "".join(parts)


class _Plot:
    """The scales of a chart: times to x, values to y."""

    def __init__(self, chart: Chart, zone: tzinfo) -> None:
        self._zone = zone
        self._start = chart.start
        self._end = chart.end
        self._span = max((self._end - self._start).total_seconds(), 1.0)
        values = chart.values
        low = min(values) if chart.floor is None else min(chart.floor, *values)
        high = max(values) if chart.ceiling is None else max(chart.ceiling, *values)
        if high - low < FLAT_SPAN / 1000:
            if chart.floor is None:
                low -= FLAT_SPAN / 2
            high = low + FLAT_SPAN
        self.ticks = nice_ticks(low, high)
        self._low, self._high = self.ticks[0], self.ticks[-1]

    def x(self, moment: datetime) -> float:
        """Return the x of a time."""
        share = (moment - self._start).total_seconds() / self._span
        return LEFT + share * (WIDTH - LEFT - RIGHT)

    def y(
        self, value: float, low: float | None = None, high: float | None = None
    ) -> float:
        """Return the y of a value, on the left axis unless given another."""
        low = self._low if low is None else low
        high = self._high if high is None else high
        share = (value - low) / (high - low)
        return HEIGHT - BOTTOM - share * (HEIGHT - TOP - BOTTOM)

    def time_axis(self) -> Iterator[str]:
        """Yield the days and hours, in the time zone, as lines and labels.

        The day is under its midnight, and under the first hour when the
        chart starts later in the day.
        """
        bottom = HEIGHT - BOTTOM
        for index, moment in enumerate(_ticks(self._start, self._end, self._zone)):
            x = self.x(moment)
            local = moment.astimezone(self._zone)
            yield _line(x, TOP, x, bottom, grid=True)
            yield _text(x, bottom + 11, f"{local.hour:02d}", "middle")
            if local.hour == 0 or index == 0:
                day = f"{local.day:02d}/{local.month:02d}"
                yield _text(x, bottom + 22, day, "middle")

    def value_axis(self) -> Iterator[str]:
        """Yield the values of the left axis, as lines and labels."""
        for value in self.ticks:
            y = self.y(value)
            yield _line(LEFT, y, WIDTH - RIGHT, y, grid=True)
            yield _text(LEFT - 6, y + 4, _number(value), "end")

    def bars(self, readings: Series) -> Iterator[str]:
        """Yield a bar for each total of an hour."""
        base = self.y(self._low)
        for reading in readings:
            left = self.x(reading.time - HOUR)
            width = max(self.x(reading.time) - left - 1, 1.0)
            top = self.y(reading.value)
            yield (
                f'<rect x="{left:.1f}" y="{top:.1f}" width="{width:.1f}" '
                f'height="{base - top:.1f}" fill="{RAIN_COLOR}"/>'
            )

    def rule(self, rule: Rule) -> str:
        """Return a value drawn across the chart, with its label on the right."""
        y = self.y(rule.value)
        return (
            f'<line x1="{LEFT}" y1="{y:.1f}" x2="{WIDTH - RIGHT}" y2="{y:.1f}" '
            f'stroke="{rule.color}" stroke-width="1.5" stroke-dasharray="6 4"/>'
            + _text(WIDTH - RIGHT + 4, y + 4, rule.label, color=rule.color)
        )

    def line(
        self, line: Line, low: float | None = None, high: float | None = None
    ) -> str:
        """Return a series as a line broken where readings miss, or as dots."""
        points = [
            (self.x(reading.time), self.y(reading.value, low, high))
            for reading in line.readings
        ]
        if line.dots:
            return "".join(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="{line.color}"/>'
                for x, y in points
            )
        path = "".join(
            f"{'M' if new else 'L'}{x:.1f} {y:.1f}"
            for (x, y), new in zip(points, _breaks(line.readings), strict=True)
        )
        return (
            f'<path d="{path}" fill="none" stroke="{line.color}" stroke-width="2" '
            'stroke-linejoin="round" stroke-linecap="round"/>'
        )

    def total(self, readings: Series, unit: str) -> Iterator[str]:
        """Yield a running total on its own axis, on the right."""
        if not readings:
            return
        ticks = nice_ticks(
            0.0, max(FLAT_SPAN, *(reading.value for reading in readings))
        )
        low, high = ticks[0], ticks[-1]
        yield self.line(Line(readings, RAIN_TOTAL_COLOR), low, high)
        for value in ticks:
            y = self.y(value, low, high)
            yield _text(
                WIDTH - RIGHT + 6, y + 4, _number(value), color=RAIN_TOTAL_COLOR
            )
        yield _text(WIDTH - 4, TOP - 8, unit, "end", RAIN_TOTAL_COLOR)


def nice_ticks(low: float, high: float, count: int = VALUE_TICKS) -> list[float]:
    """Return round values from ``low`` or below to ``high`` or above.

    They are 1, 2, 2.5 or 5 apart, times a power of ten; ``high`` is above
    ``low``.
    """
    rough = (high - low) / count
    magnitude = 10 ** math.floor(math.log10(rough))
    step = next(
        factor * magnitude
        for factor in (1, 2, 2.5, 5, 10)
        if factor * magnitude >= rough
    )
    first = math.floor(low / step + 1e-9) * step
    last = math.ceil(high / step - 1e-9) * step
    return [
        round(first + index * step, 9)
        for index in range(round((last - first) / step) + 1)
    ]


def _ticks(start: datetime, end: datetime, zone: tzinfo) -> Iterator[datetime]:
    """Yield the local hours 0, 6, 12 and 18 between two times."""
    day: date = start.astimezone(zone).date()
    while True:
        for hour in range(0, 24, HOURS_BETWEEN_TICKS):
            moment = datetime.combine(day, time(hour), tzinfo=zone)
            if moment > end:
                return
            if moment >= start:
                yield moment
        day += timedelta(days=1)


def _breaks(readings: Sequence[Reading]) -> Iterable[bool]:
    """Yield whether each reading starts a new piece of line, after a gap."""
    yield True
    for previous, current in pairwise(readings):
        yield current.time - previous.time > GAP


def _number(value: float) -> str:
    """Return a value as short as it reads: 2.3, 0.25, 100."""
    return f"{round(value, 6):g}"


def _line(x1: float, y1: float, x2: float, y2: float, *, grid: bool = False) -> str:
    style = ' class="grid"' if grid else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"{style}/>'


def _text(
    x: float, y: float, content: str, anchor: str = "start", color: str | None = None
) -> str:
    fill = f' style="fill:{color}"' if color else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{fill}>'
        f"{escape(content)}</text>"
    )
