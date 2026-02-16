# -*- coding: utf-8 -*-
import time

import nagiosplugin
import pytest
from nagiosplugin.platform import with_timeout

try:
    import unittest2 as unittest
except ImportError:  # pragma: no cover
    import unittest


class TestPlatform:
    def test_timeout(self):
        with pytest.raises(nagiosplugin.Timeout):
            with_timeout(1, time.sleep, 2)
