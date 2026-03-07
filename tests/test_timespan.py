"""Test the subpackage timespan.py"""

import argparse
from datetime import datetime

import pytest

from mplugin.timespan import Timespan
from mplugin.timespan import convert_timespan_to_sec as convert


class TestConvertTimespanToSec:
    def test_int(self) -> None:
        """Test conversion of seconds."""
        assert convert(5) == 5

    def test_float(self) -> None:
        """Test conversion of seconds."""
        assert convert(5.5) == 5.5

    def test_float_as_string(self) -> None:
        """Test conversion of seconds."""
        assert convert("5.5") == 5.5

    def test_microseconds(self) -> None:
        """Test conversion of microseconds."""
        assert convert("1μs") == 0.000001
        assert convert("1.2usec") == 0.0000012

    def test_milliseconds(self) -> None:
        """Test conversion of milliseconds."""
        assert convert("1msec") == 0.001
        assert convert("1.2345ms") == 0.0012345

    def test_seconds(self) -> None:
        """Test conversion of seconds."""
        assert convert("5s") == 5
        assert convert("45.5s") == 45.5

    def test_minutes(self) -> None:
        """Test conversion of minutes."""
        assert convert("1m") == 60
        assert convert("2min") == 120
        assert convert("3minutes") == 180

    def test_hours(self) -> None:
        """Test conversion of hours."""
        assert convert("1h") == 3600
        assert convert("2hr") == 7200
        assert convert("3 hours") == 10800

    def test_days(self) -> None:
        """Test conversion of days."""
        assert convert("1d") == 86400
        assert convert("2days") == 172800

    def test_weeks(self) -> None:
        """Test conversion of weeks."""
        assert convert("1w") == 604800
        assert convert("2weeks") == 1209600

    def test_months(self) -> None:
        """Test conversion of months."""
        assert convert("1M") == 2630016
        assert convert("2months") == 5260032

    def test_years(self) -> None:
        """Test conversion of years."""
        assert convert("1y") == 31557600
        assert convert("2years") == 63115200

    def test_combined_timespan(self) -> None:
        """Test conversion of combined timespans."""
        assert convert("1h30m") == 5400
        assert convert("2 months 8 days") == 5951232
        assert convert("3min 45.234s") == 225.234

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is properly handled."""
        assert convert("5 s") == 5
        assert convert("  10  minutes  ") == 600

    def test_decimal_values(self) -> None:
        """Test conversion with decimal values."""
        assert convert("1.5h") == 5400
        assert convert("2.5d") == 216000


parser = argparse.ArgumentParser()
parser.add_argument("--timeout", type=convert)


class TestConvertAsArgparserType:
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


class TestClassTimespan:
    class TestTimespanInit:
        def test_init_with_none_values(self) -> None:
            ts = Timespan(None, None)
            assert isinstance(ts.start, datetime)
            assert isinstance(ts.end, datetime)

        def test_init_with_int_timestamp(self) -> None:
            ts = Timespan(1000, 2000)
            assert ts.start == datetime.fromtimestamp(1000)
            assert ts.end == datetime.fromtimestamp(2000)

        def test_init_with_float_timestamp(self) -> None:
            ts = Timespan(1000.5, 2000.5)
            assert ts.start == datetime.fromtimestamp(1000.5)
            assert ts.end == datetime.fromtimestamp(2000.5)

        def test_init_with_datetime_objects(self) -> None:
            dt1 = datetime(2020, 1, 1, 12, 0, 0)
            dt2 = datetime(2020, 1, 2, 12, 0, 0)
            ts = Timespan(dt1, dt2)
            assert ts.start == dt1
            assert ts.end == dt2

        def test_init_with_none_end(self) -> None:
            ts = Timespan(1000, None)
            assert ts.start == datetime.fromtimestamp(1000)
            assert isinstance(ts.end, datetime)

    class TestTimespan:
        def test_timespan_calculation(self) -> None:
            ts = Timespan(1000, 2000)
            assert ts.timespan == 1000.0

        def test_timespan_with_datetime(self) -> None:
            dt1 = datetime(2020, 1, 1, 12, 0, 0)
            dt2 = datetime(2020, 1, 1, 13, 0, 0)
            ts = Timespan(dt1, dt2)
            assert ts.timespan == 3600.0

    class TestTimespanComparison:
        ts = Timespan(1000, 2000)
        # 1000

        def test_timespan(self) -> None:
            assert self.ts.timespan == 1000.0

        def test_lt(self) -> None:
            assert self.ts < 1500
            assert not (self.ts < 500)

        def test_le(self) -> None:
            assert self.ts <= 1000
            assert self.ts <= 1500
            assert not (self.ts <= 500)

        def test_eq_true(self) -> None:
            assert self.ts == 1000
            assert not (self.ts == 500)

        def test_ne_true(self) -> None:
            assert self.ts != 500
            assert not (self.ts != 1000)

        def test_ge_true(self) -> None:
            assert self.ts >= 1000
            assert self.ts >= 500
            assert not (self.ts >= 1500)

        def test_gt_true(self) -> None:
            assert self.ts > 500
            assert not (self.ts > 1000)

        def test_comparison_with_invalid_type(self) -> None:
            ts = Timespan(1000, 2000)
            with pytest.raises(ValueError):
                ts < "string"  # type: ignore

    class TestTimespanConversions:
        def test_float(self) -> None:
            ts = Timespan(1000, 2500)
            assert float(ts) == 1500.0

        def test_int(self) -> None:
            ts = Timespan(1000, 2500)
            assert int(ts) == 1500

        def test_int_rounding(self) -> None:
            ts = Timespan(1000, 2600)
            assert isinstance(int(ts), int)

        def test_str(self) -> None:
            ts = Timespan(1000, 2600)
            assert str(ts) == "1970-01-01T01:16:40 - 1970-01-01T01:43:20"
