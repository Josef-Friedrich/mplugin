"""
.. role:: python(code)
   :language: python
"""

from __future__ import annotations

import collections
import functools
import importlib
import io
import logging
import numbers
import os
import re
import sys
import traceback
import typing
from importlib import metadata
from logging import StreamHandler

import typing_extensions

__version__: str = metadata.version("mplugin")


# from error.py: Exceptions with special meanings for mplugin.


class CheckError(RuntimeError):
    """Abort check execution.

    This exception should be raised if a plugin is unable to determine the
    system status. Raising this exception will cause the plugin to display the
    exception’s argument and exit with an ``UNKNOWN`` (``3``) status.
    """

    pass


class Timeout(RuntimeError):
    """Maximum check run time exceeded.

    This exception is raised internally by ``mplugin`` if the runtime check takes
    longer than allowed. The check is aborted and the plugin exits with an
    ``UNKNOWN`` (``3``) status.
    """

    pass


# state.py

"""Classes to represent check outcomes.

This module defines :class:`ServiceState` which is the abstract base class
for check outcomes. The four states defined by the :term:`Monitoring plugin API`
are represented as singleton subclasses.
"""


def worst(states: list["ServiceState"]) -> "ServiceState":
    """Reduce list of *states* to the most significant state."""
    return functools.reduce(lambda a, b: a if a > b else b, states, ok)


class ServiceState:
    """Abstract base class for all states.

    Each state has two constant attributes:

    - :attr:`code` is the corresponding exit code.
    - :attr:`text` is the short text representation which is printed for
      example at the beginning of the summary line.

    :param code: The Plugin API compliant exit code. Must be ``0``, ``1``, ``2`` or ``3``.
    :param text: The short text representation that is printed, for example, at
        the beginning of the summary line.
    """

    code: int
    """The Plugin API compliant exit code. Must be ``0``, ``1``, ``2`` or ``3``."""

    text: str
    """The short text representation that is printed, for example, at
    the beginning of the summary line."""

    def __init__(self, code: int, text: str) -> None:
        self.code = code
        self.text = text

    def __str__(self) -> str:
        """Plugin-API compliant text representation."""
        return self.text

    def __int__(self) -> int:
        """The Plugin API compliant exit code."""
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


ok: ServiceState = ServiceState(0, "ok")
"""The plugin was able to check the service and it appeared to be functioning
properly."""


warning: ServiceState = ServiceState(1, "warning")
"""
The plugin was able to check the service, but it appeared to be above some
``warning`` threshold or did not appear to be working properly."""


critical: ServiceState = ServiceState(2, "critical")
"""The plugin detected that either the service was not running or it was above
some ``critical`` threshold."""


unknown: ServiceState = ServiceState(3, "unknown")
"""Invalid command line arguments were supplied to the plugin or low-level
failures internal to the plugin (such as unable to fork, or open a tcp socket)
that prevent it from performing the specified operation. Higher-level errors
(such as name resolution errors, socket timeouts, etc) are outside of the control
of plugins and should generally NOT be reported as ``unknown`` states.

The ``--help`` or ``--version`` output should also result in ``unknown`` state."""


def state(exit_code: int) -> ServiceState:
    """
    Convert an exit code to a ServiceState.

    :param exit_code: The exit code to convert. Must be ``0``, ``1``, ``2`` or ``3``.

    :return: The corresponding ServiceState (``ok``, ``warn``, ``critical``, or ``unknown``).

    :raises CheckError: If exit_code is greater than 3.
    """
    if exit_code == 0:
        return ok
    elif exit_code == 1:
        return warning
    elif exit_code == 2:
        return critical
    elif exit_code == 3:
        return unknown
    raise CheckError(f"Exit code {exit_code} is > 3")


# from range.py:


RangeSpec = typing.Union[str, int, float, "Range"]


