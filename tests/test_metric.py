# -*- coding: utf-8 -*-
import pytest

import monitoringplugin
from monitoringplugin.metric import Metric


class TestMetric:
    def test_description(self):
        assert (
            "time is 1s"
            == Metric(
                "time", 1, "s", contextobj=monitoringplugin.ScalarContext("ctx")
            ).description
        )

    def test_valueunit_float(self):
        assert "1.302s" == Metric("time", 1.30234876, "s").valueunit

    def test_valueunit_scientific(self):
        assert "1.3e+04s" == Metric("time", 13000.0, "s").valueunit

    def test_valueunit_should_not_use_scientific_for_large_ints(self):
        assert "13000s" == Metric("time", 13000, "s").valueunit

    def test_valueunit_nonfloat(self):
        assert "text" == Metric("text", "text").valueunit

    def test_evaluate_fails_if_no_context(self):
        with pytest.raises(RuntimeError):
            Metric("time", 1, "s").evaluate()

    def test_performance_fails_if_no_context(self):
        with pytest.raises(RuntimeError):
            Metric("time", 1, "s").performance()
