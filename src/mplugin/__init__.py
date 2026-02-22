from __future__ import annotations

import argparse
import collections
import functools
import importlib
import io
import json
import logging
import numbers
import os
import re
import sys
import traceback
import typing
from collections import UserDict
from importlib import metadata
from logging import StreamHandler
from tempfile import TemporaryFile
from types import TracebackType

import typing_extensions

__version__: str = metadata.version("mplugin")


# error.py

"""Exceptions with special meanings for mplugin."""


class CheckError(RuntimeError):
    """Abort check execution.

    This exception should be raised if it becomes clear for a plugin
    that it is not able to determine the system status. Raising this
    exception will make the plugin display the exception's argument and
    exit with an UNKNOWN (3) status.
    """

    pass


class Timeout(RuntimeError):
    """Maximum check run time exceeded.

    This exception is raised internally by mplugin if the check's
    run time takes longer than allowed. Check execution is aborted and
    the plugin exits with an UNKNOWN (3) status.
    """

    pass


# state.py

"""Classes  to represent check outcomes.

This module defines :class:`ServiceState` which is the abstract base class
for check outcomes. The four states defined by the :term:`Nagios plugin API`
are represented as singleton subclasses.

Note that the *warning* state is defined by the :class:`Warn` class. The
class has not been named `Warning` to avoid being confused with the
built-in Python exception of the same name.
"""


def worst(states: list["ServiceState"]) -> "ServiceState":
    """Reduce list of *states* to the most significant state."""
    return functools.reduce(lambda a, b: a if a > b else b, states, ok)


class ServiceState:
    """Abstract base class for all states.

    Each state has two constant attributes: :attr:`text` is the short
    text representation which is printed for example at the beginning of
    the summary line. :attr:`code` is the corresponding exit code.
    """

    code: int

    text: str

    def __init__(self, code: int, text: str) -> None:
        self.code = code
        self.text = text

    def __str__(self) -> str:
        """Plugin-API compliant text representation."""
        return self.text

    def __int__(self) -> int:
        """Plugin API compliant exit code."""
        return self.code

    def __gt__(self, other: typing.Any) -> bool:
        return (
            hasattr(other, "code")
            and isinstance(other.code, int)
            and self.code > other.code
        )

    def __eq__(self, other: typing.Any) -> bool:
        return (
            hasattr(other, "code")
            and isinstance(other.code, int)
            and self.code == other.code
            and hasattr(other, "text")
            and isinstance(other.text, str)
            and self.text == other.text
        )

    def __hash__(self) -> int:
        return hash((self.code, self.text))


class Ok(ServiceState):
    def __init__(self) -> None:
        super().__init__(0, "ok")


ok = Ok()


class Warn(ServiceState):
    def __init__(self) -> None:
        super().__init__(1, "warning")


# According to the Nagios development guidelines, this should be Warning,
# not Warn, but renaming the class would occlude the built-in Warning
# exception class.
warn = Warn()


class Critical(ServiceState):
    def __init__(self) -> None:
        super().__init__(2, "critical")


critical = Critical()


class Unknown(ServiceState):
    def __init__(self) -> None:
        super().__init__(3, "unknown")


unknown = Unknown()

# range.py


RangeSpec = typing.Union[str, int, float, "Range"]


class Range:
    """Represents a threshold range.

    The general format is "[@][start:][end]". "start:" may be omitted if
    start==0. "~:" means that start is negative infinity. If `end` is
    omitted, infinity is assumed. To invert the match condition, prefix
    the range expression with "@".

    See
    https://github.com/monitoring-plugins/monitoring-plugin-guidelines/blob/main/definitions/01.range_expressions.md
    for details.
    """

    invert: bool

    start: float

    end: float

    def __init__(self, spec: typing.Optional[RangeSpec] = None) -> None:
        """Creates a Range object according to `spec`.

        :param spec: may be either a string, a float, or another
            Range object.
        """
        spec = spec or ""
        if isinstance(spec, Range):
            self.invert = spec.invert
            self.start = spec.start
            self.end = spec.end
        elif isinstance(spec, int) or isinstance(spec, float):
            self.invert = False
            self.start = 0
            self.end = spec
        else:
            self.start, self.end, self.invert = Range._parse(str(spec))
        Range._verify(self.start, self.end)

    @classmethod
    def _parse(cls, spec: str) -> tuple[float, float, bool]:
        invert = False
        start: float
        start_str: str
        end: float
        end_str: str
        if spec.startswith("@"):
            invert = True
            spec = spec[1:]
        if ":" in spec:
            start_str, end_str = spec.split(":")
        else:
            start_str, end_str = "", spec
        if start_str == "~":
            start = float("-inf")
        else:
            start = cls._parse_atom(start_str, 0)
        end = cls._parse_atom(end_str, float("inf"))
        return start, end, invert

    @staticmethod
    def _parse_atom(atom: str, default: float) -> float:
        if atom == "":
            return default
        if "." in atom:
            return float(atom)
        return int(atom)

    @staticmethod
    def _verify(start: float, end: float) -> None:
        """Throws ValueError if the range is not consistent."""
        if start > end:
            raise ValueError("start %s must not be greater than end %s" % (start, end))

    def match(self, value: float) -> bool:
        """Decides if `value` is inside/outside the threshold.

        :returns: `True` if value is inside the bounds for non-inverted
            Ranges.

        Also available as `in` operator.
        """
        if value < self.start:
            return False ^ self.invert
        if value > self.end:
            return False ^ self.invert
        return True ^ self.invert

    def __contains__(self, value: float) -> bool:
        return self.match(value)

    def _format(self, omit_zero_start: bool = True) -> str:
        result: list[str] = []
        if self.invert:
            result.append("@")
        if self.start == float("-inf"):
            result.append("~:")
        elif not omit_zero_start or self.start != 0:
            result.append(("%s:" % self.start))
        if self.end != float("inf"):
            result.append(("%s" % self.end))
        return "".join(result)

    def __str__(self) -> str:
        """Human-readable range specification."""
        return self._format()

    def __repr__(self) -> str:
        """Parseable range specification."""
        return "Range(%r)" % str(self)

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Range):
            return False
        return (
            self.invert == value.invert
            and self.start == self.start
            and self.end == self.end
        )

    @property
    def violation(self) -> str:
        """Human-readable description why a value does not match."""
        return "outside range {0}".format(self._format(False))


# multiarg.py


