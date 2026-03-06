import pytest

from mplugin import Performance


def test_normal_label() -> None:
    assert "d=10" == str(Performance("d", 10))


def test_label_quoted() -> None:
    assert "'d d'=10" == str(Performance("d d", 10))


def test_label_must_not_contain_quotes() -> None:
    with pytest.raises(RuntimeError):
        str(Performance("d'", 10))


def test_label_must_not_contain_equals() -> None:
    with pytest.raises(RuntimeError):
        str(Performance("d=", 10))


def test_uom() -> None:
    assert "d=10B" == str(Performance("d", 10, "B"))


def test_warn() -> None:
    assert "d=10;5:10" == str(Performance("d", 10, warn="5:10"))


def test_crit() -> None:
    assert "d=10;;10:20" == str(Performance("d", 10, crit="10:20"))


def test_min() -> None:
    assert "d=10;;;0" == str(Performance("d", 10, min=0))


def test_max() -> None:
    assert "d=10;;;;100" == str(Performance("d", 10, max=100))


def test_uom_and_warn() -> None:
    assert "d=10B;5:10" == str(Performance("d", 10, "B", warn="5:10"))


def test_all_parameters() -> None:
    assert "d=10B;5:10;10:20;0;100" == str(
        Performance("d", 10, "B", warn="5:10", crit="10:20", min=0, max=100)
    )


def test_empty_warn_range() -> None:
    assert "d=10" == str(Performance("d", 10, warn=""))


def test_empty_crit_range() -> None:
    assert "d=10" == str(Performance("d", 10, crit=""))


def test_float_value() -> None:
    assert "d=10.5" == str(Performance("d", 10.5))


def test_boolean_value() -> None:
    assert "d=True" == str(Performance("d", True))


def test_label_with_spaces_gets_quoted() -> None:
    assert "'my metric'=10" == str(Performance("my metric", 10))


def test_label_with_special_chars_gets_quoted() -> None:
    assert "'d-metric'=10" == str(Performance("d-metric", 10))
