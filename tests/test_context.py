import pytest

import mplugin
from mplugin.context import Context, Contexts, ScalarContext


class TestContext:
    def test_description_should_be_empty_by_default(self) -> None:
        c = Context("ctx")
        assert c.describe(mplugin.Metric("m", 0)) is None

    def test_fmt_template(self) -> None:
        m1 = mplugin.Metric("foo", 1, "s", min=0)
        c = Context("describe_template", "{name} is {valueunit} (min {min})")
        assert "foo is 1s (min 0)" == c.describe(m1)

    def test_fmt_callable(self) -> None:
        def format_metric(metric, context) -> str:
            return "{0} formatted by {1}".format(metric.name, context.name)

        m1 = mplugin.Metric("foo", 1, "s", min=0)
        c = Context("describe_callable", fmt_metric=format_metric)
        assert "foo formatted by describe_callable" == c.describe(m1)


class TestScalarContext:
    def test_state_ranges_values(self) -> None:
        test_cases = [
            (1, mplugin.ok, None),
            (3, mplugin.warn, "outside range 0:2"),
            (5, mplugin.critical, "outside range 0:4"),
        ]
        c = ScalarContext("ctx", "0:2", "0:4")
        for value, exp_state, exp_reason in test_cases:
            m = mplugin.Metric("time", value)
            assert mplugin.Result(exp_state, exp_reason, m) == c.evaluate(m, None)

    def test_accept_none_warning_critical(self) -> None:
        c = ScalarContext("ctx")
        assert mplugin.Range() == c.warning
        assert mplugin.Range() == c.critical


class TestContexts:
    def test_keyerror(self) -> None:
        ctx = Contexts()
        ctx.add(Context("foo"))
        with pytest.raises(KeyError):
            ctx["bar"]

    def test_contains(self) -> None:
        ctx = Contexts()
        ctx.add(Context("foo"))
        assert "foo" in ctx
        assert "bar" not in ctx

    def test_iter(self) -> None:
        ctx = Contexts()
        ctx.add(Context("foo"))
        # includes default contexts
        assert ["default", "foo", "null"] == sorted(list(ctx))
