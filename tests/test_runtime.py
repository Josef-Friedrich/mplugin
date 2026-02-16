import logging

import pytest

import monitoringplugin
from monitoringplugin.compat import StringIO
from monitoringplugin.runtime import Runtime, guarded


def make_check():
    class Check(object):
        summary_str = "summary"
        verbose_str = "long output"
        name = "check"
        state = monitoringplugin.Ok
        exitcode = 0
        perfdata = None

        def __call__(self):
            pass

    return Check()


class TestRuntimeBase:
    def setup_method(self):
        Runtime.instance = None
        self.r = Runtime()
        self.r.sysexit = lambda: None
        self.r.stdout = StringIO()


class RuntimeTest(TestRuntimeBase):
    def test_runtime_is_singleton(self):
        assert self.r == Runtime()

    def test_run_sets_exitcode(self):
        self.r.run(make_check())
        assert 0 == self.r.exitcode

    def test_verbose(self):
        testcases = [
            (None, logging.WARNING, 0),
            (1, logging.WARNING, 1),
            ("vv", logging.INFO, 2),
            (3, logging.DEBUG, 3),
            ("vvvv", logging.DEBUG, 3),
        ]
        for argument, exp_level, exp_verbose in testcases:
            self.r.verbose = argument
            assert exp_level == self.r.logchan.level
            assert exp_verbose == self.r.verbose

    def test_execute_uses_defaults(self):
        self.r.execute(make_check())
        assert 1 == self.r.verbose
        assert None is self.r.timeout

    def test_execute_sets_verbose_and_timeout(self):
        self.r.execute(make_check(), 2, 10)
        assert 2 == self.r.verbose
        assert 10 == self.r.timeout


class RuntimeExceptionTest(TestRuntimeBase):
    def setup_method(self):
        super(RuntimeExceptionTest, self).setUp()

    def run_main_with_exception(self, exc):
        @guarded
        def main():
            raise exc

        main()

    def test_handle_exception_set_exitcode_and_formats_output(self):
        self.run_main_with_exception(RuntimeError("problem"))
        assert 3 == self.r.exitcode
        assert "UNKNOWN: RuntimeError: problem" in self.r.stdout.getvalue()

    def test_handle_exception_prints_no_traceback(self):
        self.r.verbose = 0
        self.run_main_with_exception(RuntimeError("problem"))
        assert "Traceback" not in self.r.stdout.getvalue()

    def test_handle_exception_verbose_default(self):
        self.run_main_with_exception(RuntimeError("problem"))
        assert "Traceback" in self.r.stdout.getvalue()

    def test_handle_timeout_exception(self):
        self.run_main_with_exception(monitoringplugin.Timeout("1s"))
        assert (
            "UNKNOWN: Timeout: check execution aborted after 1s"
            in self.r.stdout.getvalue()
        )

    def test_guarded_set_verbosity(self):
        @guarded(verbose=0)
        def main():
            pass

        main()
        assert 0 == self.r.verbose

    def test_guarded_no_keyword(self):
        with pytest.raises(AssertionError):

            @guarded(0)
            def main():
                pass
