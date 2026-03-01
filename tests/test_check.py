from typing import Optional

import pytest

from mplugin import (
    Check,
    CheckError,
    Context,
    Metric,
    Resource,
    Result,
    Results,
    ScalarContext,
    ServiceState,
    Summary,
    _Runtime,  # type: ignore
    critical,
    ok,
    unknown,
)


class FakeSummary(Summary):
    def ok(self, results: Results):
        return "I'm feelin' good"

    def problem(self, results: Results):
        return "Houston, we have a problem"


class R1_MetricDefaultContext(Resource):
    def probe(self):
        return [Metric("foo", 1, context="default")]


class TestCheck:
    def test_add_resource(self) -> None:
        c = Check()
        r1 = Resource()
        r2 = Resource()
        c.add(r1, r2)
        assert [r1, r2] == c.resources

    def test_add_context(self) -> None:
        ctx = ScalarContext("ctx1", "", "")
        c = Check(ctx)
        assert ctx.name in c.contexts

    def test_add_summary(self) -> None:
        s = Summary()
        c = Check(s)
        assert s == c.summary

    def test_add_results(self) -> None:
        r = Results()
        c = Check(r)
        assert r == c.results

    def test_add_unknown_type_should_raise_typeerror(self) -> None:
        with pytest.raises(TypeError):
            Check(object())  # type: ignore

    def test_check_should_accept_resource_returning_bare_metric(self) -> None:
        class R_ReturnsBareMetric(Resource):
            def probe(self) -> Metric:
                return Metric("foo", 0, context="default")

        res = R_ReturnsBareMetric()
        c = Check(res)
        c()
        assert res in c.resources

    def test_evaluate_resource_populates_results_perfdata(self) -> None:
        c = Check()
        c._evaluate_resource(R1_MetricDefaultContext())  # type: ignore
        assert 1 == len(c.results)
        assert c.results[0].metric
        assert "foo" == c.results[0].metric.name
        assert ["foo=1"] == c.perfdata

    def test_evaluate_resource_looks_up_context(self) -> None:
        class R2_MetricCustomContext(Resource):
            def probe(self):
                return [Metric("bar", 2)]

        ctx = ScalarContext("bar", "1", "1")
        c = Check(ctx)
        c._evaluate_resource(R2_MetricCustomContext())  # type: ignore
        assert c.results[0].metric
        assert c.results[0].metric.contextobj == ctx

    def test_evaluate_resource_catches_checkerror(self) -> None:
        class R3_Faulty(Resource):
            def probe(self):
                raise CheckError("problem")

        c = Check()
        c._evaluate_resource(R3_Faulty())  # type: ignore
        result = c.results[0]
        assert unknown == result.state
        assert "problem" == result.hint

    def test_call_evaluates_resources_and_compacts_perfdata(self) -> None:
        class R4_NoPerfdata(Resource):
            def probe(self) -> list[Metric]:
                return [Metric("m4", 4, context="null")]

        c = Check(R1_MetricDefaultContext(), R4_NoPerfdata())
        c()

        metric_names: list[str] = []
        for res in c.results:
            if res.metric is not None:
                metric_names.append(res.metric.name)

        assert ["foo", "m4"] == metric_names
        assert ["foo=1"] == c.perfdata

    def test_evaluate_bare_state_is_autowrapped_in_result(self) -> None:
        metric = Metric("m5", 0)

        class R5_DefaultMetric(Resource):
            def probe(self) -> list[Metric]:
                return [metric]

        class BareStateContext(Context):
            def evaluate(self, metric: Metric, resource: Resource) -> ServiceState:
                return ok

        c = Check(R5_DefaultMetric(), BareStateContext("m5"))
        c()
        assert c.results[0].state == ok
        assert c.results[0].metric
        assert c.results[0].metric.name == "m5"

    def test_first_resource_sets_name(self) -> None:
        class MyResource(Resource):
            pass

        c = Check()
        assert "" == c.name
        c.add(MyResource())
        assert "MyResource" == c.name

    def test_utf8(self) -> None:
        class UTF8(Resource):
            def probe(self) -> Metric:
                return Metric("utf8", 8, context="utf8")

        c = Check(
            UTF8(),
            ScalarContext("utf8", "1:1", fmt_metric="über {value}"),
        )
        c()
        assert "über 8 (outside range 1:1)" == c.summary_str
        assert ["warning: über 8 (outside range 1:1)"] == c.verbose_str

    def test_set_explicit_name(self) -> None:
        c = Check()
        c.name = "mycheck"
        c.add(Resource())
        assert "mycheck" == c.name

    def test_check_without_results_is_unkown(self) -> None:
        assert unknown == Check().state

    def test_default_summary_if_no_results(self) -> None:
        c = Check()
        assert "no check results" == c.summary_str

    def test_state_if_resource_has_no_metrics(self) -> None:
        c = Check(Resource())
        c()
        assert unknown == c.state
        assert 3 == c.exitcode

    def test_summary_str_calls_ok_if_state_ok(self) -> None:
        c = Check(FakeSummary())
        c._evaluate_resource(R1_MetricDefaultContext())  # type: ignore
        assert "I'm feelin' good" == c.summary_str

    def test_summary_str_calls_problem_if_state_not_ok(self) -> None:
        c = Check(FakeSummary())
        c.results.add(Result(critical))
        assert "Houston, we have a problem" == c.summary_str

    def test_execute(self) -> None:
        def fake_execute(
            check: Check,
            verbose: Optional[int] = None,
            timeout: Optional[int] = None,
            colorize: bool = False,
        ) -> None:
            assert 2 == verbose
            assert 20 == timeout
            assert colorize

        r = _Runtime()
        r.execute = fake_execute  # type: ignore
        Check().main(2, 20, True)

    def test_verbose_str(self) -> None:
        assert "" == Check().verbose_str
