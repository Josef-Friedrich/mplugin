import io
import sys
import typing
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from mplugin import critical
from mplugin.testing import MockResult


def test_mock_result() -> typing.NoReturn:

    file_stdout = io.StringIO()
    file_stderr = io.StringIO()

    with (
        mock.patch("sys.exit") as sys_exit,
        redirect_stdout(file_stdout),
        redirect_stderr(file_stderr),
    ):
        print("test!")
        sys.exit(2)
        result = MockResult(sys_exit, file_stdout, file_stderr)

        assert result.first_line == "test!"
        assert result.exitcode == 2
        assert result.state == critical
        assert result.output == "test!\n"
