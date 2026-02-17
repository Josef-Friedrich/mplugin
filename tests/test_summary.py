import monitoringplugin
from monitoringplugin.summary import Summary


class TestSummary:
    def test_ok_returns_first_result(self):
        results = monitoringplugin.Results(
            monitoringplugin.Result(monitoringplugin.ok, "result 1"),
            monitoringplugin.Result(monitoringplugin.ok, "result 2"),
        )
        assert "result 1" == Summary().ok(results)

    def test_problem_returns_first_significant(self):
        results = monitoringplugin.Results(
            monitoringplugin.Result(monitoringplugin.ok, "result 1"),
            monitoringplugin.Result(monitoringplugin.critical, "result 2"),
        )
        assert "result 2" == Summary().problem(results)

    def test_verbose(self):
        assert ["critical: reason1", "warning: reason2"] == Summary().verbose(
            monitoringplugin.Results(
                monitoringplugin.Result(monitoringplugin.critical, "reason1"),
                monitoringplugin.Result(monitoringplugin.ok, "ignore"),
                monitoringplugin.Result(monitoringplugin.warn, "reason2"),
            )
        )
