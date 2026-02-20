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

import logging
from typing import Any, NoReturn, Optional

from .context import Context, Contexts
from .error import CheckError
from .metric import Metric
from .resource import Resource
from .result import Result, Results
from .runtime import Runtime
from .state import ServiceState, ok, unknown
from .summary import Summary

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
        name: Optional[str] = None,
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
            :class:`~mplugin.resource.Resource`,
            :class:`~mplugin.context.Context`,
            :class:`~mplugin.summary.Summary`, or
            :class:`~mplugin.result.Results`.
        """
        for obj in objects:
            if isinstance(obj, Resource):
                self.resources.append(obj)
                if self.name is None:
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
        try:
            metric = None
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
                elif isinstance(result, ServiceState): # type: ignore
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

    def __call__(self):
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

    def main(self, verbose: Any = None, timeout: Any = None) -> NoReturn:
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
        far. :obj:`~mplugin.state.Unknown` if no results have been
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
        from :class:`~mplugin.summary.Summary`. Read-only property.
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
