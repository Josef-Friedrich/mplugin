from typing import Optional

import pytest

import mplugin
from mplugin import (
    Context,
    Metric,
    Resource,
    Result,
    ScalarContext,
    ServiceState,
    _Contexts,
    critical,
    ok,
    unknown,
    warn,
)


class TestContext:
    def test_description_should_be_empty_by_default(self) -> None:
        c = Context("ctx")
        assert c.describe(mplugin.Metric("m", 0)) is None

    def test_fmt_template(self) -> None:
        m1 = Metric("foo", 1, "s", min=0)
        c = Context("describe_template", "{name} is {valueunit} (min {min})")
        assert "foo is 1s (min 0)" == c.describe(m1)

    def test_fmt_callable(self) -> None:
        def format_metric(metric: Metric, context: Context) -> str:
            return "{0} formatted by {1}".format(metric.name, context.name)

        m1 = Metric("foo", 1, "s", min=0)
        c = Context("describe_callable", fmt_metric=format_metric)
        assert "foo formatted by describe_callable" == c.describe(m1)


class MyContext(Context):
    def evaluate(self, metric: Metric, resource: Resource) -> Result | ServiceState:
        if metric.value == 3:
            return self.unknown(hint="3 is unknown", metric=metric)
        if metric.value == 2:
            return self.critical(hint="2 is critical", metric=metric)
        if metric.value == 1:
            return self.warn(hint="1 is warn", metric=metric)
        return self.ok(hint="is ok", metric=metric)


class TestSubclassesContext:
    my_context = MyContext("my_context")

    def evaluate(self, value: int) -> Result:
        result = self.my_context.evaluate(Metric(f"value {value}", value), Resource())
        assert isinstance(result, Result)
        return result

    def test_ok(self) -> None:
        result: Result = self.evaluate(0)
        assert result.state == ok
        assert result.hint == "is ok"

    def test_warn(self) -> None:
        result: Result = self.evaluate(1)
        assert result.state == warn
        assert result.hint == "1 is warn"

    def test_critical(self) -> None:
        result: Result = self.evaluate(2)
        assert result.state == critical
        assert result.hint == "2 is critical"

    def test_unknwon(self) -> None:
        result: Result = self.evaluate(3)
        assert result.state == unknown
        assert result.hint == "3 is unknown"


class TestScalarContext:
    def test_state_ranges_values(self) -> None:
        test_cases: list[tuple[int, ServiceState, Optional[str]]] = [
            (1, mplugin.ok, None),
            (3, mplugin.warn, "outside range 0:2"),
            (5, mplugin.critical, "outside range 0:4"),
        ]
        c = ScalarContext("ctx", "0:2", "0:4")
        for value, exp_state, exp_reason in test_cases:
            m = mplugin.Metric("time", value)
            assert mplugin.Result(exp_state, exp_reason, m) == c.evaluate(m, Resource())

    def test_accept_none_warning_critical(self) -> None:
        c = ScalarContext("ctx")
        assert mplugin.Range() == c.warn_range
        assert mplugin.Range() == c.critical_range


class TestContexts:
    def test_keyerror(self) -> None:
        ctx = _Contexts()
        ctx.add(Context("foo"))
        with pytest.raises(KeyError):
            ctx["bar"]

    def test_contains(self) -> None:
        ctx = _Contexts()
        ctx.add(Context("foo"))
        assert "foo" in ctx
        assert "bar" not in ctx

    def test_iter(self) -> None:
        ctx = _Contexts()
        ctx.add(Context("foo"))
        # includes default contexts
        assert ["default", "foo", "null"] == sorted(list(ctx))
