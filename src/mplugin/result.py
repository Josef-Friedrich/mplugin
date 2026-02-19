"""Outcomes from evaluating metrics in contexts.

The :class:`Result` class is the base class for all evaluation results.
The :class:`Results` class (plural form) provides a result container with
access functions and iterators.

Plugin authors may create their own :class:`Result` subclass to
accomodate for special needs. :class:`~.context.Context` constructors
accept custom Result subclasses in the `result_cls` parameter.
"""

import collections
import typing
from typing import Optional, Union

from mplugin.state import ServiceState

if typing.TYPE_CHECKING:
    from .context import Context
    from .metric import Metric
    from .resource import Resource
    from .state import ServiceState


class Result:
    """Evaluation outcome consisting of state and explanation.

    A Result object is typically emitted by a
    :class:`~mplugin.context.Context` object and represents the
    outcome of an evaluation. It contains a
    :class:`~mplugin.state.ServiceState` as well as an explanation.
    Plugin authors may subclass Result to implement specific features.
    """

    state: "ServiceState"

    hint: Optional[str]

    metric: Optional["Metric"]

    def __init__(
        self,
        state: "ServiceState",
        hint: Optional[str] = None,
        metric: Optional["Metric"] = None,
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
    def resource(self) -> Optional["Resource"]:
        """Reference to the resource used to generate this result."""
        if not self.metric:
            return None
        return self.metric.resource

    @property
    def context(self) -> Optional["Context"]:
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

    def __getitem__(self, item: Union[int, str]) -> Result:
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
