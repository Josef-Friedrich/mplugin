import pytest

from mplugin import Range


class TestRangeParse:
    def test_empty_range_is_zero_to_infinity(self) -> None:
        r = Range("")
        assert not r.invert
        assert r.start == 0
        assert r.end == float("inf")

    def test_null_range(self) -> None:
        assert Range() == Range("")
        assert Range() == Range(None)  # type: ignore

    def test_explicit_start_end(self) -> None:
        r = Range("0.5:4")
        assert not r.invert
        assert r.start == 0.5
        assert r.end == 4

    def test_fail_if_start_gt_end(self) -> None:
        pytest.raises(ValueError, Range, "4:3")

    def test_int(self) -> None:
        r = Range(42)
        assert not r.invert
        assert r.start == 0
        assert r.end == 42

    def test_float(self) -> None:
        r = Range(0.12)
        assert not r.invert
        assert r.start == 0
        assert r.end == 0.12

    def test_spec_with_unknown_type_should_raise(self) -> None:
        with pytest.raises(ValueError):
            Range([1, 2])  # type: ignore

    def test_omit_start(self) -> None:
        r = Range("5")
        assert not r.invert
        assert r.start == 0
        assert r.end == 5

    def test_omit_end(self) -> None:
        r = Range("7.7:")
        assert not r.invert
        assert r.start == 7.7
        assert r.end == float("inf")

    def test_start_is_neg_infinity(self) -> None:
        r = Range("~:5.5")
        assert not r.invert
        assert r.start == float("-inf")
        assert r.end == 5.5

    def test_invert(self) -> None:
        r = Range("@-9.1:2.6")
        assert r.invert
        assert r.start == -9.1
        assert r.end == 2.6

    def test_range_from_range(self) -> None:
        orig = Range("@3:5")
        copy = Range(orig)
        assert copy == orig

    def test_contains(self) -> None:
        r = Range("1.7:2.5")
        assert 1.6 not in r
        assert 1.7 in r
        assert 2.5 in r
        assert 2.6 not in r

    def test_repr(self) -> None:
        assert "Range('2:3')" == repr(Range("2:3"))


class TestRangeStr:
    def test_empty(self) -> None:
        assert "" == str(Range())

    def test_explicit_start_stop(self) -> None:
        assert "1.5:5" == str(Range("1.5:5"))

    def test_omit_start(self) -> None:
        assert "6.7" == str(Range("6.7"))

    def test_omit_end(self) -> None:
        assert "-6.5:" == str(Range("-6.5:"))

    def test_neg_infinity(self) -> None:
        assert "~:-3.0" == str(Range("~:-3.0"))

    def test_invert(self) -> None:
        assert "@3:7" == str(Range("@3:7"))

    def test_large_number(self) -> None:
        assert "2800000000" == str(Range("2800000000"))

    def test_violation_outside(self) -> None:
        assert "outside range 2:3" == Range("2:3").violation

    def test_violation_greater_than(self) -> None:
        assert "outside range 0:4" == Range("4").violation

    def test_violation_empty_range(self) -> None:
        assert "outside range 0:" == Range("").violation