class Range:
    """Represents a threshold range.

    The general format is ``[@][start:][end]``. ``start:`` may be omitted if
    ``start==0``. ``~:`` means that start is negative infinity. If ``end`` is
    omitted, infinity is assumed. To invert the match condition, prefix
    the range expression with ``@``.

    .. seealso::

        See the
        `Monitoring Plugin Guidelines Repository <https://github.com/monitoring-plugins/monitoring-plugin-guidelines/blob/main/definitions/01.range_expressions.md>`__
        or the
        `Monitoring Plugins Development Guidelines <https://www.monitoring-plugins.org/doc/guidelines.html#THRESHOLDFORMAT>`__
        for details.

    :param spec: may be either a string, a float, or another
        Range object.
    :param invert: If the true, the value exceeds the threshold if it is
        INSIDE the range between start and end (including the endpoints).
    :param start: The (inclusive) start point on a numeric scale (possibly
        negative or negative infinity).
    :param end: The (inclusive) end point on a numeric scale (possibly
        negative or positive infinity).
    """

    invert: bool
    """If the true, the value exceeds the threshold if it is INSIDE the range
    between start and end (including the endpoints)."""

    start: float
    """The (inclusive) start point on a numeric scale (possibly negative or
    negative infinity)."""

    end: float
    """The (inclusive) end point on a numeric scale (possibly negative or
    positive infinity)."""

    def __init__(
        self,
        spec: typing.Optional[RangeSpec] = None,
        invert: typing.Optional[bool] = None,
        start: typing.Optional[float] = None,
        end: typing.Optional[float] = None,
    ) -> None:
        """Creates a Range object according to `spec`."""

        if spec is not None and not (invert is None and start is None and end is None):
            raise ValueError("Specify spec OR invert, start, end! not both")

        if isinstance(spec, Range):
            self.invert = spec.invert
            self.start = spec.start
            self.end = spec.end

        elif isinstance(spec, int) or isinstance(spec, float):
            self.invert = False
            self.start = 0
            self.end = spec

        elif spec is None and not (invert is None and start is None and end is None):
            if invert is not None:
                self.invert = invert
            else:
                self.invert = False

            if start is not None:
                self.start = start
            else:
                self.start = 0

            if end is not None:
                self.end = end
            else:
                self.end = float("inf")
        else:
            if spec is None:
                spec = ""
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


# output.py


def _filter_output(output: str, filtered: str) -> str:
    """Filters out characters from output"""
    for char in filtered:
        output = output.replace(char, "")
    return output


class _Output:
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
            self.longperfdata.append(self.format_perfdata(check))

    def format_status(self, check: "Check") -> str:
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

    def format_perfdata(self, check: "Check") -> str:
        if not check.perfdata:
            return ""
        out = " ".join(check.perfdata)
        return "| " + self._screen_chars(out, "perfdata")

    def add_longoutput(self, text: str | list[str] | tuple[str, ...]) -> None:
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
        screened = _filter_output(text, self.ILLEGAL)
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


def _quote(label: str) -> str:
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
    their respective base unit, so
    :python:`Performance('size', 10000, 'B')`
    is better than
    :python:`Performance('size', 10, 'kB')`.

    .. seealso::

        See the
        `Monitoring Plugin Guidelines Repository <https://github.com/monitoring-plugins/monitoring-plugin-guidelines/blob/main/monitoring_plugins_interface/03.Output.md#performance-data>`__
        or the
        `Monitoring Plugins Development Guidelines <https://www.monitoring-plugins.org/doc/guidelines.html#AEN197>`__
        for details.


    :param label: The short identifier, results in graph titles for example
       (20 chars or less recommended).
    :param value: The measured value (usually an ``int``, ``float``, or ``bool``).
    :param uom: The unit of measure -- use base units whereever possible.
    :param warn: The warning range.
    :param crit: The critical range.
    :param min: The known value minimum (``None`` for no minimum).
    :param max: The known value maximum (``None`` for no maximum).
    """

    label: str
    """The short identifier, results in graph titles for example (20 chars or less recommended)."""

    value: typing.Any
    """The measured value (usually an ``int``, ``float``, or ``bool``)."""

    uom: typing.Optional[str]
    """The unit of measure -- use base units whereever possible."""

    warn: typing.Optional["RangeSpec"]
    """The warning range."""

    crit: typing.Optional["RangeSpec"]
    """The critical range."""

    min: typing.Optional[float]
    """The known value minimum (``None`` for no minimum)."""

    max: typing.Optional[float]
    """The known value maximum (``None`` for no maximum)."""

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
        """Create new performance data object."""
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

        performance: str = f"{_quote(self.label)}={self.value}"

        if self.uom is not None:
            performance += self.uom

        out: list[str] = [performance]

        # https://www.monitoring-plugins.org/doc/guidelines.html#AEN197
        # warn, crit, min or max may be null (for example, if the threshold is not defined or min and max do not apply). Trailing unfilled semicolons can be dropped

        if self.warn is None:
            out.append("")
        else:
            out.append(str(self.warn))

        if self.crit is None:
            out.append("")
        else:
            out.append(str(self.crit))

        if self.min is None:
            out.append("")
        else:
            out.append(str(self.min))

        if self.max is None:
            out.append("")
        else:
            out.append(str(self.max))

        return re.sub(r";+$", "", ";".join(out))


# runtime.py

"""Functions and classes to interface with the system.

