# -*- coding: utf-8 -*-
import nagiosplugin
import pytest
from nagiosplugin.result import Result, Results
from nagiosplugin.state import Critical, Ok, Unknown, Warn

try:
    import unittest2 as unittest
except ImportError:  # pragma: no cover
    import unittest


class TestResult:
    def test_resorce_should_be_none_for_resourceless_metric(self):
        assert Result(Ok).resource is None

    def test_metric_resorce(self):
        res = object()
        m = nagiosplugin.Metric("foo", 1, resource=res)
        assert Result(Ok, metric=m).resource == res

    def test_context_should_be_none_for_contextless_metric(self):
        assert Result(Ok).context is None

    def test_metric_context(self):
        ctx = object()
        m = nagiosplugin.Metric("foo", 1, contextobj=ctx)
        assert Result(Ok, metric=m).context == ctx

    def test_str_metric_with_hint(self):
        assert "2 (unexpected)" == str(
            Result(Warn, "unexpected", nagiosplugin.Metric("foo", 2))
        )

    def test_str_metric_only(self):
        assert "3" == str(Result(Warn, metric=nagiosplugin.Metric("foo", 3)))

    def test_str_hint_only(self):
        assert "how come?" == str(Result(Warn, "how come?"))

    def test_str_empty(self):
        assert "" == str(Result(Warn))


class TestResults:
    def test_lookup_by_metric_name(self):
        r = Results()
        result = Result(Ok, "", nagiosplugin.Metric("met1", 0))
        r.add(result, Result(Ok, "other"))
        assert r["met1"] == result

    def test_lookup_by_index(self):
        r = Results()
        result = Result(Ok, "", nagiosplugin.Metric("met1", 0))
        r.add(Result(Ok, "other"), result)
        assert r[1] == result

    def test_len(self):
        r = Results()
        r.add(Result(Ok), Result(Ok), Result(Ok))
        assert 3 == len(r)

    def test_iterate_in_order_of_descending_states(self):
        r = Results()
        r.add(Result(Warn), Result(Ok), Result(Critical), Result(Warn))
        assert [Critical, Warn, Warn, Ok] == [result.state for result in r]

    def test_most_significant_state_shoud_raise_valueerror_if_empty(self):
        with pytest.raises(ValueError):
            Results().most_significant_state

    def test_most_significant_state(self):
        r = Results()
        r.add(Result(Ok))
        assert Ok == r.most_significant_state
        r.add(Result(Critical))
        assert Critical == r.most_significant_state
        r.add(Result(Warn))
        assert Critical == r.most_significant_state

    def test_most_significant_should_return_empty_set_if_empty(self):
        assert [] == Results().most_significant

    def test_most_signigicant(self):
        r = Results()
        r.add(Result(Ok), Result(Warn), Result(Ok), Result(Warn))
        assert [Warn, Warn] == [result.state for result in r.most_significant]

    def test_first_significant(self):
        r = Results()
        r.add(
            Result(Critical), Result(Unknown, "r1"), Result(Unknown, "r2"), Result(Ok)
        )
        assert Result(Unknown, "r1") == r.first_significant

    def test_contains(self):
        results = Results()
        r1 = Result(Unknown, "r1", nagiosplugin.Metric("m1", 1))
        results.add(r1)
        assert "m1" in results
        assert not "m2" in results

    def test_add_in_init(self):
        results = Results(Result(Unknown, "r1"), Result(Unknown, "r2"))
        assert 2 == len(results)

    def test_add_should_fail_unless_result_passed(self):
        with pytest.raises(ValueError):
            Results(True)
