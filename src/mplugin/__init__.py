from importlib import metadata

from .check import Check
from .context import Context, ScalarContext
from .cookie import Cookie
from .error import CheckError, Timeout
from .logtail import LogTail
from .metric import Metric
from .multiarg import MultiArg
from .performance import Performance
from .range import Range
from .resource import Resource
from .result import Result, Results
from .runtime import Runtime, guarded
from .state import critical, ok, unknown, warn
from .summary import Summary

__version__: str = metadata.version("mplugin")

__all__: list[str] = [
    "Check",
    "Context",
    "ScalarContext",
    "Cookie",
    "CheckError",
    "Timeout",
    "LogTail",
    "Metric",
    "MultiArg",
    "Performance",
    "Range",
    "Resource",
    "Result",
    "Results",
    "Runtime",
    "guarded",
    "critical",
    "ok",
    "unknown",
    "warn",
    "Summary",
]
