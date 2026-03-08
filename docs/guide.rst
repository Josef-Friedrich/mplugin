*****
Guide
*****

This tutorial will guide you through all important steps of writing a check with
the :py:mod:`mplugin` class library. Read this to get started.

Key concepts
============

:py:mod:`mplugin` has a fine-grained class model with clear separation of
concerns. This allows plugin writers to focus on one
particular tasks at a time while writing plugins. Monitoring plugins need to
perform three steps: data :term:`acquisition`, :term:`evaluation`, and
:term:`presentation`. Each step has an associated class (Resource, Context,
Summary) and information between tasks is passed with structured value objects
(Metric, Result).

Classes overview
================

Here is a diagram with the most important classes and their relationships::

                +----------+                \
                | Resource |                 |
                +----------+                 |
          _____/      |     \_____           | Acquisition
         v            v           v          |
   +---------+   +---------+   +---------+   |
   | Metric  |...| Metric  |...| Metric  |  <
   +---------+   +---------+   +---------+   |
        |             |             |        |
        v             v             v        |
   +---------+   +---------+   +---------+   |
   | Context |...| Context |...| Context |   | Evaluation
   +---------+   +---------+   +---------+   |
        |             |             |        |
        v             v             v        |
   +---------+   +---------+   +---------+   |
   | Result  |...| Result  |...| Result  |  <
   +---------+   +---------+   +---------+   |
              \___    |    ___/              |
                  v   v   v                  | Presentation
                 +---------+                 |
                 | Summary |                 |
                 +---------+                /

:py:class:`mplugin.Resource`
   A model of the thing being monitored. It should usually have the same name
   as the whole plugin. Generates one or more metrics.

   *Example: system load*

:py:class:`mplugin.Metric`
   A single measured data point. A metric consists of a name, a value, a unit,
   and optional minimum and maximum bounds. Most metrics are scalar (the value
   can be represented as single number).

   *Example: load1=0.75*

:py:class:`mplugin.Context`
   Additional information to evaluate a metric. A context has usually a warning
   and critical range which allows to determine if a given metric is OK or not.
   Contexts also include information on how to present a metric in a
   human-readable way.

   *Example: warning=0.5, critical=1.0*

:py:class:`mplugin.Result`
   Product of a metric and a context. A result consists of a state ("ok",
   "warning", "critical", "unknown"), some explanatory text, and references to
   the objects that it was generated from.

   *Example: WARNING - load1 is 0.75*

:py:class:`mplugin.Summary`
   Condenses all results in a single status line. The status line is the
   plugin's most important output: it appears in mails, text messages,
   pager alerts etc.

   *Example: LOAD WARNING - load1 is 0.75 (greater than 0.5)*

The following tutorials which will guide you through the most important
features of :mod:`mplugin`.

.. hint::

   Study the source code in the :file:`mplugin/examples` directory for
   complete examples.

Minimal setup
=============

.. admonition:: Tutorial #1: 'Hello world' check

   In the first tutorial, we will develop `check_world`. This check will determine
   if the world exists. The algorithm is simple: if the world would not exist, the
   check would not execute.

This minimalistic check consists of a :py:class:`Resource` World which models
the part of the world that is interesting for the purposes of our check.
Resource classes must define a :py:meth:`Resource.probe` method which returns a
list of metrics. We just return a single :py:class:`Metric` object that states
that the world exists.

.. literalinclude:: /../examples/check_world.py

We don't have a context to evaluate the returned metric yet, so we resort to the
built-in "null" context. The "null" context does nothing with its associated
metrics.

We now create a :py:class:`Check` object that is fed only with the resource
object. We could put context and summary objects into the :py:meth:`Check()`
constructor as well. This will be demonstrated in the next tutorial. There is
also no command line processing nor timeout handling nor output control. We call
the :py:meth:`Check.main` method to evaluate resources, construct text output
and exit with the appropriate status code.

Running the plugin creates very simple output:

.. code-block:: bash
   :linenos:

   $ check_world.py
   WORLD OK

The plugin's exit status is 0, signalling success to the calling process.


