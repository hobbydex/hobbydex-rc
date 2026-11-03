"""Cases for audit.load_linker_drift and linkers_that_would_change: wired linkers that change data on a second run.

    python3 -I -m pytest tools/test_audit_linker_drift.py -q
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402


def test_absent_file_is_none():
    with tempfile.TemporaryDirectory() as d:
        assert audit.load_linker_drift(d) is None


def test_file_is_read_and_only_changing_steps_are_listed():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "cache", "notes"))
        with open(os.path.join(d, "cache", "notes", "linker-drift.tsv"), "w") as f:
            f.write("step\tfiles\tdate\nlink_screw_specs.py\t0\t2026-11-03\nlink_nut_specs.py\t3\t2026-11-03\n")
        drift = audit.load_linker_drift(d)
        assert drift == [("link_screw_specs.py", 0), ("link_nut_specs.py", 3)]
        assert audit.linkers_that_would_change(drift) == ["link_nut_specs.py: 3 files"]


def test_clean_run_has_none():
    assert audit.linkers_that_would_change([("a.py", 0), ("b.py", 0)]) == []