This module contains the :class:`Runtime` class that handles exceptions,
timeouts and logging. Plugin authors should not use Runtime directly,
but decorate the plugin's main function with :func:`~.runtime.guarded`.
"""

P = typing.ParamSpec("P")
R = typing.TypeVar("R")


def guarded(
    original_function: typing.Any = None, verbose: typing.Any = None
) -> typing.Any:
    """Runs a function mplugin's Runtime environment.

    `guarded` makes the decorated function behave correctly with respect
    to the monitoring plugin API if it aborts with an uncaught exception or
    a timeout. It exits with an *unknown* exit code and prints a
    traceback in a format acceptable by monitoring solution.

    This function should be used as a decorator for the script's `main`
    function.

    :param verbose: Optional keyword parameter to control verbosity
        level during early execution (before
        :meth:`~mplugin.main` has been called). For example,
        use `@guarded(verbose=0)` to turn tracebacks in that phase off.
    """

    def _decorate(func: typing.Callable[P, R]):
        @functools.wraps(func)
        # This inconsistent-return-statements error can be fixed by adding a
        # typing.NoReturn type hint to Runtime._handle_exception(), but we can't do
        # that as long as we're maintaining py27 compatability.
        # pylint: disable-next=inconsistent-return-statements
        def wrapper(*args: typing.Any, **kwds: typing.Any):
            runtime = _Runtime()
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


class _AnsiColorFormatter(logging.Formatter):
    """https://medium.com/@kamilmatejuk/inside-python-colorful-logging-ad3a74442cc6"""

    def format(self, record: logging.LogRecord) -> str:
        no_style = "\033[0m"
        bold = "\033[91m"
        grey = "\033[90m"
        yellow = "\033[93m"
        red = "\033[31m"
        red_light = "\033[91m"
        blue = "\033[34m"
        start_style = {
            "DEBUG": grey,
            "INFO": blue,
            "WARNING": yellow,
            "ERROR": red,
            "CRITICAL": red_light + bold,
        }.get(record.levelname, no_style)
        end_style = no_style
        return f"{start_style}{super().format(record)}{end_style}"


# platform.py