.. admonition:: Tutorial #2: check_load

      In this tutorial, we will discuss important basic features that are present in
      nearly every check. These include command line processing, metric evaluation
      with scalar contexts, status line formatting and logging.

      The :program:`check_load` plugin resembles the one found in the standard monitoring
      plugins collection. It allows to check the system load average against
      thresholds.

Data acquisition
================

First, we will subclass :class:`~mplugin.Resource` to generate metrics for the 1,
5, and 15 minute load averages.

.. literalinclude:: /../examples/check_load.py
   :start-after: # data acquisition
   :end-before: # data presentation

:program:`check_load` has two modes of operation: the load averages may either
be takes as read from the kernel or normalized by cpu. Accordingly, the
:meth:`Load()` constructor has a parameter two switch normalization on.

In the :meth:`Load.probe` method the check reads the load averages from the
:file:`/proc` filesystem and extracts the interesting values. For each value, a
:class:`~mplugin.Metric` object is returned. Each metric has a generated name
("load1", "load5", "load15") and a value. We don't declare a unit of measure
since load averages come without unit. All metrics will share the same context
"load" which means that the thresholds for all three values will be the same.

.. note::

   Deriving the number of CPUs from :file:`/proc` is a little bit messy and
   deserves an extra method. Resource classes may encapsulate arbitrary complex
   measurement logic as long they define a :meth:`Resource.probe` method that
   returns a list of metrics. In the code example shown above, we sprinkle some
   logging statements which show effects when the check is called with an
   increased logging level (discussed below).


Evaluation
==========

The :program:`check_load` plugin should accept warning and critical ranges and
determine if any load value is outside these ranges. Since this kind of logic is
pretty standard for most of all Nagios/Icinga plugins,
:mod:`mplugin` provides a generalized context class for it. It is
the :class:`~mplugin.ScalarContext` class which accepts a warning
and a critical range as well as a template to present metric values in a
human-readable way.

When :class:`~mplugin.ScalarContext` is sufficient, it may be
configured during instantiation right in the `main` function. A first
version of the `main` function looks like this:

.. code-block:: python

   def main():
       argp = argparse.ArgumentParser(description=__doc__)
       argp.add_argument('-w', '--warning', metavar='RANGE', default='',
                         help='return warning if load is outside RANGE')
       argp.add_argument('-c', '--critical', metavar='RANGE', default='',
                         help='return critical if load is outside RANGE')
       argp.add_argument('-r', '--percpu', action='store_true', default=False)
       args = argp.parse_args()
       check = mplugin.Check(
           Load(args.percpu),
           mplugin.ScalarContext('load', args.warning, args.critical))
       check.main()

Note that the context name "load" is referenced by all three metrics returned by
the `Load.probe` method.

This version of :program:`check_load` is already functional:

.. code-block:: bash
   :linenos:

   $ ./check_load.py
   LOAD OK - load1 is 0.11
   | load15=0.21;;;0 load1=0.11;;;0 load5=0.18;;;0

   $ ./check_load.py -c 0.1:0.2
   LOAD CRITICAL - load15 is 0.22 (outside 0.1:0.2)
   | load15=0.22;;0.1:0.2;0 load1=0.11;;0.1:0.2;0 load5=0.2;;0.1:0.2;0
   # exit status 2

   $ ./check_load.py -c 0.1:0.2 -r
   LOAD OK - load1 is 0.105
   | load15=0.11;;0.1:0.2;0 load1=0.105;;0.1:0.2;0 load5=0.1;;0.1:0.2;0

In the first invocation (lines 1--3), :program:`check_load` reports only the
first load value which looks bit arbitrary. In the second invocation (lines
5--8), we set a critical threshold. The range specification is parsed
automatically according to the :term:`Monitoring plugin API` and the first metric
that lies outside is reported. In the third invocation (lines 10--12), we
request normalization and all values fit in the range this time.

Result presentation
===================

Although we now have a running check, the output is not as informative as it
could be. The first line of output (status line) is very important since the
information presented therein should give the admin a clue what is going on.
We want the first line to display:

