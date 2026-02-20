from mplugin import Result, Results, Summary, critical, ok, warn


class TestSummary:
    def test_ok_returns_first_result(self) -> None:
        results = Results(
            Result(ok, "result 1"),
            Result(ok, "result 2"),
        )
        assert "result 1" == Summary().ok(results)

    def test_problem_returns_first_significant(self) -> None:
        results = Results(
            Result(ok, "result 1"),
            Result(critical, "result 2"),
        )
        assert "result 2" == Summary().problem(results)

    def test_verbose(self) -> None:
        assert ["critical: reason1", "warning: reason2"] == Summary().verbose(
            Results(
                Result(critical, "reason1"),
                Result(ok, "ignore"),
                Result(warn, "reason2"),
            )
        )
