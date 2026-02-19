import re
import typing
from typing import Any, Optional

from mplugin.range import Range

if typing.TYPE_CHECKING:
    from .range import RangeSpec


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

    value: Any
    """measured value (usually an int, float, or bool)"""

    uom: Optional[str]
    """unit of measure -- use base units whereever possible"""

    warn: Optional["RangeSpec"]
    """warning range"""

    crit: Optional["RangeSpec"]
    """critical range"""

    min: Optional[float]
    """known value minimum (None for no minimum)"""

    max: Optional[float]
    """known value maximum (None for no maximum)"""

    # Changing these now would be API-breaking, so we'll ignore these
    # shadowed built-ins and the long list of arguments
    # pylint: disable-next=redefined-builtin,too-many-arguments
    def __init__(
        self,
        label: str,
        value: Any,
        uom: Optional[str] = None,
        warn: Optional["RangeSpec"] = None,
        crit: Optional["RangeSpec"] = None,
        min: Optional[float] = None,
        max: Optional[float] = None,
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