* a load overview when there is nothing wrong
* which load value violates a threshold, if applicable
* which threshold is being violated, if applicable.

The last two points are already covered by the :class:`~mplugin.result.Result` default
implementation, but we need to tweak the summary to display a load overview
as stated in the first point:

.. literalinclude:: /../examples/check_load.py
   :start-after: # data presentation
   :end-before: # runtime environment and data evaluation

The :class:`~mplugin.Summary` class has three methods which can be
specialized: :meth:`~mplugin.Summary.ok` to return a status line
when there are no problems, :meth:`~mplugin.Summary.problem` to
return a status line when the overall check status indicates problems, and
:meth:`~mplugin.Summary.verbose` to generate additional output. All
three methods get a set of :class:`~mplugin.result.Result` objects passed
in. In our code, the `ok` method queries uses the original metrics referenced by
the result objects to build an overview like "loadavg is 0.19, 0.16, 0.14".

Check setup
===========

The last step in this tutorial is to put the pieces together:

.. literalinclude:: /../examples/check_load.py
   :start-after: # runtime environment and data evaluation

In the :py:func:`main` function we parse the command line parameters using the
standard :class:`argparse.ArgumentParser` class. Watch the
:class:`~mplugin.Check` object creation: its constructor can be fed
with a variable number of :class:`~mplugin.Resource`,
:class:`~mplugin.Context`, and
:class:`~mplugin.Summary` objects. In this tutorial, instances of
our specialized `Load` and `LoadSummary` classes go in.

We did not specialize a :class:`~mplugin.Context` class to evaluate
the load metrics. Instead, we use the supplied
:class:`~mplugin.ScalarContext` which compares a scalar value
against two ranges according to the range syntax defined by the monitoring plugin
API. The default :class:`~mplugin.ScalarContext`
implementation covers the majority of evaluation needs. Checks using non-scalar
metrics or requiring special logic should subclass
:class:`~mplugin.Context` to fit their needs.

The check's :meth:`~mplugin.Check.main` method runs the check, prints
the check's output including summary, log messages and :term:`performance data`
to *stdout* and exits the plugin with the appropriate exit code.

Note the :func:`~mplugin.runtime.guarded` decorator in front of the main
function. It helps the code part outside :class:`~mplugin.Check` to
behave: in case of uncaught exceptions, it ensures that the exit code is **3**
(unknown) and that the exception string is properly formatted. Additionally,
logging is set up at an early stage so that even messages logged from
constructors are captured and printed at the right place in the output (between
status line and performance data).


.. admonition:: Tutorial #3: check_users

      In the third tutorial, we will learn how to process multiple metrics.
      Additionally, we will see how to use logging and verbosity levels.


Multiple metrics
================

A plugin can perform several measurements at once. This is often necessary to
perform more complex state evaluations or improve latency. Consider a check that
determines both the number of total logged in users and the number of unique
logged in users.

A Resource implementation could look like this:

.. code-block:: python

   class Users(mplugin.Resource):

       def __init__(self):
           self.users = []
           self.unique_users = set()

       def list_users(self):
           """Return logged in users as list of user names."""
           [...]
           return users

       def probe(self):
           """Return both total and unique user count."""
           self.users = self.list_users()
           self.unique_users = set(self.users)
           return [mplugin.Metric('total', len(self.users), min=0,
                                       context='users'),
                   mplugin.Metric('unique', len(self.unique_users), min=0,
                                       context='users')]

The `probe()` method returns a list containing two metric objects.
Alternatively, the `probe()` method can act as generator and yield
metrics:

.. code-block:: python

   def probe(self):
       """Return both total and unique user count."""
       self.users = self.list_users()
       self.unique_users = set(self.users)
       yield mplugin.Metric('total', len(self.users), min=0,
                                 context='users')
       yield mplugin.Metric('unique', len(self.unique_users), min=0,
                                 context='users')]

This may be more comfortable than constructing a list of metrics first and
returning them all at once.

