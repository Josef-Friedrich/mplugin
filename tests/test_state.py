from monitoringplugin.state import critical, ok, unknown, warn, worst


class TestState:
    def test_str(self):
        assert "ok" == str(ok)

    def test_int(self):
        assert 3 == int(unknown)

    def test_cmp_less(self):
        assert warn < critical

    def test_cmp_greater(self):
        assert warn > ok

    def test_worst(self):
        assert critical == worst([ok, critical, warn])

    def test_worst_of_emptyset_is_ok(self):
        assert ok == worst([])
