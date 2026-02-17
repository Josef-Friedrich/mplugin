"""Classes  to represent check outcomes.

This module defines :class:`ServiceState` which is the abstract base class
for check outcomes. The four states defined by the :term:`Nagios plugin API`
are represented as singleton subclasses.

Note that the *warning* state is defined by the :class:`Warn` class. The
class has not been named `Warning` to avoid being confused with the
built-in Python exception of the same name.
"""

from __future__ import annotations

import functools
from typing import Any


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

    def __gt__(self, other: Any) -> bool:
        return (
            hasattr(other, "code")
            and isinstance(other.code, int)
            and self.code > other.code
        )

    def __eq__(self, value: Any) -> bool:
        return (
            hasattr(value, "code")
            and isinstance(value.code, int)
            and self.code == value.code
            and hasattr(value, "text")
            and isinstance(value.text, str)
            and self.text == value.text
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