To assign a :class:`~mplugin.Context` to a
:class:`~mplugin.Metric`, pass the context's name in the metric's
**context** parameter. Both metrics use the same context "users". This way, the
main function must define only one context that applies the same thresholds to
both metrics:

.. code-block:: python

   @mplugin.guarded
   def main():
       argp = argparse.ArgumentParser()
       [...]
       args = argp.parse_args()
       check = mplugin.Check(
           Users(),
           mplugin.ScalarContext('users', args.warning, args.critical,
                                      fmt_metric='{value} users logged in'))
       check.main()


Multiple contexts
=================

The above example defines only one context for all metrics. This may not be
practical. Each metric should get its own context now. By default, a metric is
matched by a context of the same name. So we just leave out the **context**
parameters:

.. code-block:: python

   def probe(self):
       [...]
       return [mplugin.Metric('total', len(self.users), min=0),
               mplugin.Metric('unique', len(self.unique_users), min=0)]

We then define two contexts (one for each metric) in the `main()` function:

.. code-block:: python

   @mplugin.guarded
   def main():
       [...]
       args = argp.parse_args()
       check = mplugin.Check(
           Users(),
           mplugin.ScalarContext('total', args.warning, args.critical,
                                      fmt_metric='{value} users logged in'),
           mplugin.ScalarContext(
               'unique', args.warning_unique, args.critical_unique,
               fmt_metric='{value} unique users logged in'))
       check.main(args.verbose, args.timeout)

Alternatively, we can require every context that fits in metric definitions.


Logging and verbosity levels
============================

**mplugin** integrates with the `logging`_ module from Python's standard
library. If the main function is decorated with :meth:`guarded` (which is heavily
recommended), the logging module gets automatically configured before the
execution of the `main()` function starts. Messages logged to the *mplugin*
logger (or any sublogger) are processed with mplugin's integrated logging.

Consider the following example check::

   import argparse
   import mplugin
   import logging

   _log = logging.getLogger('mplugin')


   class Logging(mplugin.Resource):

       def probe(self):
           _log.warning('warning message')
           _log.info('info message')
           _log.debug('debug message')
           return [mplugin.Metric('zero', 0, context='default')]


   @mplugin.guarded
   def main():
       argp = argparse.ArgumentParser()
       argp.add_argument('-v', '--verbose', action='count', default=0)
       args = argp.parse_args()
       check = mplugin.Check(Logging())
       check.main(args.verbose)

   if __name__ == '__main__':
       main()



The verbosity level is set in the :meth:`check.main()` invocation depending on
the number of ``-v`` flags.

.. code-block:: bash

   $ check_verbose.py
   LOGGING OK - zero is 0 | zero=0
   warning message (check_verbose.py:11)
   $ check_verbose.py -v
   LOGGING OK - zero is 0
   warning message (check_verbose.py:11)
   | zero=0
   $ check_verbose.py -vv
   LOGGING OK - zero is 0
   warning message (check_verbose.py:11)
   info message (check_verbose.py:12)
   | zero=0
   $ check_verbose.py -vvv
   LOGGING OK - zero is 0
   warning message (check_verbose.py:11)
   info message (check_verbose.py:12)
   debug message (check_verbose.py:13)
   | zero=0

When called with *verbose=0,* both the summary and the performance data are
printed on one line and the warning message is displayed. Messages logged with
*warning* or *error* level are always printed.
Setting *verbose* to 1 does not change the logging level but enable multi-line
output. Additionally, full tracebacks would be printed in the case of an
uncaught exception.
Verbosity levels of ``2`` and ``3`` enable logging with *info* or *debug* levels.

This behaviour conforms to the "Verbose output" suggestions found in the
`Monitoring plug-in development guidelines`_.

The initial verbosity level is 1 (multi-line output). This means that tracebacks
are printed for uncaught exceptions raised in the initialization phase (before
:meth:`Check.main` is called). This is generally a good thing. To suppress
tracebacks during initialization, call :func:`~mplugin.runtime.guarded`
with an optional `verbose` parameter. Example:

