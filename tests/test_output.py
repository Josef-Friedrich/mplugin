import io
import logging
from typing import Optional, cast

from mplugin import Check, _Output, ok  # type: ignore


class FakeCheck:
    name: Optional[str] = "Fake"
    state = ok
    summary_str = "check summary"
    verbose_str = "hello world\n"
    perfdata = ["foo=1m;2;3", "bar=1s;2;3"]


class TestOutput:
    def setup_method(self) -> None:
        self.logio = io.StringIO()
        self.logchan = logging.StreamHandler(self.logio)

    def test_add_longoutput_string(self) -> None:
        o = _Output(self.logchan)
        o.add_longoutput("first line\nsecond line\n")
        assert str(o) == "first line\nsecond line\n"

    def test_add_longoutput_list(self) -> None:
        o = _Output(self.logchan)
        o.add_longoutput(["first line", "second line"])
        assert str(o) == "first line\nsecond line\n"

    def test_add_longoutput_tuple(self) -> None:
        o = _Output(self.logchan)
        o.add_longoutput(("first line", "second line"))
        assert str(o) == "first line\nsecond line\n"

    def test_str_should_append_log(self) -> None:
        o = _Output(self.logchan)
        print("debug log output", file=self.logio)
        assert "debug log output\n" == str(o)

    def test_empty_summary_perfdata(self) -> None:
        o = _Output(self.logchan)
        check = FakeCheck()
        check.summary_str = ""
        check.perfdata = []
        o.add(cast(Check, check))
        assert "FAKE OK\n" == str(o)

    def test_empty_name(self) -> None:
        o = _Output(self.logchan)
        check = FakeCheck()
        check.name = None
        check.perfdata = []
        o.add(cast(Check, check))
        assert "OK - check summary\n" == str(o)

    def test_summary_utf8(self) -> None:
        o = _Output(self.logchan)
        check = FakeCheck()
        check.summary_str = "utf-8 ümłäúts"
        check.perfdata = []
        o.add(cast(Check, check))
        assert "FAKE OK - utf-8 ümłäúts\n" == "{0}".format(o)

    def test_add_check_singleline(self) -> None:
        o = _Output(self.logchan)
        o.add(cast(Check, FakeCheck()))
        assert "FAKE OK - check summary | foo=1m;2;3 bar=1s;2;3\n" == str(o)

    def test_add_check_multiline(self) -> None:
        o = _Output(self.logchan, verbose=1)
        o.add(cast(Check, FakeCheck()))
        assert "FAKE OK - check summary\nhello world\n| foo=1m;2;3 bar=1s;2;3\n" == str(
            o
        )

    def test_remove_illegal_chars(self) -> None:
        check = FakeCheck()
        check.summary_str = "PIPE | STATUS"
        check.verbose_str = "long pipe | output"
        check.perfdata = []
        print("debug pipe | x", file=self.logio)
        o = _Output(self.logchan, verbose=1)
        o.add(cast(Check, check))
        assert (
            "FAKE OK - PIPE  STATUS\nlong pipe  output\ndebug pipe  x\nwarning: removed illegal characters (0x7c) from status line\nwarning: removed illegal characters (0x7c) from long output\nwarning: removed illegal characters (0x7c) from logging output\n"
            == str(o)
        )

    def test_long_perfdata(self) -> None:
        check = FakeCheck()
        check.verbose_str = ""
        check.perfdata = ["duration=340.4ms;500;1000;0"] * 5
        o = _Output(self.logchan, verbose=1)
        o.add(cast(Check, check))
        assert (
            "FAKE OK - check summary\n| duration=340.4ms;500;1000;0 duration=340.4ms;500;1000;0 duration=340.4ms;500;1000;0 duration=340.4ms;500;1000;0 duration=340.4ms;500;1000;0\n"
            == str(o)
        )

    def test_log_output_precedes_perfdata(self) -> None:
        check = FakeCheck()
        check.perfdata = ["foo=1"]
        print("debug log output", file=self.logio)
        o = _Output(self.logchan, verbose=1)
        o.add(cast(Check, check))
        assert (
            "FAKE OK - check summary\n"
            + "hello world\n"
            + "debug log output\n"
            + "| foo=1\n"
            == str(o)
        )
