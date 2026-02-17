"""Structured representation for data points.

This module contains the :class:`Metric` class whose instances are
passed as value objects between most of monitoringplugin's core classes.
Typically, :class:`~.resource.Resource` objects emit a list of metrics
as result of their :meth:`~.resource.Resource.probe` methods.
"""

import numbers
import typing
from typing import Any, Optional, Self, TypedDict, Unpack

from monitoringplugin.performance import Performance

if typing.TYPE_CHECKING:
    from monitoringplugin.result import Result

    from .context import Context
    from .resource import Resource


class MetricKwargs(TypedDict, total=False):
    name: str
    value: Any
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
    value: Any
    uom: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    context: Optional[str] = None
    contextobj: Optional["Context"] = None
    resource: Optional["Resource"] = None

    # Changing these now would be API-breaking, so we'll ignore these
    # shadowed built-ins
    # pylint: disable-next=redefined-builtin
    def __init__(
        self,
        name: str,
        value: Any,
        uom: Optional[str] = None,
        min: Optional[float] = None,
        max: Optional[float] = None,
        context: Optional[str] = None,
        contextobj: Optional["Context"] = None,
        resource: Optional["Resource"] = None,
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
            (set automatically by :class:`~monitoringplugin.check.Check`)
        :param resource: reference to the originating
            :class:`~monitoringplugin.resource.Resource` (set automatically
            by :class:`~monitoringplugin.check.Check`)
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

    def replace(self, **attr: Unpack[MetricKwargs]) -> Self:
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

    def evaluate(self) -> "Result":
        """Evaluates this instance according to the context.

        :return: :class:`~monitoringplugin.result.Result` object
        :raise RuntimeError: if no context has been associated yet
        """
        if not self.contextobj:
            raise RuntimeError("no context set for metric", self.name)
        if not self.resource:
            raise RuntimeError("no resource set for metric", self.name)
        return self.contextobj.evaluate(self, self.resource)

    def performance(self) -> Optional[Performance]:
        """Generates performance data according to the context.

        :return: :class:`~monitoringplugin.performance.Performance` object
        :raise RuntimeError: if no context has been associated yet
        """
        if not self.contextobj:
            raise RuntimeError("no context set for metric", self.name)
        if not self.resource:
            raise RuntimeError("no resource set for metric", self.name)
        return self.contextobj.performance(self, self.resource)
