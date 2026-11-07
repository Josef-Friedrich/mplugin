import re
import subprocess
import sys
from pathlib import Path

import pytest

base = Path(__file__).parent / ".." / "examples"


def run_example(filename: str, regexp: str):
    proc = subprocess.Popen(
        [sys.executable, base / filename, "-v"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"PYTHONPATH": ":".join(sys.path)},
        encoding="UTF-8",
    )
    out, err = proc.communicate()
    assert err == ""
    assert re.match(regexp, out) is not None, f'"{out}" does not match "{regexp}"'
    assert 0 == proc.returncode


def test_check_load():
    if not sys.platform.startswith("linux"):
        pytest.skip("requires Linux")
    run_example(
        "check_load.py",
        """\
LOAD OK - loadavg is [0-9., ]+
| load15=[0-9.]+;;;0 load1=[0-9.]+;;;0 load5=[0-9.]+;;;0
""",
    )


def test_check_users():
    run_example(
        "check_users.py",
        """\
USERS OK - \\d+ users logged in
users: .*
| total=\\d+;;;0 unique=\\d+;;;0
""",
    )


def test_check_world():
    run_example("check_world.py", "^WORLD OK$")
