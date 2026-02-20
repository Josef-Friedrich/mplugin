The m(onitoring)plugin library
==============================

This is a fork of the `nagiosplugin`_. Changes:

- Type hints
- Removed deprecated code: ``ScalarResult``
- ``Ok`` renamed to ``ok``

About
-----

**mplugin** is a Python class library which helps writing Nagios or Icinga
compatible plugins easily in Python. It cares for much of the boilerplate code
and default logic commonly found in Nagios checks, including:

- Nagios 3 Plugin API compliant parameters and output formatting
- Full Nagios range syntax support
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
the `tutorials`_ can also be found in the `mplugin/examples` directory of
the source distribution.

.. _available online: https://mplugin.readthedocs.io/
.. _tutorials: https://mplugin.readthedocs.io/en/stable/tutorial/
.. _nagiosplugin: https://github.com/mpounsett/nagiosplugin

Acknowledgements
----------------

mplugin was originally written and maintained by Christian Kauhaus
<kc@flyingcircus.io>.  Additional contributions from the community are
acknowledged in the file CONTRIBUTORS.txt
