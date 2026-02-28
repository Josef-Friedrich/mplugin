import pytest

from mplugin import (
    Context,
    Metric,
    Resource,
    Result,
    Results,
    critical,
    ok,
    unknown,
    warning,
)


class TestResult:
    def test_resorce_should_be_none_for_resourceless_metric(self) -> None:
        assert Result(ok).resource is None

    def test_metric_resorce(self) -> None:
        res = Resource()
        m = Metric("foo", 1, resource=res)
        assert Result(ok, metric=m).resource == res

    def test_context_should_be_none_for_contextless_metric(self) -> None:
        assert Result(ok).context is None

    def test_metric_context(self) -> None:
        ctx = Context("test")
        m = Metric("foo", 1, contextobj=ctx)
        assert Result(ok, metric=m).context == ctx

    def test_str_metric_with_hint(self) -> None:
        assert "2 (unexpected)" == str(Result(warning, "unexpected", Metric("foo", 2)))

    def test_str_metric_only(self) -> None:
        assert "3" == str(Result(warning, metric=Metric("foo", 3)))

    def test_str_hint_only(self) -> None:
        assert "how come?" == str(Result(warning, "how come?"))

    def test_str_empty(self) -> None:
        assert "" == str(Result(warning))


class TestResults:
    def test_lookup_by_metric_name(self) -> None:
        r = Results()
        result = Result(ok, "", Metric("met1", 0))
        r.add(result, Result(ok, "other"))
        assert r["met1"] == result

    def test_lookup_by_index(self) -> None:
        r = Results()
        result = Result(ok, "", Metric("met1", 0))
        r.add(Result(ok, "other"), result)
        assert r[1] == result

    def test_len(self) -> None:
        r = Results()
        r.add(Result(ok), Result(ok), Result(ok))
        assert 3 == len(r)

    def test_iterate_in_order_of_descending_states(self) -> None:
        r = Results()
        r.add(Result(warning), Result(ok), Result(critical), Result(warning))
        assert [critical, warning, warning, ok] == [result.state for result in r]

    def test_most_significant_state_shoud_raise_valueerror_if_empty(self):
        with pytest.raises(ValueError):
            Results().most_significant_state

    def test_most_significant_state(self) -> None:
        r = Results()
        r.add(Result(ok))
        assert ok == r.most_significant_state
        r.add(Result(critical))
        assert critical == r.most_significant_state
        r.add(Result(warning))
        assert critical == r.most_significant_state

    def test_most_significant_should_return_empty_set_if_empty(self) -> None:
        assert [] == Results().most_significant

    def test_most_signigicant(self) -> None:
        r = Results()
        r.add(Result(ok), Result(warning), Result(ok), Result(warning))
        assert [warning, warning] == [result.state for result in r.most_significant]

    def test_first_significant(self) -> None:
        r = Results()
        r.add(
            Result(critical), Result(unknown, "r1"), Result(unknown, "r2"), Result(ok)
        )
        assert Result(unknown, "r1") == r.first_significant

    def test_contains(self) -> None:
        results = Results()
        r1 = Result(unknown, "r1", Metric("m1", 1))
        results.add(r1)
        assert "m1" in results
        assert "m2" not in results

    def test_add_in_init(self) -> None:
        results = Results(Result(unknown, "r1"), Result(unknown, "r2"))
        assert 2 == len(results)

    def test_add_should_fail_unless_result_passed(self) -> None:
        with pytest.raises(ValueError):
            Results(True)  # type: ignore
