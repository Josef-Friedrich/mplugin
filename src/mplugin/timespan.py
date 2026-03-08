"""
Offers classes and functions to make it easier and more efficient to work with time spans.
"""

import re
from datetime import datetime
from typing import Any, Optional, Union

DateTimeSpec = Optional[Union[int, float, datetime]]


def convert_timespan_to_sec(spec: Union[str, int, float]) -> float:
    """Convert a timespan format string to seconds.
    If no time unit is specified, generally seconds are assumed.

    The following time units are understood:

    - ``years``, ``year``, ``y`` (defined as ``365.25`` days)
    - ``months``, ``month``, ``M`` (defined as ``30.44`` days)
    - ``weeks``, ``week``, ``w``
    - ``days``, ``day``, ``d``
    - ``hours``, ``hour``, ``hr``, ``h``
    - ``minutes``, ``minute``, ``min``, ``m``
    - ``seconds``, ``second``, ``sec``, ``s``
    - ``milliseconds``, ``millisecond``, ``msec``, ``ms``
    - ``microseconds``,  ``microsecond``, ``usec``, ``μs``, ``μ``, ``us``

    This function can be used as type in the
    :py:meth:`argparse.ArgumentParser.add_argument` method.

    .. code-block:: python

        parser.add_argument(
            "-c",
            "--critical",
            default=5356800,
            help="Interval in seconds for critical state.",
            type=timespan,
        )

    :param spec: The specification of the timespan as a string, for example
      ``2.345s``, ``3min 45.234s``, ``34min``, ``2 months 8 days`` or as a
      number.

    :return: The timespan in seconds
    """

    # A int or a float encoded as string without an extension
    try:
        spec = float(spec)
    except ValueError:
        pass

    if isinstance(spec, int) or isinstance(spec, float):
        return spec

    # Remove all whitespaces
    spec = re.sub(r"\s+", "", spec)

    replacements: list[tuple[list[str], str]] = [
        (["years", "year"], "y"),
        (["months", "month"], "M"),
        (["weeks", "week"], "w"),
        (["days", "day"], "d"),
        (["hours", "hour", "hr"], "h"),
        (["minutes", "minute", "min"], "m"),
        (["seconds", "second", "sec"], "s"),
        (["milliseconds", "millisecond", "msec"], "ms"),
        (["microseconds", "microsecond", "usec", "μs", "μ"], "us"),
    ]

    for replacement in replacements:
        for r in replacement[0]:
            spec = spec.replace(r, replacement[1])

    # Add a whitespace after the units
    spec = re.sub(r"([a-zA-Z]+)", r"\1 ", spec)

    seconds: dict[str, float] = {
        "y": 31557600,  # 365.25 days
        "M": 2630016,  # 30.44 days
        "w": 604800,  # 7 * 24 * 60 * 60
        "d": 86400,  # 24 * 60 * 60
        "h": 3600,  # 60 * 60
        "m": 60,
        "s": 1,
        "ms": 0.001,
        "us": 0.000001,
    }
    result: float = 0
    # Split on the whitespaces
    for span in spec.split():
        match = re.search(r"([\d\.]+)([a-zA-Z]+)", span)
        if match:
            value = match.group(1)
            unit = match.group(2)
            result += float(value) * seconds[unit]
    return result


TIMESPAN_FORMAT_HELP = """
Timespan format
---------------

If no time unit is specified, generally seconds are assumed. The following time
units are understood:

- years, year, y (defined as 365.25 days)
- months, month, M (defined as 30.44 days)
- weeks, week, w
- days, day, d
- hours, hour, hr, h
- minutes, minute, min, m
- seconds, second, sec, s
- milliseconds, millisecond, msec, ms
- microseconds,  microsecond, usec, μs, μ, us

The following are valid examples of timespan specifications:

- 1
- 1.23
- 2.345s
- 3min 45.234s
- 34min
- 2 months 8 days
- 1h30m
"""
"""This string can be included in the Command Line Interface help text."""


class Timespan:
    """
    A class to represent a time interval between two datetime objects.

    The Timespan class manages a time period defined by a start and end datetime.
    It supports multiple ways to initialize the timespan, including explicit start/end
    times or a duration from the current moment.

    :param start: The start datetime. Can be a datetime object, Unix
        timestamp (int/float), or None to use current time. Default is None.
    :param end: The end datetime. Can be a datetime object, Unix timestamp
        (int/float), or None to use current time. Default is None.
    :param timespan_from_now: Duration in seconds from the current moment
        to define the timespan. If specified, end is set to now and start
        is calculated backwards. Cannot be used together with start or end
        parameters. Default is None.

    :raises ValueError: If both ``start/end`` and ``timespan_from_now``
        parameters are specified.

    Examples
    --------
    Create a timespan from explicit start and end times::

        ts = Timespan(start=datetime(2024, 1, 1), end=datetime(2024, 1, 2))

    Create a timespan for the last hour::

        ts = Timespan(timespan_from_now=3600)

    Compare timespans with numeric values::

        if ts > 3600:  # more than 1 hour
            print("Long timespan")

    Convert to different types::

        duration_seconds = float(ts)
        duration_rounded = int(ts)
    """

    start: datetime
    """The beginning of the timespan."""

    end: datetime
    """The end of the timespan."""

    def __init__(
        self,
        start: DateTimeSpec = None,
        end: DateTimeSpec = None,
        timespan_from_now: Optional[Union[int, float]] = None,
    ) -> None:
        """ """
        if not (start is None and end is None) and timespan_from_now is not None:
            raise ValueError("specify start or end OR timespan_from_now")

        if timespan_from_now is None:
            self.start = Timespan.__normalize(start)
            self.end = Timespan.__normalize(end)
        else:
            self.end = Timespan.__normalize()
            self.start = Timespan.__normalize(self.end.timestamp() - timespan_from_now)

    @property
    def timespan(self) -> float:
        """The duration of the timespan in seconds."""
        return self.end.timestamp() - self.start.timestamp()

    @staticmethod
    def __normalize(date: DateTimeSpec = None) -> datetime:
        if date is None:
            return datetime.now()
        if isinstance(date, int) or isinstance(date, float):
            return datetime.fromtimestamp(date)
        return date

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float):
            return self.timespan < other
        raise ValueError("Unsupported type for __lt__")

    def __le__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float):
            return self.timespan <= other
        raise ValueError("Unsupported type for __le__")

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float):
            return self.timespan == other
        raise ValueError("Unsupported type for __eq__")

    def __ne__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float):
            return self.timespan != other
        raise ValueError("Unsupported type for __ne__")

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float):
            return self.timespan >= other
        raise ValueError("Unsupported type for __ge__")

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float):
            return self.timespan > other
        raise ValueError("Unsupported type for __gt__")

    def __float__(self) -> float:
        return self.timespan

    def __int__(self) -> int:
        return round(self.timespan)

    def __str__(self) -> str:
        return f"{self.start.isoformat()} - {self.end.isoformat()}"
