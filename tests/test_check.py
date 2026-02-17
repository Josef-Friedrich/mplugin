import pytest

import monitoringplugin
from monitoringplugin.check import Check


class FakeSummary(monitoringplugin.Summary):
    def ok(self, results):
        return "I'm feelin' good"

    def problem(self, results):
        return "Houston, we have a problem"


class R1_MetricDefaultContext(monitoringplugin.Resource):
    def probe(self):
        return [monitoringplugin.Metric("foo", 1, context="default")]


class TestCheck:
    def test_add_resource(self):
        c = Check()
        r1 = monitoringplugin.Resource()
        r2 = monitoringplugin.Resource()
        c.add(r1, r2)
        assert [r1, r2] == c.resources

    def test_add_context(self):
        ctx = monitoringplugin.ScalarContext("ctx1", "", "")
        c = Check(ctx)
        assert ctx.name in c.contexts

    def test_add_summary(self):
        s = monitoringplugin.Summary()
        c = Check(s)
        assert s == c.summary

    def test_add_results(self):
        r = monitoringplugin.Results()
        c = Check(r)
        assert r == c.results

    def test_add_unknown_type_should_raise_typeerror(self):
        with pytest.raises(TypeError):
            Check(object())

    def test_check_should_accept_resource_returning_bare_metric(self):
        class R_ReturnsBareMetric(monitoringplugin.Resource):
            def probe(self):
                return monitoringplugin.Metric("foo", 0, context="default")

        res = R_ReturnsBareMetric()
        c = Check(res)
        c()
        assert res in c.resources

    def test_evaluate_resource_populates_results_perfdata(self):
        c = Check()
        c._evaluate_resource(R1_MetricDefaultContext())
        assert 1 == len(c.results)
        assert "foo" == c.results[0].metric.name
        assert ["foo=1"] == c.perfdata

    def test_evaluate_resource_looks_up_context(self):
        class R2_MetricCustomContext(monitoringplugin.Resource):
            def probe(self):
                return [monitoringplugin.Metric("bar", 2)]

        ctx = monitoringplugin.ScalarContext("bar", "1", "1")
        c = Check(ctx)
        c._evaluate_resource(R2_MetricCustomContext())
        assert c.results[0].metric.contextobj == ctx

    def test_evaluate_resource_catches_checkerror(self):
        class R3_Faulty(monitoringplugin.Resource):
            def probe(self):
                raise monitoringplugin.CheckError("problem")

        c = Check()
        c._evaluate_resource(R3_Faulty())
        result = c.results[0]
        assert monitoringplugin.unknown == result.state
        assert "problem" == result.hint

    def test_call_evaluates_resources_and_compacts_perfdata(self):
        class R4_NoPerfdata(monitoringplugin.Resource):
            def probe(self):
                return [monitoringplugin.Metric("m4", 4, context="null")]

        c = Check(R1_MetricDefaultContext(), R4_NoPerfdata())
        c()
        assert ["foo", "m4"] == [res.metric.name for res in c.results]
        assert ["foo=1"] == c.perfdata

    def test_evaluate_bare_state_is_autowrapped_in_result(self):
        metric = monitoringplugin.Metric("m5", 0)

        class R5_DefaultMetric(monitoringplugin.Resource):
            def probe(self):
                return [metric]

        class BareStateContext(monitoringplugin.Context):
            def evaluate(self, metric, resource):
                return monitoringplugin.ok

        c = Check(R5_DefaultMetric(), BareStateContext("m5"))
        c()
        assert c.results[0].state == monitoringplugin.ok
        assert c.results[0].metric.name == "m5"

    def test_first_resource_sets_name(self):
        class MyResource(monitoringplugin.Resource):
            pass

        c = Check()
        assert "" == c.name
        c.add(MyResource())
        assert "MyResource" == c.name

    def test_utf8(self):
        class UTF8(monitoringplugin.Resource):
            def probe(self):
                return monitoringplugin.Metric("utf8", 8, context="utf8")

        c = Check(
            UTF8(),
            monitoringplugin.ScalarContext("utf8", "1:1", fmt_metric="über {value}"),
        )
        c()
        assert "über 8 (outside range 1:1)" == c.summary_str
        ["warning: über 8 (outside range 1:1)"] == c.verbose_str

    def test_set_explicit_name(self):
        c = Check()
        c.name = "mycheck"
        c.add(monitoringplugin.Resource())
        assert "mycheck" == c.name

    def test_check_without_results_is_unkown(self):
        assert monitoringplugin.unknown == Check().state

    def test_default_summary_if_no_results(self):
        c = Check()
        assert "no check results" == c.summary_str

    def test_state_if_resource_has_no_metrics(self):
        c = Check(monitoringplugin.Resource())
        c()
        assert monitoringplugin.unknown == c.state
        assert 3 == c.exitcode

    def test_summary_str_calls_ok_if_state_ok(self):
        c = Check(FakeSummary())
        c._evaluate_resource(R1_MetricDefaultContext())
        assert "I'm feelin' good" == c.summary_str

    def test_summary_str_calls_problem_if_state_not_ok(self):
        c = Check(FakeSummary())
        c.results.add(monitoringplugin.Result(monitoringplugin.critical))
        assert "Houston, we have a problem" == c.summary_str

    def test_execute(self):
        def fake_execute(_runtime_obj, verbose, timeout):
            assert 2 == verbose
            assert 20 == timeout

        r = monitoringplugin.Runtime()
        r.execute = fake_execute
        Check().main(2, 20)

    def test_verbose_str(self):
        assert "" == Check().verbose_str
