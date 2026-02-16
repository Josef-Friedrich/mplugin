import monitoringplugin
from monitoringplugin.summary import Summary


class TestSummary:
    def test_ok_returns_first_result(self):
        results = monitoringplugin.Results(
            monitoringplugin.Result(monitoringplugin.Ok, "result 1"),
            monitoringplugin.Result(monitoringplugin.Ok, "result 2"),
        )
        assert "result 1" == Summary().ok(results)

    def test_problem_returns_first_significant(self):
        results = monitoringplugin.Results(
            monitoringplugin.Result(monitoringplugin.Ok, "result 1"),
            monitoringplugin.Result(monitoringplugin.Critical, "result 2"),
        )
        assert "result 2" == Summary().problem(results)

    def test_verbose(self):
        assert ["critical: reason1", "warning: reason2"] == Summary().verbose(
            monitoringplugin.Results(
                monitoringplugin.Result(monitoringplugin.Critical, "reason1"),
                monitoringplugin.Result(monitoringplugin.Ok, "ignore"),
                monitoringplugin.Result(monitoringplugin.Warn, "reason2"),
            )
        )
