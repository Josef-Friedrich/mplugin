import io
import logging

import monitoringplugin
from monitoringplugin.output import Output


class FakeCheck:
    name = "Fake"
    state = monitoringplugin.ok
    summary_str = "check summary"
    verbose_str = "hello world\n"
    perfdata = ["foo=1m;2;3", "bar=1s;2;3"]


class TestOutput:
    def setup_method(self):
        self.logio = io.StringIO()
        self.logchan = logging.StreamHandler(self.logio)

    def test_add_longoutput_string(self):
        o = Output(self.logchan)
        o.add_longoutput("first line\nsecond line\n")
        assert str(o) == "first line\nsecond line\n"

    def test_add_longoutput_list(self):
        o = Output(self.logchan)
        o.add_longoutput(["first line", "second line"])
        assert str(o) == "first line\nsecond line\n"

    def test_add_longoutput_tuple(self):
        o = Output(self.logchan)
        o.add_longoutput(("first line", "second line"))
        assert str(o) == "first line\nsecond line\n"

    def test_str_should_append_log(self):
        o = Output(self.logchan)
        print("debug log output", file=self.logio)
        assert "debug log output\n" == str(o)

    def test_empty_summary_perfdata(self):
        o = Output(self.logchan)
        check = FakeCheck()
        check.summary_str = ""
        check.perfdata = []
        o.add(check)
        assert "FAKE OK\n" == str(o)

    def test_empty_name(self):
        o = Output(self.logchan)
        check = FakeCheck()
        check.name = None
        check.perfdata = []
        o.add(check)
        assert "OK - check summary\n" == str(o)

    def test_summary_utf8(self):
        o = Output(self.logchan)
        check = FakeCheck()
        check.summary_str = "utf-8 ümłäúts"
        check.perfdata = []
        o.add(check)
        assert "FAKE OK - utf-8 ümłäúts\n" == "{0}".format(o)

    def test_add_check_singleline(self):
        o = Output(self.logchan)
        o.add(FakeCheck())
        assert "FAKE OK - check summary | foo=1m;2;3 bar=1s;2;3\n" == str(o)

    def test_add_check_multiline(self):
        o = Output(self.logchan, verbose=1)
        o.add(FakeCheck())
        assert "FAKE OK - check summary\nhello world\n| foo=1m;2;3 bar=1s;2;3\n" == str(
            o
        )

    def test_remove_illegal_chars(self):
        check = FakeCheck()
        check.summary_str = "PIPE | STATUS"
        check.verbose_str = "long pipe | output"
        check.perfdata = []
        print("debug pipe | x", file=self.logio)
        o = Output(self.logchan, verbose=1)
        o.add(check)
        assert (
            "FAKE OK - PIPE  STATUS\nlong pipe  output\ndebug pipe  x\nwarning: removed illegal characters (0x7c) from status line\nwarning: removed illegal characters (0x7c) from long output\nwarning: removed illegal characters (0x7c) from logging output\n"
            == str(o)
        )

    def test_long_perfdata(self):
        check = FakeCheck()
        check.verbose_str = ""
        check.perfdata = ["duration=340.4ms;500;1000;0"] * 5
        o = Output(self.logchan, verbose=1)
        o.add(check)
        assert (
            "FAKE OK - check summary\n| duration=340.4ms;500;1000;0 duration=340.4ms;500;1000;0 duration=340.4ms;500;1000;0 duration=340.4ms;500;1000;0 duration=340.4ms;500;1000;0\n"
            == str(o)
        )

    def test_log_output_precedes_perfdata(self):
        check = FakeCheck()
        check.perfdata = ["foo=1"]
        print("debug log output", file=self.logio)
        o = Output(self.logchan, verbose=1)
        o.add(check)
        assert (
            "FAKE OK - check summary\n"
            + "hello world\n"
            + "debug log output\n"
            + "| foo=1\n"
            == str(o)
        )
