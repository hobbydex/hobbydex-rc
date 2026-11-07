"""audit.run_child: a tool the audit runs that goes past its timeout is killed and reported as None, not waited for.

    python3 -I tools/test_audit_child_timeout.py
"""
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

SLEEP = "import time; time.sleep(120)"


def test_child_in_time_gives_its_output():
    run = audit.run_child([sys.executable, "-I", "-c", "print('counted')"], timeout=60)
    assert run.returncode == 0
    assert run.stdout.strip() == "counted"


def test_child_past_its_timeout_gives_none():
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        run = audit.run_child([sys.executable, "-I", "-c", SLEEP, "link_maker_pages.py"], timeout=1)
    assert run is None
    assert "child timed out after 1 s: link_maker_pages.py" in err.getvalue()


def test_default_timeout_is_an_hour():
    assert audit.CHILD_TIMEOUT == 3600


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