class MultiArg:
    args: list[str]
    fill: typing.Optional[str]

    def __init__(
        self,
        args: typing.Union[list[str], str],
        fill: typing.Optional[str] = None,
        splitchar: str = ",",
    ) -> None:
        if isinstance(args, list):
            self.args = args
        else:
            self.args = args.split(splitchar)
        self.fill = fill

    def __len__(self) -> int:
        return self.args.__len__()

    def __iter__(self) -> typing.Iterator[str]:
        return self.args.__iter__()

    def __getitem__(self, key: int) -> typing.Optional[str]:
        try:
            return self.args.__getitem__(key)
        except IndexError:
            pass
        if self.fill is not None:
            return self.fill
        try:
            return self.args.__getitem__(-1)
        except IndexError:
            return None


# platform.py


def with_timeout(
    time: int, func: typing.Callable[P, R], *args: typing.Any, **kwargs: typing.Any
) -> None:
    """Call `func` but terminate after `t` seconds."""

    if os.name == "posix":
        signal = importlib.import_module("signal")

        def timeout_handler(signum: int, frame: typing.Any) -> typing.NoReturn:
            raise Timeout("{0}s".format(time))

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(time)
        try:
            func(*args, **kwargs)
        finally:
            signal.alarm(0)

    if os.name == "nt":
        # We use a thread here since NT systems don't have POSIX signals.
        threading = importlib.import_module("threading")

        func_thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        func_thread.daemon = True  # quit interpreter even if still running
        func_thread.start()
        func_thread.join(time)
        if func_thread.is_alive():
            raise Timeout("{0}s".format(time))


def flock_exclusive(fileobj: io.TextIOWrapper) -> None:
    """Acquire exclusive lock for open file `fileobj`."""

    if os.name == "posix":
        fcntl = importlib.import_module("fcntl")
        fcntl.flock(fileobj, fcntl.LOCK_EX)

    if os.name == "nt":
        msvcrt = importlib.import_module("msvcrt")
        msvcrt.locking(fileobj.fileno(), msvcrt.LK_LOCK, 2147483647)


# cookie.py

"""Persistent dict to remember state between invocations.

Cookies are used to remember file positions, counters and the like
between plugin invocations. It is not intended for substantial amounts
of data. Cookies are serialized into JSON and saved to a state file. We
prefer a plain text format to allow administrators to inspect and edit
its content. See :class:`~mplugin.logtail.LogTail` for an
application of cookies to get only new lines of a continuously growing
file.

Cookies are locked exclusively so that at most one process at a time has
access to it. Changes to the dict are not reflected in the file until
:meth:`Cookie.commit` is called. It is recommended to use Cookie as
context manager to get it opened and committed automatically.
"""


