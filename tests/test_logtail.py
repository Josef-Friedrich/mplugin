import tempfile

import pytest

from mplugin import Cookie, LogTail


class TestLogTail:
    def setup_method(self) -> None:
        self.lf = tempfile.NamedTemporaryFile(prefix="log.")
        self.cf = tempfile.NamedTemporaryFile(prefix="cookie.")
        self.cookie = Cookie(self.cf.name)

    def teardown_method(self) -> None:
        self.cf.close()
        self.lf.close()

    def test_empty_file(self) -> None:
        with LogTail(self.lf.name, self.cookie) as tail:
            assert [] == list(tail)

    def test_successive_reads(self) -> None:
        self.lf.write(b"first line\n")
        self.lf.flush()
        with LogTail(self.lf.name, self.cookie) as tail:
            assert b"first line\n" == next(tail)
        self.lf.write(b"second line\n")
        self.lf.flush()
        with LogTail(self.lf.name, self.cookie) as tail:
            assert b"second line\n" == next(tail)
        # no write
        with LogTail(self.lf.name, self.cookie) as tail:
            with pytest.raises(StopIteration):
                next(tail)

    def test_offer_same_content_again_after_exception(self) -> None:
        self.lf.write(b"first line\n")
        self.lf.flush()
        try:
            with LogTail(self.lf.name, self.cookie) as tail:
                assert [b"first line\n"] == list(tail)
                raise RuntimeError()
        except RuntimeError:
            pass
        with LogTail(self.lf.name, self.cookie) as tail:
            assert [b"first line\n"] == list(tail)
