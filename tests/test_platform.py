import time

import pytest

from mplugin import Timeout, with_timeout


class TestPlatform:
    def test_timeout(self) -> None:
        with pytest.raises(Timeout):
            with_timeout(1, time.sleep, 2)
