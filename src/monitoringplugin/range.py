from typing import Optional, Union


class Range:
    """Represents a threshold range.

    The general format is "[@][start:][end]". "start:" may be omitted if
    start==0. "~:" means that start is negative infinity. If `end` is
    omitted, infinity is assumed. To invert the match condition, prefix
    the range expression with "@".

    See
    http://nagiosplug.sourceforge.net/developer-guidelines.html#THRESHOLDFORMAT
    for details.
    """

    invert: bool

    start: float

    end: float

    def __init__(self, spec: Optional[Union[str, float, "Range"]] = None) -> None:
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

    def __str__(self):
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
    def violation(self):
        """Human-readable description why a value does not match."""
        return "outside range {0}".format(self._format(False))


RangeOrString = Range | str