class Cookie(UserDict[str, typing.Any]):
    path: typing.Optional[str]

    def __init__(self, statefile: typing.Optional[str] = None) -> None:
        """Creates a persistent dict to keep state.

        After creation, a cookie behaves like a normal dict.

        :param statefile: file name to save the dict's contents

        .. note:: If `statefile` is empty or None, the Cookie will be
           oblivous, i.e., it will forget its contents on garbage
           collection. This makes it possible to explicitely throw away
           state between plugin runs (for example by a command line
           argument).
        """
        super(Cookie, self).__init__()
        self.path = statefile
        self.fobj = None

    def __enter__(self) -> typing_extensions.Self:
        """Allows Cookie to be used as context manager.

        Opens the file and passes a dict-like object into the
        subordinate context. See :meth:`open` for details about opening
        semantics. When the context is left in the regular way (no
        exception raised), the cookie is committed to disk.

        :yields: open cookie
        """
        self.open()
        return self

    def __exit__(
        self,
        exc_type: typing.Optional[type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[TracebackType],
    ) -> None:
        if not exc_type:
            self.commit()
        self.close()

    def open(self):
        """Reads/creates the state file and initializes the dict.

        If the state file does not exist, it is touched into existence.
        An exclusive lock is acquired to ensure serialized access. If
        :meth:`open` fails to parse file contents, it truncates
        the file before raising an exception. This guarantees that
        plugins will not fail repeatedly when their state files get
        damaged.

        :returns: Cookie object (self)
        :raises ValueError: if the state file is corrupted or does not
            deserialize into a dict
        """
        self.fobj = self._create_fobj()
        flock_exclusive(self.fobj)
        if os.fstat(self.fobj.fileno()).st_size:
            try:
                self.data = self._load()
            except ValueError:
                self.fobj.truncate(0)
                raise
        return self

    def _create_fobj(self):
        if not self.path:
            return TemporaryFile(
                "w+", encoding="ascii", prefix="oblivious_cookie_", dir=None
            )
        # mode='a+' has problems with mixed R/W operation on Mac OS X
        try:
            return open(self.path, "r+", encoding="ascii")
        except IOError:
            return open(self.path, "w+", encoding="ascii")

    def _load(self) -> dict[str, typing.Any]:
        if not self.fobj:
            raise RuntimeError("file object is none")
        self.fobj.seek(0)
        data = json.load(self.fobj)
        if not isinstance(data, dict):
            raise ValueError(
                "format error: cookie does not contain dict", self.path, data
            )
        return typing.cast(dict[str, typing.Any], data)

    def close(self) -> None:
        """Closes a cookie and its underlying state file.

        This method has no effect if the cookie is already closed.
        Once the cookie is closed, any operation (like :meth:`commit`)
        will raise an exception.
        """
        if not self.fobj:
            return
        self.fobj.close()
        self.fobj = None

    def commit(self) -> None:
        """Persists the cookie's dict items in the state file.

        The cookies content is serialized as JSON string and saved to
        the state file. The buffers are flushed to ensure that the new
        content is saved in a durable way.
        """
        if not self.fobj:
            raise IOError("cannot commit closed cookie", self.path)
        self.fobj.seek(0)
        self.fobj.truncate()
        json.dump(self.data, self.fobj)
        self.fobj.write("\n")
        self.fobj.flush()
        os.fsync(self.fobj)


# logtail.py


class LogTail:
    """Access previously unseen parts of a growing file.

    LogTail builds on :class:`~.cookie.Cookie` to access new lines of a
    continuosly growing log file. It should be used as context manager that
    provides an iterator over new lines to the subordinate context. LogTail
    saves the last file position into the provided cookie object.
    As the path to the log file is saved in the cookie, several LogTail
    instances may share the same cookie.
    """

    path: str
    cookie: "Cookie"
    logfile: typing.Optional[io.BufferedIOBase] = None
    stat: typing.Optional[os.stat_result]

    def __init__(self, path: str, cookie: "Cookie") -> None:
        """Creates new LogTail context.

        :param path: path to the log file that is to be observed
        :param cookie: :class:`~.cookie.Cookie` object to save the last
            file position
        """
        self.path = os.path.abspath(path)
        self.cookie = cookie
        self.logfile = None
        self.stat = None

    def _seek_if_applicable(self, fileinfo: dict[str, typing.Any]) -> None:
        self.stat = os.stat(self.path)
        if (
            self.stat.st_ino == fileinfo.get("inode", -1)
            and self.stat.st_size >= fileinfo.get("pos", 0)
            and self.logfile is not None
        ):
            self.logfile.seek(fileinfo["pos"])

    def __enter__(self) -> typing.Generator[bytes, typing.Any, None]:
        """Seeks to the last seen position and reads new lines.

        The last file position is read from the cookie. If the log file
        has not been changed since the last invocation, LogTail seeks to
        that position and reads new lines. Otherwise, the position saved
        in the cookie is reset and LogTail reads from the beginning.
        After leaving the subordinate context, the new position is saved
        in the cookie and the cookie is closed.

        :yields: new lines as bytes strings
        """
        self.logfile = open(self.path, "rb")
        self.cookie.open()
        self._seek_if_applicable(self.cookie.get(self.path, {}))
        line = self.logfile.readline()
        while len(line):
            yield line
            line = self.logfile.readline()

    def __exit__(
        self,
        exc_type: typing.Optional[type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[TracebackType],
    ) -> None:
        if not exc_type and self.stat is not None and self.logfile is not None:
            self.cookie[self.path] = dict(
                inode=self.stat.st_ino, pos=self.logfile.tell()
            )
            self.cookie.commit()
        self.cookie.close()
        if self.logfile is not None:
            self.logfile.close()


# output.py


def filter_output(output: str, filtered: str) -> str:
    """Filters out characters from output"""
    for char in filtered:
        output = output.replace(char, "")
    return output


class Output:
    ILLEGAL = "|"

    logchan: StreamHandler[io.StringIO]
    verbose: int
    status: str
    out: list[str]
    warnings: list[str]
    longperfdata: list[str]

    def __init__(self, logchan: StreamHandler[io.StringIO], verbose: int = 0) -> None:
        self.logchan = logchan
        self.verbose = verbose
        self.status = ""
        self.out = []
        self.warnings = []
        self.longperfdata = []

    def add(self, check: "Check") -> None:
        self.status = self.format_status(check)
        if self.verbose == 0:
            perfdata = self.format_perfdata(check)
            if perfdata:
                self.status += " " + perfdata
        else:
            self.add_longoutput(check.verbose_str)
            self.longperfdata.append(self.format_perfdata(check, 79))

    def format_status(self, check: "Check"):
        if check.name:
            name_prefix = check.name.upper() + " "
        else:
            name_prefix = ""
        summary_str = check.summary_str.strip()
        return self._screen_chars(
            "{0}{1}{2}".format(
                name_prefix,
                str(check.state).upper(),
                " - " + summary_str if summary_str else "",
            ),
            "status line",
        )

    # Needs refactoring, but won't remove now because it's probably API-breaking
    # pylint: disable-next=unused-argument
    def format_perfdata(self, check: "Check", linebreak: typing.Any = None) -> str:
        if not check.perfdata:
            return ""
        out = " ".join(check.perfdata)
        return "| " + self._screen_chars(out, "perfdata")

    def add_longoutput(self, text: str | list[str] | tuple[str]) -> None:
        if isinstance(text, (list, tuple)):
            for line in text:
                self.add_longoutput(line)
        else:
            self.out.append(self._screen_chars(text, "long output"))

    def __str__(self):
        output = [
            elem
            for elem in [self.status]
            + self.out
            + [self._screen_chars(self.logchan.stream.getvalue(), "logging output")]
            + self.warnings
            + self.longperfdata
            if elem
        ]
        return "\n".join(output) + "\n"

    def _screen_chars(self, text: str, where: str) -> str:
        text = text.rstrip("\n")
        screened = filter_output(text, self.ILLEGAL)
        if screened != text:
            self.warnings.append(
                self._illegal_chars_warning(where, set(text) - set(screened))
            )
        return screened

    @staticmethod
    def _illegal_chars_warning(where: str, removed_chars: set[str]) -> str:
        hex_chars = ", ".join("0x{0:x}".format(ord(c)) for c in removed_chars)
        return "warning: removed illegal characters ({0}) from {1}".format(
            hex_chars, where
        )


# performance.py


def quote(label: str) -> str:
    if re.match(r"^\w+$", label):
        return label
    return f"'{label}'"


class Performance:
    """
    Performance data (perfdata) representation.

    :term:`Performance data` are created during metric evaluation in a context
    and are written into the *perfdata* section of the plugin's output.
    :class:`Performance` allows the creation of value objects that are passed
    between other mplugin objects.

    For sake of consistency, performance data should represent their values in
    their respective base unit, so `Performance('size', 10000, 'B')` is better
    than `Performance('size', 10, 'kB')`.
    https://github.com/monitoring-plugins/monitoring-plugin-guidelines/blob/main/monitoring_plugins_interface/03.Output.md#performance-data
    """

    label: str
    """short identifier, results in graph titles for example (20 chars or less recommended)"""

    value: typing.Any
    """measured value (usually an int, float, or bool)"""

    uom: typing.Optional[str]
    """unit of measure -- use base units whereever possible"""

    warn: typing.Optional["RangeSpec"]
    """warning range"""

    crit: typing.Optional["RangeSpec"]
    """critical range"""

    min: typing.Optional[float]
    """known value minimum (None for no minimum)"""

    max: typing.Optional[float]
    """known value maximum (None for no maximum)"""

    # Changing these now would be API-breaking, so we'll ignore these
    # shadowed built-ins and the long list of arguments
    # pylint: disable-next=redefined-builtin,too-many-arguments
    def __init__(
        self,
        label: str,
        value: typing.Any,
        uom: typing.Optional[str] = None,
        warn: typing.Optional["RangeSpec"] = None,
        crit: typing.Optional["RangeSpec"] = None,
        min: typing.Optional[float] = None,
        max: typing.Optional[float] = None,
    ) -> None:
        """Create new performance data object.

        :param label: short identifier, results in graph
            titles for example (20 chars or less recommended)
        :param value: measured value (usually an int, float, or bool)
        :param uom: unit of measure -- use base units whereever possible
        :param warn: warning range
        :param crit: critical range
        :param min: known value minimum (None for no minimum)
        :param max: known value maximum (None for no maximum)
        """
        if "'" in label or "=" in label:
            raise RuntimeError("label contains illegal characters", label)
        self.label = label
        self.value = value
        self.uom = uom
        self.warn = warn
        self.crit = crit
        self.min = min
        self.max = max

    def __str__(self) -> str:
        """String representation conforming to the plugin API.

        Labels containing spaces or special characters will be quoted.
        """

        performance: str = f"{quote(self.label)}={self.value}"

        if self.uom is not None:
            performance += self.uom

        out: list[str] = [performance]

        if self.warn is not None and self.warn != "" and self.warn != Range(""):
            out.append(str(self.warn))

        if self.crit is not None and self.crit != "" and self.crit != Range(""):
            out.append(str(self.crit))

        if self.min is not None:
            out.append(str(self.min))

        if self.max is not None:
            out.append(str(self.max))

        return ";".join(out)


# runtime.py

"""Functions and classes to interface with the system.

This module contains the :class:`Runtime` class that handles exceptions,
timeouts and logging. Plugin authors should not use Runtime directly,
but decorate the plugin's main function with :func:`~.runtime.guarded`.
"""

P = typing.ParamSpec("P")
R = typing.TypeVar("R")


def guarded(
    original_function: typing.Optional[typing.Callable[P, R]] = None,
    verbose: typing.Optional[int] = None,
) -> typing.Callable[P, R]:
    """Runs a function mplugin's Runtime environment.

    `guarded` makes the decorated function behave correctly with respect
    to the Nagios plugin API if it aborts with an uncaught exception or
    a timeout. It exits with an *unknown* exit code and prints a
    traceback in a format acceptable by Nagios.

    This function should be used as a decorator for the script's `main`
    function.

    :param verbose: Optional keyword parameter to control verbosity
        level during early execution (before
        :meth:`~mplugin.Check.main` has been called). For example,
        use `@guarded(verbose=0)` to turn tracebacks in that phase off.
    """

    def _decorate(func: typing.Callable[P, R]):
        @functools.wraps(func)
        # This inconsistent-return-statements error can be fixed by adding a
        # typing.NoReturn type hint to Runtime._handle_exception(), but we can't do
        # that as long as we're maintaining py27 compatability.
        # pylint: disable-next=inconsistent-return-statements
        def wrapper(*args: typing.Any, **kwds: typing.Any):
            runtime = Runtime()
            if verbose is not None:
                runtime.verbose = verbose
            try:
                return func(*args, **kwds)
            except Timeout as exc:
                runtime._handle_exception(  # type: ignore
                    "Timeout: check execution aborted after {0}".format(exc)
                )
            except Exception:
                runtime._handle_exception()  # type: ignore

        return wrapper

    if original_function is not None:
        assert callable(original_function), (
            'Function {!r} not callable. Forgot to add "verbose=" keyword?'.format(
                original_function
            )
        )
        return _decorate(original_function)
    return _decorate  # type: ignore


class Runtime:
    instance = None
    check: typing.Optional["Check"] = None
    _verbose = 1
    timeout: typing.Optional[int] = None
    logchan: logging.StreamHandler[io.StringIO]
    output: Output
    stdout = None
    exitcode: int = 70  # EX_SOFTWARE

    def __new__(cls) -> typing_extensions.Self:
        if not cls.instance:
            cls.instance = super(Runtime, cls).__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        rootlogger = logging.getLogger(__name__.split(".", 1)[0])
        rootlogger.setLevel(logging.DEBUG)
        self.logchan = logging.StreamHandler(io.StringIO())
        self.logchan.setFormatter(logging.Formatter("%(message)s"))
        rootlogger.addHandler(self.logchan)
        self.output = Output(self.logchan)

    def _handle_exception(
        self, statusline: typing.Optional[str] = None
    ) -> typing.NoReturn:
        exc_type, value = sys.exc_info()[0:2]
        name = self.check.name.upper() + " " if self.check else ""
        self.output.status = "{0}UNKNOWN: {1}".format(
            name,
            statusline or traceback.format_exception_only(exc_type, value)[0].strip(),
        )
        if self.verbose > 0:
            self.output.add_longoutput(traceback.format_exc())
        print("{0}".format(self.output), end="", file=self.stdout)
        self.exitcode = 3
        self.sysexit()

    @property
    def verbose(self) -> int:
        return self._verbose

    @verbose.setter
    def verbose(self, verbose: typing.Any) -> None:
        if isinstance(verbose, int):
            self._verbose = verbose
        elif isinstance(verbose, float):
            self._verbose = int(verbose)
        else:
            self._verbose = len(verbose or [])
        if self._verbose >= 3:
            self.logchan.setLevel(logging.DEBUG)
            self._verbose = 3
        elif self._verbose == 2:
            self.logchan.setLevel(logging.INFO)
        else:
            self.logchan.setLevel(logging.WARNING)
        self.output.verbose = self._verbose

    def run(self, check: "Check") -> None:
        check()
        self.output.add(check)
        self.exitcode = check.exitcode

    def execute(
        self, check: "Check", verbose: typing.Any = None, timeout: typing.Any = None
    ) -> typing.NoReturn:
        self.check = check
        if verbose is not None:
            self.verbose = verbose
        if timeout is not None:
            self.timeout = int(timeout)
        if self.timeout:
            with_timeout(self.timeout, self.run, check)
        else:
            self.run(check)
        print("{0}".format(self.output), end="", file=self.stdout)
        self.sysexit()

    def sysexit(self) -> typing.NoReturn:
        sys.exit(self.exitcode)


# metric.py

"""Structured representation for data points.

This module contains the :class:`Metric` class whose instances are
passed as value objects between most of mplugin's core classes.
Typically, :class:`~.resource.Resource` objects emit a list of metrics
as result of their :meth:`~.resource.Resource.probe` methods.
"""


class MetricKwargs(typing.TypedDict, total=False):
    name: str
    value: typing.Any
    uom: str
    min: float
    max: float
    context: str
    contextobj: "Context"
    resource: "Resource"


class Metric:
    """Single measured value.

    The value should be expressed in terms of base units, so
    Metric('swap', 10240, 'B') is better than Metric('swap', 10, 'kiB').
    """

    name: str
    value: typing.Any
    uom: typing.Optional[str] = None
    min: typing.Optional[float] = None
    max: typing.Optional[float] = None
    context: str
    contextobj: typing.Optional["Context"] = None
    resource: typing.Optional["Resource"] = None

    # Changing these now would be API-breaking, so we'll ignore these
    # shadowed built-ins
    # pylint: disable-next=redefined-builtin
    def __init__(
        self,
        name: str,
        value: typing.Any,
        uom: typing.Optional[str] = None,
        min: typing.Optional[float] = None,
        max: typing.Optional[float] = None,
        context: typing.Optional[str] = None,
        contextobj: typing.Optional["Context"] = None,
        resource: typing.Optional["Resource"] = None,
    ) -> None:
        """Creates new Metric instance.

        :param name: short internal identifier for the value -- appears
            also in the performance data
        :param value: data point, usually has a boolen or numeric type,
            but other types are also possible
        :param uom: :term:`unit of measure`, preferrably as ISO
            abbreviation like "s"
        :param min: minimum value or None if there is no known minimum
        :param max: maximum value or None if there is no known maximum
        :param context: name of the associated context (defaults to the
            metric's name if left out)
        :param contextobj: reference to the associated context object
            (set automatically by :class:`~mplugin.check.Check`)
        :param resource: reference to the originating
            :class:`~mplugin.Resource` (set automatically
            by :class:`~mplugin.check.Check`)
        """
        self.name = name
        self.value = value
        self.uom = uom
        self.min = min
        self.max = max
        if context is not None:
            self.context = context
        else:
            self.context = name
        self.contextobj = contextobj
        self.resource = resource

    def __str__(self):
        """Same as :attr:`valueunit`."""
        return self.valueunit

    def replace(
        self, **attr: typing_extensions.Unpack[MetricKwargs]
    ) -> typing_extensions.Self:
        """Creates new instance with updated attributes."""
        for key, value in attr.items():
            setattr(self, key, value)
        return self

    @property
    def description(self):
        """Human-readable, detailed string representation.

        Delegates to the :class:`~.context.Context` to format the value.

        :returns: :meth:`~.context.Context.describe` output or
            :attr:`valueunit` if no context has been associated yet
        """
        if self.contextobj:
            return self.contextobj.describe(self)
        return str(self)

    @property
    def valueunit(self) -> str:
        """Compact string representation.

        This is just the value and the unit. If the value is a real
        number, express the value with a limited number of digits to
        improve readability.
        """
        return "%s%s" % (self._human_readable_value, self.uom or "")

    @property
    def _human_readable_value(self) -> str:
        """Limit number of digits for floats."""
        if isinstance(self.value, numbers.Real) and not isinstance(
            self.value, numbers.Integral
        ):
            return "%.4g" % self.value
        return str(self.value)

    def evaluate(self) -> typing.Union["Result", "ServiceState"]:
        """Evaluates this instance according to the context.

        :return: :class:`~mplugin.Result` object
        :raise RuntimeError: if no context has been associated yet
        """
        if not self.contextobj:
            raise RuntimeError("no context set for metric", self.name)
        if not self.resource:
            raise RuntimeError("no resource set for metric", self.name)
        return self.contextobj.evaluate(self, self.resource)

    def performance(self) -> typing.Optional[Performance]:
        """Generates performance data according to the context.

        :return: :class:`~mplugin.performance.Performance` object
        :raise RuntimeError: if no context has been associated yet
        """
        if not self.contextobj:
            raise RuntimeError("no context set for metric", self.name)
        if not self.resource:
            raise RuntimeError("no resource set for metric", self.name)
        return self.contextobj.performance(self, self.resource)


# resource.py

"""Domain model for data :term:`acquisition`.

:class:`Resource` is the base class for the plugin's :term:`domain
model`. It shoul model the relevant details of reality that a plugin is
supposed to check. The :class:`~.check.Check` controller calls
:meth:`Resource.probe` on all passed resource objects to acquire data.

Plugin authors should subclass :class:`Resource` and write
whatever methods are needed to get the interesting bits of information.
The most important resource subclass should be named after the plugin
itself.
"""


class Resource:
    """Abstract base class for custom domain models.

    Subclasses may add arguments to the constructor to parametrize
    information retrieval.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    # This could be corrected by re-implementing this class as a proper ABC.
    # See issue #42
    # pylint: disable=no-self-use
    def probe(
        self,
    ) -> typing.Union[list["Metric"], "Metric", typing.Generator["Metric", None, None]]:
        """Query system state and return metrics.

        This is the only method called by the check controller.
        It should trigger all necessary actions and create metrics.

        :return: list of :class:`~mplugin.Metric` objects,
            or generator that emits :class:`~mplugin.Metric`
            objects, or single :class:`~mplugin.Metric`
            object
        """
        return []


# result.py

"""Outcomes from evaluating metrics in contexts.

The :class:`Result` class is the base class for all evaluation results.
The :class:`Results` class (plural form) provides a result container with
access functions and iterators.

Plugin authors may create their own :class:`Result` subclass to
accomodate for special needs. :class:`~.context.Context` constructors
accept custom Result subclasses in the `result_cls` parameter.
"""


class Result:
    """Evaluation outcome consisting of state and explanation.

    A Result object is typically emitted by a
    :class:`~mplugin.Context` object and represents the
    outcome of an evaluation. It contains a
    :class:`~mplugin.state.ServiceState` as well as an explanation.
    Plugin authors may subclass Result to implement specific features.
    """

    state: "ServiceState"

    hint: typing.Optional[str]

    metric: typing.Optional["Metric"]

    def __init__(
        self,
        state: "ServiceState",
        hint: typing.Optional[str] = None,
        metric: typing.Optional["Metric"] = None,
    ) -> None:
        self.state = state
        self.hint = hint
        self.metric = metric

    def __str__(self) -> str:
        """Textual result explanation.

        The result explanation is taken from :attr:`metric.description`
        (if a metric has been passed to the constructur), followed
        optionally by the value of :attr:`hint`. This method's output
        should consist only of a text for the reason but not for the
        result's state. The latter is rendered independently.

        :returns: result explanation or empty string
        """
        if self.metric and self.metric.description:
            desc = self.metric.description
        else:
            desc = None

        if self.hint and desc:
            return "{0} ({1})".format(desc, self.hint)
        if self.hint:
            return self.hint
        if desc:
            return desc
        return ""

    @property
    def resource(self) -> typing.Optional["Resource"]:
        """Reference to the resource used to generate this result."""
        if not self.metric:
            return None
        return self.metric.resource

    @property
    def context(self) -> typing.Optional["Context"]:
        """Reference to the metric used to generate this result."""
        if not self.metric:
            return None
        return self.metric.contextobj

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Result):
            return False
        return (
            self.state == value.state
            and self.hint == value.hint
            and self.metric == value.metric
        )


class Results:
    """Container for result sets.

    Basically, this class manages a set of results and provides
    convenient access methods by index, name, or result state. It is
    meant to make queries in :class:`~.summary.Summary`
    implementations compact and readable.

    The constructor accepts an arbitrary number of result objects and
    adds them to the container.
    """

    results: list[Result]
    by_state: dict["ServiceState", list[Result]]
    by_name: dict[str, Result]

    def __init__(self, *results: Result) -> None:
        self.results = []
        self.by_state = collections.defaultdict(list)
        self.by_name = {}
        if results:
            self.add(*results)

    def add(self, *results: Result):
        """Adds more results to the container.

        Besides passing :class:`Result` objects in the constructor,
        additional results may be added after creating the container.

        :raises ValueError: if `result` is not a :class:`Result` object
        """
        for result in results:
            if not isinstance(result, Result):  # type: ignore
                raise ValueError(
                    "trying to add non-Result to Results container", result
                )
            self.results.append(result)
            self.by_state[result.state].append(result)
            try:
                self.by_name[result.metric.name] = result  # type: ignore
            except AttributeError:
                pass
        return self

    def __iter__(self):
        """Iterates over all results.

        The iterator is sorted in order of decreasing state
        significance (unknown > critical > warning > ok).

        :returns: result object iterator
        """
        for state in reversed(sorted(self.by_state)):
            for result in self.by_state[state]:
                yield result

    def __len__(self):
        """Number of results in this container."""
        return len(self.results)

    def __getitem__(self, item: typing.Union[int, str]) -> Result:
        """Access result by index or name.

        If *item* is an integer, the itemth element in the
        container is returned. If *item* is a string, it is used to
        look up a result with the given name.

        :returns: :class:`Result` object
        :raises KeyError: if no matching result is found
        """
        if isinstance(item, int):
            return self.results[item]
        return self.by_name[item]

    def __contains__(self, name: str) -> bool:
        """Tests if a result with given name is present.

        :returns: boolean
        """
        return name in self.by_name

    @property
    def most_significant_state(self) -> "ServiceState":
        """The "worst" state found in all results.

        :returns: :obj:`~mplugin.state.ServiceState` object
        :raises ValueError: if no results are present
        """
        return max(self.by_state.keys())

    @property
    def most_significant(self) -> list[Result]:
        """Returns list of results with most significant state.

        From all results present, a subset with the "worst" state is
        selected.

        :returns: list of :class:`Result` objects or empty list if no
            results are present
        """
        try:
            return self.by_state[self.most_significant_state]
        except ValueError:
            return []

    @property
    def first_significant(self) -> Result:
        """Selects one of the results with most significant state.

        :returns: :class:`Result` object
        :raises IndexError: if no results are present
        """
        return self.most_significant[0]


# summary.py

"""Create status line from results.

This module contains the :class:`Summary` class which serves as base
class to get a status line from the check's :class:`~.result.Results`. A
Summary object is used by :class:`~.check.Check` to obtain a suitable data
:term:`presentation` depending on the check's overall state.

Plugin authors may either stick to the default implementation or subclass it
to adapt it to the check's domain. The status line is probably the most
important piece of text returned from a check: It must lead directly to the
problem in the most concise way. So while the default implementation is quite
usable, plugin authors should consider subclassing to provide a specific
implementation that gets the output to the point.
"""


class Summary:
    """Creates a summary formatter object.

    This base class takes no parameters in its constructor, but subclasses may
    provide more elaborate constructors that accept parameters to influence
    output creation.
    """

    # It might be possible to re-implement this as a @staticmethod,
    # but this might be an API-breaking change, so it should probably stay in
    # place until a 2.x rewrite.  If this can't be a @staticmethod, then it
    # should probably be an @abstractmethod.
    # See issue #44
    # pylint: disable-next=no-self-use
    def ok(self, results: "Results") -> str:
        """Formats status line when overall state is ok.

        The default implementation returns a string representation of
        the first result.

        :param results: :class:`~mplugin.Results` container
        :returns: status line
        """
        return "{0}".format(results[0])

    # It might be possible to re-implement this as a @staticmethod,
    # but this might be an API-breaking change, so it should probably stay in
    # place until a 2.x rewrite.  If this can't be a @staticmethod, then it
    # should probably be an @abstractmethod.
    # See issue #44
    # pylint: disable-next=no-self-use
    def problem(self, results: "Results") -> str:
        """Formats status line when overall state is not ok.

        The default implementation returns a string representation of te
        first significant result, i.e. the result with the "worst"
        state.

        :param results: :class:`~.result.Results` container
        :returns: status line
        """
        return "{0}".format(results.first_significant)

    # It might be possible to re-implement this as a @staticmethod,
    # but this might be an API-breaking change, so it should probably stay in
    # place until a 2.x rewrite.  If this can't be a @staticmethod, then it
    # should probably be an @abstractmethod.
    # See issue #44
    # pylint: disable-next=no-self-use
    def verbose(self, results: "Results") -> list[str]:
        """Provides extra lines if verbose plugin execution is requested.

        The default implementation returns a list of all resources that are in
        a non-ok state.

        :param results: :class:`~.result.Results` container
        :returns: list of strings
        """
        msgs: list[str] = []
        for result in results:
            if result.state == ok:
                continue
            msgs.append("{0}: {1}".format(result.state, result))
        return msgs

    # It might be possible to re-implement this as a @staticmethod,
    # but this might be an API-breaking change, so it should probably stay in
    # place until a 2.x rewrite.  If this can't be a @staticmethod, then it
    # should probably be an @abstractmethod.
    # See issue #44
    # pylint: disable-next=no-self-use
    def empty(self) -> typing.Literal["no check results"]:
        """Formats status line when the result set is empty.

        :returns: status line
        """
        return "no check results"


# context.py

"""Metadata about metrics to perform data :term:`evaluation`.

This module contains the :class:`Context` class, which is the base for
all contexts. :class:`ScalarContext` is an important specialization to
cover numeric contexts with warning and critical thresholds. The
:class:`~.check.Check` controller selects a context for each
:class:`~.metric.Metric` by matching the metric's `context` attribute with the
context's `name`. The same context may be used for several metrics.

Plugin authors may just use to :class:`ScalarContext` in the majority of cases.
Sometimes is better to subclass :class:`Context` instead to implement custom
evaluation or performance data logic.
"""


FmtMetric = str | typing.Callable[["Metric", "Context"], str]


class Context:
    name: str
    fmt_metric: typing.Optional[FmtMetric]
    result_cls: type[Result]

    def __init__(
        self,
        name: str,
        fmt_metric: typing.Optional[FmtMetric] = None,
        result_cls: type[Result] = Result,
    ) -> None:
        """Creates generic context identified by `name`.

        Generic contexts just format associated metrics and evaluate
        always to :obj:`~mplugin.ok`. Metric formatting is
        controlled with the :attr:`fmt_metric` attribute. It can either
        be a string or a callable. See the :meth:`describe` method for
        how formatting is done.

        :param name: A context name that is matched by the context
            attribute of :class:`~mplugin.Metric`
        :param fmt_metric: string or callable to convert
            context and associated metric to a human readable string
        :param result_cls: use this class (usually a
            :class:`~.result.Result` subclass) to represent the
            evaluation outcome
        """
        self.name = name
        self.fmt_metric = fmt_metric
        self.result_cls = result_cls

    def evaluate(
        self, metric: "Metric", resource: "Resource"
    ) -> typing.Union[Result, ServiceState]:
        """Determines state of a given metric.

        This base implementation returns :class:`~mplugin.ok`
        in all cases. Plugin authors may override this method in
        subclasses to specialize behaviour.

        :param metric: associated metric that is to be evaluated
        :param resource: resource that produced the associated metric
            (may optionally be consulted)
        :returns: :class:`~.result.Result` or
            :class:`~.state.ServiceState` object
        """
        return self.result_cls(ok, metric=metric)

    def ok(
        self,
        hint: typing.Optional[str] = None,
        metric: typing.Optional["Metric"] = None,
    ) -> Result:
        return Result(ok, hint=hint, metric=metric)

    def warn(
        self,
        hint: typing.Optional[str] = None,
        metric: typing.Optional["Metric"] = None,
    ) -> Result:
        return Result(warn, hint=hint, metric=metric)

    def critical(
        self,
        hint: typing.Optional[str] = None,
        metric: typing.Optional["Metric"] = None,
    ) -> Result:
        return Result(critical, hint=hint, metric=metric)

    def unknown(
        self,
        hint: typing.Optional[str] = None,
        metric: typing.Optional["Metric"] = None,
    ) -> Result:
        return Result(unknown, hint=hint, metric=metric)

    # This could be corrected by re-implementing this class as a proper ABC.
    # See issue #43
    # pylint: disable-next=no-self-use
    def performance(
        self, metric: "Metric", resource: "Resource"
    ) -> typing.Optional[Performance]:
        """Derives performance data from a given metric.

        This base implementation just returns none. Plugin authors may
        override this method in subclass to specialize behaviour.

        :param metric: associated metric from which performance data are
            derived
        :param resource: resource that produced the associated metric
            (may optionally be consulted)
        :returns: :class:`~.performance.Performance` object or `None`
        """
        return None

    def describe(self, metric: "Metric") -> typing.Optional[str]:
        """Provides human-readable metric description.

        Formats the metric according to the :attr:`fmt_metric`
        attribute. If :attr:`fmt_metric` is a string, it is evaluated as
        format string with all metric attributes in the root namespace.
        If :attr:`fmt_metric` is callable, it is called with the metric
        and this context as arguments. If :attr:`fmt_metric` is not set,
        this default implementation does not return a description.

        Plugin authors may override this method in subclasses to control
        text output more tightly.

        :param metric: associated metric
        :returns: description string or None
        """
        if not self.fmt_metric:
            return None

        if isinstance(self.fmt_metric, str):
            return self.fmt_metric.format(
                name=metric.name,
                value=metric.value,
                uom=metric.uom,
                valueunit=metric.valueunit,
                min=metric.min,
                max=metric.max,
            )

        return self.fmt_metric(metric, self)


class ScalarContext(Context):
    warn_range: Range

    critical_range: Range

    def __init__(
        self,
        name: str,
        warning: typing.Optional[RangeSpec] = None,
        critical: typing.Optional[RangeSpec] = None,
        fmt_metric: FmtMetric = "{name} is {valueunit}",
        result_cls: type[Result] = Result,
    ) -> None:
        """Ready-to-use :class:`Context` subclass for scalar values.

        ScalarContext models the common case where a single scalar is to
        be evaluated against a pair of warning and critical thresholds.

        :attr:`name`, :attr:`fmt_metric`, and :attr:`result_cls`,
        are described in the :class:`Context` base class.

        :param warning: Warning threshold as
            :class:`~mplugin.Range` object or range string.
        :param critical: Critical threshold as
            :class:`~mplugin.Range` object or range string.
        """
        super(ScalarContext, self).__init__(name, fmt_metric, result_cls)
        self.warn_range = Range(warning)
        self.critical_range = Range(critical)

    def evaluate(self, metric: "Metric", resource: "Resource") -> Result:
        """Compares metric with ranges and determines result state.

        The metric's value is compared to the instance's :attr:`warning`
        and :attr:`critical` ranges, yielding an appropropiate state
        depending on how the metric fits in the ranges. Plugin authors
        may override this method in subclasses to provide custom
        evaluation logic.

        :param metric: metric that is to be evaluated
        :param resource: not used
        :returns: :class:`~mplugin.Result` object
        """
        if not self.critical_range.match(metric.value):
            return self.result_cls(critical, self.critical_range.violation, metric)
        if not self.warn_range.match(metric.value):
            return self.result_cls(warn, self.warn_range.violation, metric)
        return self.result_cls(ok, None, metric)

    def performance(self, metric: "Metric", resource: "Resource") -> Performance:
        """Derives performance data.

        The metric's attributes are combined with the local
        :attr:`warning` and :attr:`critical` ranges to get a
        fully populated :class:`~mplugin.performance.Performance`
        object.

        :param metric: metric from which performance data are derived
        :param resource: not used
        :returns: :class:`~mplugin.performance.Performance` object
        """
        return Performance(
            metric.name,
            metric.value,
            metric.uom,
            self.warn_range,
            self.critical_range,
            metric.min,
            metric.max,
        )


class Contexts:
    """Container for collecting all generated contexts."""

    by_name: dict[str, Context]

    def __init__(self) -> None:
        self.by_name = dict(
            default=ScalarContext("default", "", ""), null=Context("null")
        )

    def add(self, context: Context) -> None:
        self.by_name[context.name] = context

    def __getitem__(self, context_name: str) -> Context:
        try:
            return self.by_name[context_name]
        except KeyError:
            raise KeyError(
                "cannot find context",
                context_name,
                "known contexts: {0}".format(", ".join(self.by_name.keys())),
            )

    def __contains__(self, context_name: str) -> bool:
        return context_name in self.by_name

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self.by_name)


# check.py

"""Controller logic for check execution.

This module contains the :class:`Check` class which orchestrates the
the various stages of check execution. Interfacing with the
outside system is done via a separate :class:`Runtime` object.

When a check is called (using :meth:`Check.main` or
:meth:`Check.__call__`), it probes all resources and evaluates the
returned metrics to results and performance data. A typical usage
pattern would be to populate a check with domain objects and then
delegate control to it.
"""


_log = logging.getLogger(__name__)


class Check:
    resources: list[Resource]
    contexts: Contexts
    summary: Summary
    results: Results
    perfdata: list[str]
    name: str

    def __init__(
        self,
        *objects: Resource | Context | Summary | Results,
        name: typing.Optional[str] = None,
    ) -> None:
        """Creates and configures a check.

        Specialized *objects* representing resources, contexts,
        summary, or results are passed to the the :meth:`add` method.
        Alternatively, objects can be added later manually.
        If no *name* is given, the output prefix is set to the first
        resource's name. If *name* is None, no prefix is set at all.
        """
        self.resources = []
        self.contexts = Contexts()
        self.summary = Summary()
        self.results = Results()
        self.perfdata = []
        if name is not None:
            self.name = name
        else:
            self.name = ""
        self.add(*objects)

    def add(self, *objects: Resource | Context | Summary | Results):
        """Adds domain objects to a check.

        :param objects: one or more objects that are descendants from
            :class:`~mplugin.Resource`,
            :class:`~mplugin.Context`,
            :class:`~mplugin.Summary`, or
            :class:`~mplugin.Results`.
        """
        for obj in objects:
            if isinstance(obj, Resource):
                self.resources.append(obj)
                if self.name is None:  # type: ignore
                    self.name = ""
                elif self.name == "":
                    self.name = self.resources[0].name
            elif isinstance(obj, Context):
                self.contexts.add(obj)
            elif isinstance(obj, Summary):
                self.summary = obj
            elif isinstance(obj, Results):  # type: ignore
                self.results = obj
            else:
                raise TypeError("cannot add type {0} to check".format(type(obj)), obj)
        return self

    def _evaluate_resource(self, resource: Resource) -> None:
        metric = None
        try:
            metrics = resource.probe()
            if not metrics:
                _log.warning("resource %s did not produce any metric", resource.name)
            if isinstance(metrics, Metric):
                # resource returned a bare metric instead of list/generator
                metrics = [metrics]
            for metric in metrics:
                context = self.contexts[metric.context]
                metric = metric.replace(contextobj=context, resource=resource)
                result = metric.evaluate()
                if isinstance(result, Result):
                    self.results.add(result)
                elif isinstance(result, ServiceState):  # type: ignore
                    self.results.add(Result(result, metric=metric))
                else:
                    raise ValueError(
                        "evaluate() returned neither Result nor ServiceState object",
                        metric.name,
                        result,
                    )
                self.perfdata.append(str(metric.performance() or ""))
        except CheckError as e:
            self.results.add(Result(unknown, str(e), metric))

    def __call__(self) -> None:
        """Actually run the check.

        After a check has been called, the :attr:`results` and
        :attr:`perfdata` attributes are populated with the outcomes. In
        most cases, you should not use __call__ directly but invoke
        :meth:`main`, which delegates check execution to the
        :class:`Runtime` environment.
        """
        for resource in self.resources:
            self._evaluate_resource(resource)
        self.perfdata = sorted([p for p in self.perfdata if p])

    def main(
        self, verbose: typing.Any = None, timeout: typing.Any = None
    ) -> typing.NoReturn:
        """All-in-one control delegation to the runtime environment.

        Get a :class:`~mplugin.runtime.Runtime` instance and
        perform all phases: run the check (via :meth:`__call__`), print
        results and exit the program with an appropriate status code.

        :param verbose: output verbosity level between 0 and 3
        :param timeout: abort check execution with a :exc:`Timeout`
            exception after so many seconds (use 0 for no timeout)
        """
        runtime = Runtime()
        runtime.execute(self, verbose, timeout)

    @property
    def state(self) -> ServiceState:
        """Overall check state.

        The most significant (=worst) state seen in :attr:`results` to
        far. :obj:`~mplugin.unknown` if no results have been
        collected yet. Corresponds with :attr:`exitcode`. Read-only
        property.
        """
        try:
            return self.results.most_significant_state
        except ValueError:
            return unknown

    @property
    def summary_str(self) -> str:
        """Status line summary string.

        The first line of output that summarizes that situation as
        perceived by the check. The string is usually queried from a
        :class:`Summary` object. Read-only property.
        """
        if not self.results:
            return self.summary.empty() or ""

        if self.state == ok:
            return self.summary.ok(self.results) or ""

        return self.summary.problem(self.results) or ""

    @property
    def verbose_str(self):
        """Additional lines of output.

        Long text output if check runs in verbose mode. Also queried
        from :class:`~mplugin.Summary`. Read-only property.
        """
        return self.summary.verbose(self.results) or ""

    @property
    def exitcode(self) -> int:
        """Overall check exit code according to the Nagios API.

        Corresponds with :attr:`state`. Read-only property.
        """
        try:
            return int(self.results.most_significant_state)
        except ValueError:
            return 3


class __CustomArgumentParser(argparse.ArgumentParser):
    """
    Override the exit method for the options ``--help``, ``-h`` and ``--version``,
    ``-V`` with ``Unknown`` (exit code 3), according to the
    `Monitoring Plugin Guidelines
    <https://github.com/monitoring-plugins/monitoring-plugin-guidelines/blob/main/monitoring_plugins_interface/02.Input.md>`__.
    """

    def exit(
        self, status: int = 3, message: typing.Optional[str] = None
    ) -> typing.NoReturn:
        if message:
            self._print_message(message, sys.stderr)
        sys.exit(status)


def setup_argparser(
    name: typing.Optional[str],
    version: typing.Optional[str] = None,
    license: typing.Optional[str] = None,
    repository: typing.Optional[str] = None,
    copyright: typing.Optional[str] = None,
    description: typing.Optional[str] = None,
    epilog: typing.Optional[str] = None,
) -> argparse.ArgumentParser:
    """
    Set up and configure an argument parser for a monitoring plugin
    according the
    `Monitoring Plugin Guidelines
    <https://github.com/monitoring-plugins/monitoring-plugin-guidelines/blob/main/monitoring_plugins_interface/02.Input.md>`__.

    This function creates a customized ArgumentParser instance with metadata
    and formatting suitable for monitoring plugins. It automatically prefixes
    the plugin name with ``check_`` if not already present.

    :param name: The name of the plugin. If provided and doesn't start with
        ``check``, it will be prefixed with ``check_``.
    :param version: The version number of the plugin. If provided, it will be
        included in the parser description.
    :param license: The license type of the plugin. If provided, it will be
        included in the parser description.
    :param repository: The repository URL of the plugin. If provided, it will
        be included in the parser description.
    :param copyright: The copyright information for the plugin. If provided,
        it will be included in the parser description.
    :param description: A detailed description of the plugin's functionality.
        If provided, it will be appended to the parser description after a
        blank line.
    :param epilog: Additional information to display after the help message.

    :returns: A configured ArgumentParser instance with RawDescriptionHelpFormatter,
        80 character width, and metadata assembled from the provided parameters.
    """
    description_lines: list[str] = []

    if name is not None and not name.startswith("check"):
        name = f"check_{name}"

    if version is not None:
        description_lines.append(f"version {version}")

    if license is not None:
        description_lines.append(f"Licensed under the {license}.")

    if repository is not None:
        description_lines.append(f"Repository: {repository}.")

    if copyright is not None:
        description_lines.append(copyright)

    if description is not None:
        description_lines.append("")
        description_lines.append(description)

    parser: argparse.ArgumentParser = __CustomArgumentParser(
        prog=name,
        formatter_class=lambda prog: argparse.RawDescriptionHelpFormatter(
            prog, width=80
        ),
        description="\n".join(description_lines),
        epilog=epilog,
    )

    if version is not None:
        parser.add_argument(
            "-V",
            "--version",
            action="version",
            version=f"%(prog)s {version}",
        )

    return parser
