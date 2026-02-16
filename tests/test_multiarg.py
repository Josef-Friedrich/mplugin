from monitoringplugin.multiarg import MultiArg


class TestMultiarg:
    def test_len(self) -> None:
        m = MultiArg(["a", "b"])
        assert 2 == len(m)

    def test_iter(self) -> None:
        m = MultiArg(["a", "b"])
        assert ["a", "b"] == list(m)

    def test_split(self) -> None:
        m = MultiArg("a,b")
        assert ["a", "b"] == list(m)

    def test_explicit_fill_element(self) -> None:
        m = MultiArg(["0", "1"], fill="extra")
        assert "1" == m[1]
        assert "extra" == m[2]

    def test_fill_with_last_element(self) -> None:
        m = MultiArg(["0", "1"])
        assert "1" == m[1]
        assert "1" == m[2]

    def test_fill_empty_multiarg_returns_none(self) -> None:
        assert None is MultiArg([])[0]
