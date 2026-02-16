import time

import pytest

import monitoringplugin
from monitoringplugin.platform import with_timeout


class TestPlatform:
    def test_timeout(self):
        with pytest.raises(monitoringplugin.Timeout):
            with_timeout(1, time.sleep, 2)
