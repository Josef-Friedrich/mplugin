from monitoringplugin.state import Critical, Ok, Unknown, Warn, worst


class TestState:
    def test_str(self):
        assert "ok" == str(Ok)

    def test_int(self):
        assert 3 == int(Unknown)

    def test_cmp_less(self):
        assert Warn < Critical

    def test_cmp_greater(self):
        assert Warn > Ok

    def test_worst(self):
        assert Critical == worst([Ok, Critical, Warn])

    def test_worst_of_emptyset_is_ok(self):
        assert Ok == worst([])