+-----------------+----------+----------------------------+
| verbosity level | args     | output                     |
+=================+==========+============================+
| 0               |          | one line, error, warning   |
+-----------------+----------+----------------------------+
| 1               | ``-v``   | multi-line, error, warning |
+-----------------+----------+----------------------------+
| 2               | ``-vv``  | info                       |
+-----------------+----------+----------------------------+
| 3               | ``-vvv`` | debug                      |
+-----------------+----------+----------------------------+

.. code-block:: python

   @mplugin.guarded(verbose=0)
   def main():
      [...]

.. note::

   The initial verbosity level takes effect only until :meth:`Check.main`
   is called with a different verbosity level.


It is advisable to sprinkle logging statements in the plugin code, especially
into the resource model classes. A logging example for a users check could look
like this:

.. code-block:: python

   class Users(mplugin.Resource):

       [...]

       def list_users(self):
           """Return list of logged in users."""
           _log.info('querying users with "%s" command', self.who_cmd)
           users = []
           try:
               for line in subprocess.check_output([self.who_cmd]).splitlines():
                   _log.debug('who output: %s', line.strip())
                   users.append(line.split()[0].decode())
           except OSError:
               raise mplugin.CheckError(
                   'cannot determine number of users ({} failed)'.format(
                       self.who_cmd))
           _log.debug('found users: %r', users)
           return users

Interesting items to log are: the command which is invoked to query the
information from the system, or the raw result to verify that parsing works
correctly.

.. _logging: http://docs.python.org/3/library/logging.html

.. _Monitoring plug-in development guidelines: https://www.monitoring-plugins.org/doc/guidelines.html

Plugin Debugging
================

Debugging plugins can sometimes be complicated since there are so many classes,
which are tied together in an implicit way. I have collected some frequent
questions about debugging.

.. index::
   single: verbose; traceback

An uncaught exception makes the plugin return UNKNOWN. Where is the cause?
--------------------------------------------------------------------------

When your plugin raises an exception, you may get very little output. Example::

   $ check_users.py
   USERS UNKNOWN: RuntimeError: error

Set the **verbose** parameter of :py:meth:`~mplugin.Check.main`
to some value greater than zero and you will get the full traceback::

   $ check_users.py -v
   USERS UNKNOWN: RuntimeError: error
   Traceback (most recent call last):
     File "mplugin/runtime.py", line 38, in wrapper
       return func(*args, **kwds)
     File "mplugin/examples/check_users.py", line 104, in main
       check.main(args.verbose, args.timeout)
     File "mplugin/check.py", line 110, in main
       runtime.execute(self, verbose, timeout)
     File "mplugin/runtime.py", line 118, in execute
       with_timeout(self.timeout, self.run, check)
     File "mplugin/platform/posix.py", line 19, in with_timeout
       func(*args, **kwargs)
     File "mplugin/runtime.py", line 107, in run
       check()
     File "mplugin/check.py", line 95, in __call__
       self._evaluate_resource(resource)
     File "mplugin/check.py", line 73, in _evaluate_resource
       metrics = resource.probe()
     File "mplugin/examples/check_users.py", line 57, in probe
       self.users = self.list_users()
     File "mplugin/examples/check_users.py", line 34, in list_users
       raise RuntimeError('error')
   RuntimeError: error


A Check constructor dies with "cannot add type <...>"
-----------------------------------------------------

When you see the following exception raised from
:py:meth:`~mplugin.Check` (or `Check.add()`)::

   UNKNOWN: TypeError: ("cannot add type <class '__main__.Users'> to check", <__main__.Users object at 0x7f0c64f73f90>)

chances are high that you are trying to add an object that is not an instance
from Resource, Context, Summary, or Results or its subclasses. A common
error is to base a resource class on `object` instead of
:py:class:`~mplugin.Resource`.


.. index:: pdb

I'm trying to use pdb but I get a timeout after 10s
---------------------------------------------------

When using an interactive debugger like pdb on plugins, you may experience that
your debugging session is aborted with a timeout after 10 seconds. Just set the
**timeout** parameter in :py:meth:`~mplugin.Check.main` to 0 to avoid
this.
