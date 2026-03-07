"""Offers classes to persist the state between check runs."""

from __future__ import annotations

import importlib
import io
import json
import os
from collections import UserDict
from tempfile import TemporaryFile
from types import TracebackType
from typing import Any, Generator, Optional, cast

from typing_extensions import Self


def _flock_exclusive(fileobj: io.TextIOWrapper) -> None:
    """Acquire exclusive lock for open file `fileobj`."""

    if os.name == "posix":
        fcntl = importlib.import_module("fcntl")
        fcntl.flock(fileobj, fcntl.LOCK_EX)

    if os.name == "nt":
        msvcrt = importlib.import_module("msvcrt")
        msvcrt.locking(fileobj.fileno(), msvcrt.LK_LOCK, 2147483647)


class Cookie(UserDict[str, Any]):
    """Creates a persistent dict to keep state.

    Cookies are used to remember file positions, counters and the like
    between plugin invocations. It is not intended for substantial amounts
    of data. Cookies are serialized into JSON and saved to a state file. We
    prefer a plain text format to allow administrators to inspect and edit
    its content. See :class:`~mplugin.logtail.LogTail` for an
    application of cookies to get only new lines of a continuously growing
    file.

    Cookies are locked exclusively so that at most one process at a time has
    access to it. Changes to the dict are not reflected in the file until
    :meth:`Cookie.commit` is called. It is recommended to use Cookie as
    context manager to get it opened and committed automatically.

    After creation, a cookie behaves like a normal dict.

    :param statefile: file name to save the dict's contents

    .. note:: If `statefile` is empty or None, the Cookie will be
        oblivous, i.e., it will forget its contents on garbage
        collection. This makes it possible to explicitely throw away
        state between plugin runs (for example by a command line
        argument).
    """

    path: Optional[str]

    fobj: Optional[io.TextIOWrapper]

    def __init__(self, statefile: Optional[str] = None) -> None:

        super(Cookie, self).__init__()
        self.path = statefile
        self.fobj = None

    def __enter__(self) -> Self:
        """Allows Cookie to be used as context manager.

        Opens the file and passes a dict-like object into the
        subordinate context. See :meth:`open` for details about opening
        semantics. When the context is left in the regular way (no
        exception raised), the cookie is committed to disk.

        :yields: open cookie
        """
        self.open()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        if not exc_type:
            self.commit()
        self.close()

    def open(self) -> Self:
        """Reads/creates the state file and initializes the dict.

        If the state file does not exist, it is touched into existence.
        An exclusive lock is acquired to ensure serialized access. If
        :meth:`open` fails to parse file contents, it truncates
        the file before raising an exception. This guarantees that
        plugins will not fail repeatedly when their state files get
        damaged.

        :returns: Cookie object (self)
        :raises ValueError: if the state file is corrupted or does not
            deserialize into a dict
        """
        self.fobj = self._create_fobj()
        _flock_exclusive(self.fobj)
        if os.fstat(self.fobj.fileno()).st_size:
            try:
                self.data = self._load()
            except ValueError:
                self.fobj.truncate(0)
                raise
        return self

    def _create_fobj(self) -> io.TextIOWrapper:
        if not self.path:
            return TemporaryFile(
                "w+", encoding="ascii", prefix="oblivious_cookie_", dir=None
            )
        # mode='a+' has problems with mixed R/W operation on Mac OS X
        try:
            return open(self.path, "r+", encoding="ascii")
        except IOError:
            return open(self.path, "w+", encoding="ascii")

    def _load(self) -> dict[str, Any]:
        if not self.fobj:
            raise RuntimeError("file object is none")
        self.fobj.seek(0)
        data = json.load(self.fobj)
        if not isinstance(data, dict):
            raise ValueError(
                "format error: cookie does not contain dict", self.path, data
            )
        return cast(dict[str, Any], data)

    def close(self) -> None:
        """Closes a cookie and its underlying state file.

        This method has no effect if the cookie is already closed.
        Once the cookie is closed, any operation (like :meth:`commit`)
        will raise an exception.
        """
        if not self.fobj:
            return
        self.fobj.close()
        self.fobj = None

    def commit(self) -> None:
        """Persists the cookie's dict items in the state file.

        The cookies content is serialized as JSON string and saved to
        the state file. The buffers are flushed to ensure that the new
        content is saved in a durable way.
        """
        if not self.fobj:
            raise IOError("cannot commit closed cookie", self.path)
        self.fobj.seek(0)
        self.fobj.truncate()
        json.dump(self.data, self.fobj)
        self.fobj.write("\n")
        self.fobj.flush()
        os.fsync(self.fobj)


class LogTail:
    """Access previously unseen parts of a growing file.

    LogTail builds on :class:`~.cookie.Cookie` to access new lines of a
    continuosly growing log file. It should be used as context manager that
    provides an iterator over new lines to the subordinate context. LogTail
    saves the last file position into the provided cookie object.
    As the path to the log file is saved in the cookie, several LogTail
    instances may share the same cookie.
    """

    path: str
    cookie: Cookie
    logfile: Optional[io.BufferedIOBase] = None
    stat: Optional[os.stat_result]

    def __init__(self, path: str, cookie: Cookie) -> None:
        """Creates new LogTail context.

        :param path: path to the log file that is to be observed
        :param cookie: :class:`~.cookie.Cookie` object to save the last
            file position
        """
        self.path = os.path.abspath(path)
        self.cookie = cookie
        self.logfile = None
        self.stat = None

    def _seek_if_applicable(self, fileinfo: dict[str, Any]) -> None:
        self.stat = os.stat(self.path)
        if (
            self.stat.st_ino == fileinfo.get("inode", -1)
            and self.stat.st_size >= fileinfo.get("pos", 0)
            and self.logfile is not None
        ):
            self.logfile.seek(fileinfo["pos"])

    def __enter__(self) -> Generator[bytes, Any, None]:
        """Seeks to the last seen position and reads new lines.

        The last file position is read from the cookie. If the log file
        has not been changed since the last invocation, LogTail seeks to
        that position and reads new lines. Otherwise, the position saved
        in the cookie is reset and LogTail reads from the beginning.
        After leaving the subordinate context, the new position is saved
        in the cookie and the cookie is closed.

        :yields: new lines as bytes strings
        """
        self.logfile = open(self.path, "rb")
        self.cookie.open()
        self._seek_if_applicable(self.cookie.get(self.path, {}))
        line = self.logfile.readline()
        while len(line):
            yield line
            line = self.logfile.readline()

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        if not exc_type and self.stat is not None and self.logfile is not None:
            self.cookie[self.path] = dict(
                inode=self.stat.st_ino, pos=self.logfile.tell()
            )
            self.cookie.commit()
        self.cookie.close()
        if self.logfile is not None:
            self.logfile.close()
