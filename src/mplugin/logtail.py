from __future__ import annotations

import os
from types import TracebackType
import typing
from io import BufferedIOBase

if typing.TYPE_CHECKING:
    from .cookie import Cookie


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
    cookie: "Cookie"
    logfile: typing.Optional[BufferedIOBase] = None
    stat: typing.Optional[os.stat_result]

    def __init__(self, path: str, cookie: "Cookie") -> None:
        """Creates new LogTail context.

        :param path: path to the log file that is to be observed
        :param cookie: :class:`~.cookie.Cookie` object to save the last
            file position
        """
        self.path = os.path.abspath(path)
        self.cookie = cookie
        self.logfile = None
        self.stat = None

    def _seek_if_applicable(self, fileinfo: dict[str, typing.Any]) -> None:
        self.stat = os.stat(self.path)
        if self.stat.st_ino == fileinfo.get(
            "inode", -1
        ) and self.stat.st_size >= fileinfo.get("pos", 0) and self.logfile is not None:
            self.logfile.seek(fileinfo["pos"])

    def __enter__(self) -> typing.Generator[bytes, typing.Any, None]:
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

    def __exit__(self, exc_type: typing.Optional[type[BaseException]],
             exc_value: typing.Optional[BaseException],
             traceback: typing.Optional[TracebackType]) -> None:
        if not exc_type and self.stat is not None and self.logfile is not None:
            self.cookie[self.path] = dict(
                inode=self.stat.st_ino, pos=self.logfile.tell()
            )
            self.cookie.commit()
        self.cookie.close()
        if self.logfile is not None:
            self.logfile.close()
