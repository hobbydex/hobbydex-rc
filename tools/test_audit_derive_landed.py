"""Cases for audit.last_derive_landed and derive_not_landed: the daily derive must land a PR within 2 days.

    python3 -I -m pytest tools/test_audit_derive_landed.py -q
"""
import datetime
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

TODAY = datetime.date(2026, 11, 5)


def test_recent_landing_is_fine():
    assert audit.derive_not_landed("2026-11-04", TODAY) == []
    assert audit.derive_not_landed("2026-11-03", TODAY) == []


def test_stale_landing_is_flagged():
    assert audit.derive_not_landed("2026-10-29", TODAY) == ["derive: last landed 2026-10-29 (7 days ago)"]


def test_no_landing_known_is_flagged():
    assert len(audit.derive_not_landed(None, TODAY)) == 1


def _repo(d, subject):
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", subject], check=True)


def test_status_field_and_git_log_take_the_later_day():
    with tempfile.TemporaryDirectory() as rc, tempfile.TemporaryDirectory() as tools:
        _repo(rc, "Derived fields: pack counts (2026-10-29) (#1)")
        os.makedirs(os.path.join(tools, "cache"))
        with open(os.path.join(tools, "cache", "local_loop_status.json"), "w") as f:
            json.dump({"derive": {"last_derive_landed": "2026-01-01"}}, f)
        assert audit.last_derive_landed(rc, tools) == datetime.date.today().isoformat()   # the git commit is dated today
        with open(os.path.join(tools, "cache", "local_loop_status.json"), "w") as f:
            json.dump({"derive": {"last_derive_landed": "2999-01-01"}}, f)
        assert audit.last_derive_landed(rc, tools) == "2999-01-01"


def test_other_commits_are_no_derive():
    with tempfile.TemporaryDirectory() as rc, tempfile.TemporaryDirectory() as tools:
        _repo(rc, "Parts: something else (#2)")
        assert audit.last_derive_landed(rc, tools) is None
