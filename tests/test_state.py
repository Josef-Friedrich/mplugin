from mplugin import critical, ok, unknown, warning, worst


class TestState:
    def test_str(self) -> None:
        assert "ok" == str(ok)

    def test_int(self) -> None:
        assert 3 == int(unknown)

    def test_cmp_less(self) -> None:
        assert warning < critical

    def test_cmp_greater(self) -> None:
        assert warning > ok


class TestWorst:
    def test_not_empty_set(self) -> None:
        assert critical == worst([ok, critical, warning])

    def test_empty_set_is_ok(self) -> None:
        assert ok == worst([])
