"""Test the function convert_timespan_to_seconds"""

import argparse

from mplugin import convert_timespan_to_seconds as convert  # type: ignore


def test_int() -> None:
    """Test conversion of seconds."""
    assert convert(5) == 5


def test_float() -> None:
    """Test conversion of seconds."""
    assert convert(5.5) == 5.5


def test_float_as_string() -> None:
    """Test conversion of seconds."""
    assert convert("5.5") == 5.5


def test_microseconds() -> None:
    """Test conversion of microseconds."""
    assert convert("1μs") == 0.000001
    assert convert("1.2usec") == 0.0000012


def test_milliseconds() -> None:
    """Test conversion of milliseconds."""
    assert convert("1msec") == 0.001
    assert convert("1.2345ms") == 0.0012345


def test_seconds() -> None:
    """Test conversion of seconds."""
    assert convert("5s") == 5
    assert convert("45.5s") == 45.5


def test_minutes() -> None:
    """Test conversion of minutes."""
    assert convert("1m") == 60
    assert convert("2min") == 120
    assert convert("3minutes") == 180


def test_hours() -> None:
    """Test conversion of hours."""
    assert convert("1h") == 3600
    assert convert("2hr") == 7200
    assert convert("3 hours") == 10800


def test_days() -> None:
    """Test conversion of days."""
    assert convert("1d") == 86400
    assert convert("2days") == 172800


def test_weeks() -> None:
    """Test conversion of weeks."""
    assert convert("1w") == 604800
    assert convert("2weeks") == 1209600


def test_months() -> None:
    """Test conversion of months."""
    assert convert("1M") == 2630016
    assert convert("2months") == 5260032


def test_years() -> None:
    """Test conversion of years."""
    assert convert("1y") == 31557600
    assert convert("2years") == 63115200


def test_combined_timespan() -> None:
    """Test conversion of combined timespans."""
    assert convert("1h30m") == 5400
    assert convert("2 months 8 days") == 5951232
    assert convert("3min 45.234s") == 225.234


def test_whitespace_handling() -> None:
    """Test that whitespace is properly handled."""
    assert convert("5 s") == 5
    assert convert("  10  minutes  ") == 600


def test_decimal_values() -> None:
    """Test conversion with decimal values."""
    assert convert("1.5h") == 5400
    assert convert("2.5d") == 216000


parser = argparse.ArgumentParser()
parser.add_argument("--timeout", type=convert)


class TestAsArgparserType:
    def test_seconds(self) -> None:
        """Test TimeSpanAction with seconds."""

        args = parser.parse_args(["--timeout", "5s"])
        assert args.timeout == 5

    def test_minutes(self) -> None:
        """Test TimeSpanAction with minutes."""
        args = parser.parse_args(["--timeout", "2min"])
        assert args.timeout == 120

    def test_hours(self) -> None:
        """Test TimeSpanAction with hours."""
        args = parser.parse_args(["--timeout", "1h"])
        assert args.timeout == 3600

    def test_combined(self) -> None:
        """Test TimeSpanAction with combined timespan."""
        args = parser.parse_args(["--timeout", "1h30m"])
        assert args.timeout == 5400

    def test_float(self) -> None:
        """Test TimeSpanAction with float value."""
        args = parser.parse_args(["--timeout", "1.5h"])
        assert args.timeout == 5400

    def test_with_spaces(self) -> None:
        """Test TimeSpanAction with spaces."""
        args = parser.parse_args(["--timeout", "2 hours 30 minutes"])
        assert args.timeout == 9000
