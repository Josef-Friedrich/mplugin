import pytest

import monitoringplugin
from monitoringplugin.context import Context, Contexts, ScalarContext


class TestContext:
    def test_description_should_be_empty_by_default(self):
        c = Context("ctx")
        assert c.describe(monitoringplugin.Metric("m", 0)) is None

    def test_fmt_template(self):
        m1 = monitoringplugin.Metric("foo", 1, "s", min=0)
        c = Context("describe_template", "{name} is {valueunit} (min {min})")
        assert "foo is 1s (min 0)" == c.describe(m1)

    def test_fmt_callable(self):
        def format_metric(metric, context):
            return "{0} formatted by {1}".format(metric.name, context.name)

        m1 = monitoringplugin.Metric("foo", 1, "s", min=0)
        c = Context("describe_callable", fmt_metric=format_metric)
        assert "foo formatted by describe_callable" == c.describe(m1)


class TestScalarContext:
    def test_state_ranges_values(self):
        test_cases = [
            (1, monitoringplugin.ok, None),
            (3, monitoringplugin.warn, "outside range 0:2"),
            (5, monitoringplugin.critical, "outside range 0:4"),
        ]
        c = ScalarContext("ctx", "0:2", "0:4")
        for value, exp_state, exp_reason in test_cases:
            m = monitoringplugin.Metric("time", value)
            assert monitoringplugin.Result(exp_state, exp_reason, m) == c.evaluate(
                m, None
            )

    def test_accept_none_warning_critical(self):
        c = ScalarContext("ctx")
        assert monitoringplugin.Range() == c.warning
        assert monitoringplugin.Range() == c.critical


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
