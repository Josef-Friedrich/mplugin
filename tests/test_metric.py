import pytest

from mplugin import Context, Metric, Resource, Result, ScalarContext, ok


class TestConstructor:
    def test_metric_boolean_value(self) -> None:
        m = Metric("up", True)
        assert m.value is True
        assert str(m) == "True"

    def test_metric_with_all_parameters(self) -> None:
        ctx = Context("full_test")
        r = Resource()
        m = Metric(
            "comprehensive",
            99.5,
            uom="ms",
            min=0,
            max=1000,
            context=ctx,
            resource=r,
        )
        assert m.name == "comprehensive"
        assert m.value == 99.5
        assert m.uom == "ms"
        assert m.min == 0
        assert m.max == 1000
        assert m.context_name == "full_test"
        assert m.resource == r


class TestValueUnit:
    def test_valueunit_float(self) -> None:
        assert "1.302s" == Metric("time", 1.30234876, "s").valueunit

    def test_valueunit_scientific(self) -> None:
        assert "1.3e+04s" == Metric("time", 13000.0, "s").valueunit

    def test_valueunit_should_not_use_scientific_for_large_ints(self) -> None:
        assert "13000s" == Metric("time", 13000, "s").valueunit

    def test_valueunit_nonfloat(self) -> None:
        assert "text" == Metric("text", "text").valueunit

    def test_metric_valueunit_property(self) -> None:
        m = Metric("swap", 512, uom="MB")
        assert m.valueunit == "512MB"

    def test_metric_valueunit_without_uom(self) -> None:
        m = Metric("count", 42)
        assert m.valueunit == "42"


class TestMetric2:
    def test_metric_creation_minimal(self) -> None:
        m = Metric("test", 42)
        assert m.name == "test"
        assert m.value == 42
        assert m.uom is None
        assert m.min is None
        assert m.max is None
        assert m.context_name == "test"

    def test_metric_creation_with_uom(self) -> None:
        m = Metric("memory", 1024, uom="B")
        assert m.name == "memory"
        assert m.value == 1024
        assert m.uom == "B"

    def test_metric_creation_with_min_max(self) -> None:
        m = Metric("cpu", 75.5, min=0, max=100)
        assert m.min == 0
        assert m.max == 100

    def test_metric_str_representation(self) -> None:
        m = Metric("temp", 98.6, uom="°C")
        assert str(m) == "98.6°C"

    def test_metric_human_readable_float(self) -> None:
        m = Metric("rate", 0.123456789)
        assert m.valueunit == "0.1235"

    def test_metric_human_readable_int(self) -> None:
        m = Metric("count", 12345)
        assert m.valueunit == "12345"


class TestDescription:
    def test_description(self) -> None:
        assert (
            "time is 1s"
            == Metric("time", 1, "s", context=ScalarContext("ctx")).description
        )

    def test_without_context(self) -> None:
        m = Metric("test", 42)
        assert m.description == "42"

    def test_with_context(self) -> None:
        ctx = Context("test", fmt_metric="Value: {value}")
        m = Metric("test", 42, context=ctx)
        assert m.description == "Value: 42"


class TestContext:
    def test_metric_context_raises_without_assignment(self) -> None:
        m = Metric("test", 1)
        with pytest.raises(RuntimeError):
            _ = m.context

    def test_evaluate_fails_if_no_context(self) -> None:
        with pytest.raises(RuntimeError):
            Metric("time", 1, "s").evaluate()

    def test_performance_fails_if_no_context(self) -> None:
        with pytest.raises(RuntimeError):
            Metric("time", 1, "s").performance()

    def test_metric_evaluate_with_context(self) -> None:
        ctx = Context("test_metric")
        m = Metric("test_metric", 1, context=ctx)
        m.resource = Resource()
        result = m.evaluate()
        assert isinstance(result, Result)
        assert result.state == ok

    def test_performance_no_context_set(self) -> None:
        m = Metric("test", 1, resource=Resource(), context=Context("test"))
        perfs = m.performance()
        assert perfs == []

    def test_performance_with_context(self) -> None:
        ctx = Context("perf_test")
        m = Metric("perf_test", 50, uom="percent")
        m.context = ctx
        m.resource = Resource()
        perfs = m.performance()
        assert perfs == []

    def test_from_string(self) -> None:
        m = Metric("foo", 1, context="custom_ctx")
        assert m.context_name == "custom_ctx"

    def test_from_context_object(self) -> None:
        ctx = Context("my_context")
        m = Metric("bar", 2, context=ctx)
        assert m.context_name == "my_context"
        assert m._Metric__context == ctx  # type: ignore

    def test_setter_getter(self) -> None:
        ctx = Context("ctx")
        m = Metric("test", 1)
        m.context = ctx
        assert m.context == ctx


class TestResource:
    def test_raises_without_assignment(self) -> None:
        m = Metric("test", 1)
        with pytest.raises(RuntimeError):
            _ = m.resource

    def test_setter_getter(self) -> None:
        r = Resource()
        m = Metric("test", 1)
        m.resource = r
        assert m.resource == r
