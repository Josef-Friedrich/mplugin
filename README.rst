The m(onitoring)plugin library
==============================

This is a fork of the `nagiosplugin`_. Changes:

- Drop support for Python versions 3.9 and below
- Add type hints
- Remove deprecated code: ``ScalarResult``
- Rename all four service state objects to lower-class names. For example,
  ``Ok`` was renamed to ``ok``, and so on
- Rename the warning state from ``warn`` to ``warning``
- Export the class ``ServiceState``
- Convert all namped tuples in classes (``Metric``, ``Performance``, ``ServiceState``)
- Remove ``compat.py``
- Add helper methods ``ok()``, ``warning()``, ``critical()``, ``unknown()`` in ``Context``
- Add the ``setup_argparse`` function
- Add the  ``timespan()`` function to convert time interval strings, such as ``2h30min``,  into seconds.
- Merge all code into a single source file,
- Merge the entire code base into a single file to make it easier to embed the code
  in a monitoring plugin instead of importing it. This allows a plugin to be
  implemented without dependencies.

About
-----

**mplugin** is a Python class library which helps writing Nagios or Icinga
compatible plugins easily in Python. It cares for much of the boilerplate code
and default logic commonly found in monitoring checks, including:

- Monitoring Plugin API compliant parameters and output formatting
- Full monitoring range syntax support
- Automatic threshold checking
- Multiple independend measures
- Custom status line to communicate the main point quickly
- Long output and performance data
- Timeout handling
- Persistent "cookies" to retain state information between check runs
- Resume log file processing at the point where the last run left
- No dependencies beyond the Python standard library.

**mplugin** runs on POSIX and Windows systems. It is compatible with
and Python 3.10 and later.

Feedback and Suggestions
------------------------

mplugin is currently maintained by Josef Friedrich <josef@friedrich.rocks>.  A
public issue tracker can be found at
<https://github.com/Josef-Friedrich/mplugin/issues> for bugs, suggestions, and
patches.

License
-------

The mplugin package is released under the Zope Public License 2.1 (ZPL), a
BSD-style Open Source license.

Documentation
-------------

Comprehensive documentation is `available online`_. The examples mentioned in
the `tutorials`_ can also be found in the `examples` directory of
the source distribution.

.. _available online: https://mplugin.readthedocs.io/
.. _tutorials: https://mplugin.readthedocs.io/en/stable/tutorial/
.. _nagiosplugin: https://github.com/mpounsett/nagiosplugin

Acknowledgements
----------------

mplugin was originally written and maintained by Christian Kauhaus
<kc@flyingcircus.io>.  Additional contributions from the community are
acknowledged in the file CONTRIBUTORS.txt
