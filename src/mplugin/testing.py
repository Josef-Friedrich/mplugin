"""Helper classes and methods for testing monitoring plugins."""

from __future__ import annotations

import io
import os
import subprocess
import typing
from pathlib import Path
from unittest.mock import Mock

from mplugin import ServiceState, state


class MockResult:
    """A class to collect the result of a mocked execution."""

    __sys_exit: Mock
    __stdout: typing.Optional[str] = None
    __stderr: typing.Optional[str] = None

    def __init__(
        self,
        sys_exit_mock: Mock,
        stdout: typing.Optional[io.StringIO],
        stderr: typing.Optional[io.StringIO],
    ) -> None:
        self.__sys_exit = sys_exit_mock

        if stdout is not None:
            out = stdout.getvalue()
            if out != "":
                self.__stdout = out

        if stderr is not None:
            err = stderr.getvalue()
            if err != "":
                self.__stderr = err

    @property
    def exitcode(self) -> int:
        """The captured exit code"""
        return int(self.__sys_exit.call_args[0][0])

    @property
    def state(self) -> ServiceState:
        return state(self.exitcode)

    @property
    def stdout(self) -> typing.Optional[str]:
        if self.__stdout:
            return self.__stdout
        return None

    @property
    def stderr(self) -> typing.Optional[str]:
        if self.__stderr:
            return self.__stderr
        return None

    @property
    def output(self) -> str:
        out: str = ""

        if self.__stderr:
            out += self.__stderr

        if self.__stdout:
            out += self.__stdout

        return out

    @property
    def first_line(self) -> typing.Optional[str]:
        """The first line of the output without a newline break at the
        end as a string.
        """
        if self.output:
            return self.output.split("\n", 1)[0]
        return None


def run_with_bin(args: list[str], bin_dir: Path) -> subprocess.CompletedProcess[str]:
    """
    Run a command with a modified PATH environment variable.

    Prepends the specified binary directory to the PATH environment variable
    before running the subprocess, allowing executables in that directory to
    be found first during command resolution.

    :param args: List of command arguments to execute
    :param bin_dir: Directory to prepend to the PATH environment variable
    :return: Completed process object with stdout and stderr as strings
    """

    env: dict[str, str] = os.environ.copy()
    env["PATH"] = str(bin_dir) + ":" + env["PATH"]
    return subprocess.run(args, env=env, encoding="utf-8")
