import os
import tempfile

import pytest

from mplugin import Cookie


class TestCookie:
    def setup_method(self) -> None:
        self.tf = tempfile.NamedTemporaryFile(prefix="cookietest_")

    def teardown_method(self) -> None:
        self.tf.close()

    def test_get_default_value_if_empty(self) -> None:
        with Cookie(self.tf.name) as c:
            assert "default value" == c.get("key", "default value")

    def test_get_file_contents(self):
        with open(self.tf.name, "w") as f:
            f.write('{"hello": "world"}\n')
        with Cookie(self.tf.name) as c:
            assert "world" == c["hello"]

    def test_get_without_open_should_raise_keyerror(self) -> None:
        c = Cookie(self.tf.name)
        with pytest.raises(KeyError):
            c["foo"]

    def test_exit_should_write_content(self) -> None:
        os.unlink(self.tf.name)
        with Cookie(self.tf.name) as c:
            c["hello"] = "wörld"
        with open(self.tf.name) as f:
            assert '{"hello": "w\\u00f6rld"}\n' == f.read()

    def test_should_not_commit_on_exception(self) -> None:
        try:
            with Cookie(self.tf.name) as c:
                c["foo"] = True
                raise RuntimeError()
        except RuntimeError:
            pass
        with open(self.tf.name) as f:
            assert "" == f.read()

    def test_double_close_raises_no_exception(self) -> None:
        c = Cookie(self.tf.name)
        c.open()
        c.close()
        c.close()
        assert True

    def test_close_within_with_block_fails(self) -> None:
        with pytest.raises(IOError):
            with Cookie(self.tf.name) as c:
                c.close()

    def test_multiple_commit(self) -> None:
        c = Cookie(self.tf.name)
        c.open()
        c["key"] = 1
        c.commit()
        with open(self.tf.name) as f:
            assert '"key": 1' in f.read()
        c["key"] = 2
        c.commit()
        with open(self.tf.name) as f:
            assert '"key": 2' in f.read()
        c.close()

    def test_corrupted_cookie_should_raise(self) -> None:
        with open(self.tf.name, "w") as f:
            f.write("{{{")
        c = Cookie(self.tf.name)
        with pytest.raises(ValueError):
            c.open()
        c.close()

    def test_wrong_cookie_format(self) -> None:
        with open(self.tf.name, "w") as f:
            f.write("[1, 2, 3]\n")
        c = Cookie(self.tf.name)
        with pytest.raises(ValueError):
            c.open()
        c.close()

    def test_cookie_format_exception_truncates_file(self) -> None:
        with open(self.tf.name, "w") as f:
            f.write("{slö@@ä")
        c = Cookie(self.tf.name)
        try:
            c.open()
        except ValueError:
            pass
        finally:
            c.close()
        assert 0 == os.stat(self.tf.name).st_size

    def test_oblivious_cookie(self) -> None:
        c = Cookie("")
        # the following method calls are not expected to perfom any function
        c.open()
        c["key"] = 1
        c.commit()
        c.close()
        assert c["key"] == 1
