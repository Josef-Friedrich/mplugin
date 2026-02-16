import pytest

from monitoringplugin.performance import Performance


class TestPerformance:
    def test_normal_label(self):
        assert "d=10" == str(Performance("d", 10))

    def test_label_quoted(self):
        assert "'d d'=10" == str(Performance("d d", 10))

    def test_label_must_not_contain_quotes(self):
        with pytest.raises(RuntimeError):
            str(Performance("d'", 10))

    def test_label_must_not_contain_equals(self):
        with pytest.raises(RuntimeError):
            str(Performance("d=", 10))