def _with_timeout(
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


class _Runtime:
    instance: typing.Optional[typing_extensions.Self] = None  # type: ignore
    check: typing.Optional["Check"] = None
    _verbose = 1
    _colorize: bool = False
    """Use ANSI colors to colorize the logging output"""
    timeout: typing.Optional[int] = None
    logchan: logging.StreamHandler[io.StringIO]
    output: _Output
    stdout: typing.Optional[io.StringIO] = None
    exitcode: int = 70  # EX_SOFTWARE

    def __new__(cls) -> typing_extensions.Self:
        if not cls.instance:
            cls.instance: typing_extensions.Self = super(_Runtime, cls).__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        rootlogger = logging.getLogger("mplugin")
        rootlogger.setLevel(logging.DEBUG)
        self.logchan = logging.StreamHandler(io.StringIO())
        self.logchan.setFormatter(logging.Formatter("%(message)s"))
        rootlogger.addHandler(self.logchan)
        self.output = _Output(self.logchan)

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

    @property
    def colorize(self) -> int:
        return self._colorize

    @colorize.setter
    def colorize(self, colorize: bool) -> None:
        self._colorize = colorize
        if colorize:
            self.logchan.setFormatter(_AnsiColorFormatter("%(message)s"))
        else:
            self.logchan.setFormatter(logging.Formatter("%(message)s"))

    def run(self, check: "Check") -> None:
        check()
        self.output.add(check)
        self.exitcode = check.exitcode

    def execute(
        self,
        check: "Check",
        verbose: typing.Any = None,
        timeout: typing.Any = None,
        colorize: bool = False,
    ) -> typing.NoReturn:
        self.check = check
        if verbose is not None:
            self.verbose = verbose
        if timeout is not None:
            self.timeout = int(timeout)
        if colorize:
            self.colorize = True
        if self.timeout:
            _with_timeout(self.timeout, self.run, check)
        else:
            self.run(check)
        print("{0}".format(self.output), end="", file=self.stdout)
        self.sysexit()

    def sysexit(self) -> typing.NoReturn:
        sys.exit(self.exitcode)


# from metric.py

"""Structured representation for data points.
"""


class Metric:
    """Single measured value.

    Instances of ths class are passed as value objects between most of
    mplugin's core classes. Typically, :class:`~.Resource` objects
    emit a list of metrics as result of their :meth:`~.Resource.probe`
    methods.

    The value should be expressed in terms of base units, so
    :python:`Metric('swap', 10240, 'B')`
    is better than
    :python:`Metric('swap', 10, 'kiB')`.


    :param name: A short internal identifier for the value -- appears
        also in the performance data.
    :param value: A data point. This value vsually has a boolen or numeric type,
        but other types are also possible.
    :param uom: :term:`unit of measure`, preferrably as ISO
        abbreviation like ``s``.
    :param min: The minimum value or ``None`` if there is no known minimum.
    :param max: The maximum value or ``None`` if there is no known maximum.
    :param context: The name of the associated :class:`~.Context` (defaults to the
        metric’s name if left out).
    """

    name: str
    """A short internal identifier for the value -- appears also in the
    performance data."""

    value: typing.Any
    """A data point. This value vsually has a boolen or numeric type,
    but other types are also possible."""

    uom: typing.Optional[str] = None
    """:term:`unit of measure`, preferrably as ISO
        abbreviation like ``s``."""

    min: typing.Optional[float] = None
    """The minimum value or ``None`` if there is no known minimum."""

    max: typing.Optional[float] = None
    """The maximum value or ``None`` if there is no known maximum."""

    context_name: str
    """The name of the associated :class:`~.Context` (defaults to the
        metric’s name if left out)."""

    __context: typing.Optional["Context"] = None
    __resource: typing.Optional["Resource"] = None

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
        context: typing.Optional[typing.Union[str, Context]] = None,
        resource: typing.Optional[Resource] = None,
    ) -> None:
        """Creates new Metric instance."""
        self.name = name
        self.value = value
        self.uom = uom
        self.min = min
        self.max = max
        if context is not None:
            if isinstance(context, str):
                self.context_name = context
            if isinstance(context, Context):
                self.context_name = context.name
                self.__context = context
        else:
            self.context_name = name
        if resource is not None:
            self.__resource = resource

    def __str__(self) -> str:
        """Same as :attr:`valueunit`."""
        return self.valueunit

    @property
    def resource(self) -> Resource:
        if not self.__resource:
            raise RuntimeError("no resource set for metric", self.name)
        return self.__resource

    @resource.setter
    def resource(self, resource: Resource) -> None:
        self.__resource = resource

    @property
    def context(self) -> Context:
        if not self.__context:
            raise RuntimeError("no context set for metric", self.name)
        return self.__context

    @context.setter
    def context(self, context: Context) -> None:
        self.__context = context

    @property
    def description(self) -> typing.Optional[str]:
        """Human-readable, detailed string representation.

        Delegates to the :class:`~.context.Context` to format the value.

        :returns: :meth:`~.context.Context.describe` output or
            :attr:`valueunit` if no context has been associated yet
        """
        if self.__context:
            return self.__context.describe(self)
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
        return self.context.evaluate(self, self.resource)

    def performance(self) -> list[Performance]:
        """Generates performance data according to the context.

        :return: :class:`~mplugin.Performance` object
        :raise RuntimeError: if no context has been associated yet
        """
        result = self.context.performance(self, self.resource)

        if result is None:
            return []

        if isinstance(result, Performance):
            return [result]

        output: list[Performance] = []

        for preformance in result:
            output.append(preformance)

        return output


# resource.py

"""Domain model for data :term:`acquisition`.
"""


