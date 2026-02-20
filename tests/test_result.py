import pytest

from mplugin import Metric, Result, Results, critical, ok, unknown, warn


class TestResult:
    def test_resorce_should_be_none_for_resourceless_metric(self) -> None:
        assert Result(ok).resource is None

    def test_metric_resorce(self) -> None:
        res = object()
        m = Metric("foo", 1, resource=res)
        assert Result(ok, metric=m).resource == res

    def test_context_should_be_none_for_contextless_metric(self) -> None:
        assert Result(ok).context is None

    def test_metric_context(self) -> None:
        ctx = object()
        m = Metric("foo", 1, contextobj=ctx)
        assert Result(ok, metric=m).context == ctx

    def test_str_metric_with_hint(self) -> None:
        assert "2 (unexpected)" == str(Result(warn, "unexpected", Metric("foo", 2)))

    def test_str_metric_only(self) -> None:
        assert "3" == str(Result(warn, metric=Metric("foo", 3)))

    def test_str_hint_only(self) -> None:
        assert "how come?" == str(Result(warn, "how come?"))

    def test_str_empty(self) -> None:
        assert "" == str(Result(warn))


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
        r.add(Result(warn), Result(ok), Result(critical), Result(warn))
        assert [critical, warn, warn, ok] == [result.state for result in r]

    def test_most_significant_state_shoud_raise_valueerror_if_empty(self):
        with pytest.raises(ValueError):
            Results().most_significant_state

    def test_most_significant_state(self) -> None:
        r = Results()
        r.add(Result(ok))
        assert ok == r.most_significant_state
        r.add(Result(critical))
        assert critical == r.most_significant_state
        r.add(Result(warn))
        assert critical == r.most_significant_state

    def test_most_significant_should_return_empty_set_if_empty(self) -> None:
        assert [] == Results().most_significant

    def test_most_signigicant(self) -> None:
        r = Results()
        r.add(Result(ok), Result(warn), Result(ok), Result(warn))
        assert [warn, warn] == [result.state for result in r.most_significant]

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
            Results(True)