class Resource:
    """Abstract base class for custom domain models.

    :class:`Resource` is the base class for the plugin's :term:`domain
    model`. It shoul model the relevant details of reality that a plugin is
    supposed to check. The :class:`~.check.Check` controller calls
    :meth:`Resource.probe` on all passed resource objects to acquire data.

    Plugin authors should subclass :class:`Resource` and write
    whatever methods are needed to get the interesting bits of information.
    The most important resource subclass should be named after the plugin
    itself.

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

        A plugin can perform several measurements at once.

        .. code-block:: Python

            def probe(self):
                self.users = self.list_users()
                self.unique_users = set(self.users)
                return [
                    Metric("total", len(self.users), min=0, context="users"),
                    Metric("unique", len(self.unique_users), min=0, context="users"),
                ]

        Alternatively, the probe() method can act as generator and yield metrics:

        .. code-block:: Python

            def probe(self):
                self.users = self.list_users()
                self.unique_users = set(self.users)
                yield Metric('total', len(self.users), min=0,
                                        context='users')
                yield Metric('unique', len(self.unique_users), min=0,
                                        context='users')]

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
accomodate for special needs.
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
        return self.metric.context

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

    def add(self, *results: Result) -> typing_extensions.Self:
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

    def __iter__(self) -> typing.Generator[Result, typing.Any, None]:
        """Iterates over all results.

        The iterator is sorted in order of decreasing state
        significance (unknown > critical > warning > ok).

        :returns: result object iterator
        """
        for state in reversed(sorted(self.by_state)):
            for result in self.by_state[state]:
                yield result

    def __len__(self) -> int:
        """Number of results in this container."""
        return len(self.results)

    def __getitem__(self, item: typing.Union[int, str]) -> Result:
        """Access result by index or name.

        If *item* is an integer, the itemth element in the
        container is returned. If *item* is a string, it is used to
        look up a result with the given name.

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
    """

    name: str
    fmt_metric: typing.Optional[FmtMetric]

    def __init__(
        self,
        name: str,
        fmt_metric: typing.Optional[FmtMetric] = None,
    ) -> None:

        self.name = name
        self.fmt_metric = fmt_metric

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
        return self.result(ok, metric=metric)

    def result(
        self,
        state: ServiceState,
        hint: typing.Optional[str] = None,
        metric: typing.Optional["Metric"] = None,
    ) -> Result:
        """
        Create a Result object with the given state, hint, and metric.

        :param state: The service state for the result.
        :param hint: An optional hint message providing additional context.
        :param metric: An optional Metric object associated with the result.

        :return: A Result object containing the provided state, hint, and metric.
        """
        return Result(state=state, hint=hint, metric=metric)

    def ok(
        self,
        hint: typing.Optional[str] = None,
        metric: typing.Optional["Metric"] = None,
    ) -> Result:
        """
        Create a successful Result.

        :param hint: Optional hint message providing additional context about the successful operation.
        :param metric: Optional Metric object associated with this result.

        :return: A Result object representing a successful operation.
        """
        return self.result(ok, hint=hint, metric=metric)

    def warning(
        self,
        hint: typing.Optional[str] = None,
        metric: typing.Optional["Metric"] = None,
    ) -> Result:
        """
        Create a warning result.

        :param hint: Optional hint message to provide additional context for the warning.
        :param metric: Optional metric associated with the warning.

        :return: A Result object representing a warning.
        """
        return self.result(warning, hint=hint, metric=metric)

    def critical(
        self,
        hint: typing.Optional[str] = None,
        metric: typing.Optional["Metric"] = None,
    ) -> Result:
        """
        Create a critical result.

        :param hint: Optional hint message providing additional context about the critical result.
        :param metric: Optional metric object associated with this critical result.

        :return: A Result object representing a critical state.
        """
        return self.result(critical, hint=hint, metric=metric)

    def unknown(
        self,
        hint: typing.Optional[str] = None,
        metric: typing.Optional["Metric"] = None,
    ) -> Result:
        """
        Create a Result object with an unknown status.

        :param hint: Optional hint message providing additional context about why the result is unknown
        :param metric: Optional Metric object associated with this result

        :return: A Result object with unknown status
        """
        return self.result(unknown, hint=hint, metric=metric)

    # This could be corrected by re-implementing this class as a proper ABC.
    # See issue #43
    # pylint: disable-next=no-self-use
    def performance(
        self, metric: "Metric", resource: "Resource"
    ) -> typing.Optional[
        typing.Union[
            Performance,
            typing.Sequence[Performance],
            typing.Generator[Performance, typing.Any, None],
        ]
    ]:
        """Derives performance data from a given metric.

        This base implementation just returns none. Plugin authors may
        override this method in subclass to specialize behaviour.

        .. code-block:: python

            def performance(self, metric: Metric, resource: Resource) -> Performance:
                return Performance(label=metric.name, value=metric.value)

        .. code-block:: python

            def performance(
                self, metric: Metric, resource: Resource
            ) -> Performance | None:
                if not opts.performance_data:
                    return None
                return Performance(
                    metric.name,
                    metric.value,
                    metric.uom,
                    self.warning,
                    self.critical,
                    metric.min,
                    metric.max,
                )

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
    ) -> None:
        """Ready-to-use :class:`Context` subclass for scalar values.

        ScalarContext models the common case where a single scalar is to
        be evaluated against a pair of warning and critical thresholds.

        :attr:`name` and :attr:`fmt_metric`,
        are described in the :class:`Context` base class.

        :param warning: Warning threshold as
            :class:`~mplugin.Range` object or range string.
        :param critical: Critical threshold as
            :class:`~mplugin.Range` object or range string.
        """
        super(ScalarContext, self).__init__(name, fmt_metric)
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
            return self.critical(self.critical_range.violation, metric)
        if not self.warn_range.match(metric.value):
            return self.warning(self.warn_range.violation, metric)
        return self.ok(None, metric)

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


class _Contexts:
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


# from check.py: Controller logic for check execution.


log: logging.Logger = logging.getLogger("mplugin")
"""
**mplugin** integrates with the logging module from Python's standard
library. If the main function is decorated with :meth:`guarded` (which is heavily
recommended), the logging module gets automatically configured before the
execution of the `main()` function starts. Messages logged to the *mplugin*
logger (or any sublogger) are processed with mplugin's integrated logging.

The verbosity level is set in the :meth:`check.main()` invocation depending on
the number of ``-v`` flags.

When called with *verbose=0,* both the summary and the performance data are
printed on one line and the warning message is displayed. Messages logged with
*warning* or *error* level are always printed.
Setting *verbose* to 1 does not change the logging level but enable multi-line
output. Additionally, full tracebacks would be printed in the case of an
uncaught exception.
Verbosity levels of ``2`` and ``3`` enable logging with *info* or *debug* levels.
"""


class Check:
    """Controller logic for check execution.

    The class :class:`Check` orchestrates the
    the various stages of check execution. Interfacing with the
    outside system is done via a separate :class:`Runtime` object.

    When a check is called (using :meth:`Check.main` or
    :meth:`Check.__call__`), it probes all resources and evaluates the
    returned metrics to results and performance data. A typical usage
    pattern would be to populate a check with domain objects and then
    delegate control to it.
    """

    resources: list[Resource]
    contexts: _Contexts
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
        self.contexts = _Contexts()
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
                log.warning("resource %s did not produce any metric", resource.name)
            if isinstance(metrics, Metric):
                # resource returned a bare metric instead of list/generator
                metrics = [metrics]
            for metric in metrics:
                context = self.contexts[metric.context_name]
                metric.context = context
                metric.resource = resource

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
                for performance in metric.performance():
                    self.perfdata.append(str(performance))
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
        self,
        verbose: typing.Any = None,
        timeout: typing.Any = None,
        colorize: bool = False,
    ) -> typing.NoReturn:
        """All-in-one control delegation to the runtime environment.

        Get a :class:`_Runtime` instance and
        perform all phases: run the check (via :meth:`__call__`), print
        results and exit the program with an appropriate status code.

        :param verbose: output verbosity level between 0 and 3
        :param timeout: abort check execution with a :exc:`Timeout`
            exception after so many seconds (use 0 for no timeout)
        :param colorize: Use ANSI colors to colorize the logging output
        """
        runtime = _Runtime()
        runtime.execute(self, verbose=verbose, timeout=timeout, colorize=colorize)

    @property
    def state(self) -> ServiceState:
        """Overall check state.

        The most significant (=worst) state seen in :attr:`results` to
        far. :obj:`unknown` if no results have been
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
        from :class:`Summary`. Read-only property.
        """
        return self.summary.verbose(self.results) or ""

    @property
    def exitcode(self) -> int:
        """Overall check exit code according to the monitoring API.

        Corresponds with :attr:`state`. Read-only property.
        """
        try:
            return int(self.results.most_significant_state)
        except ValueError:
            return 3
