"""audit.hardware_in_box: a release's box hardware counts role kit and role listed rows (Schumacher's manual does not
mark the box, so its spares are listed). Other roles and non-hardware parts do not count.

    python3 -I tools/test_audit_kit_box_hardware.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

PART_OF = {
    "part/x/screw": {"category": "screw"},
    "part/x/nut": {"category": "nut"},
    "part/x/body": {"category": "chassis"},
}


def rel(*rows):
    return {"id": "release/x/1", "contains": [{"part": p, "role": r} for p, r in rows]}


def test_kit_rows_count():
    r = rel(*[("part/x/screw", "kit")] * 4 + [("part/x/nut", "kit")] * 2)
    assert audit.hardware_in_box(r, PART_OF) == 6


def test_listed_rows_count_with_kit_rows():
    r = rel(*[("part/x/screw", "kit")] * 4 + [("part/x/screw", "listed")] * 6)
    assert audit.hardware_in_box(r, PART_OF) == 10


def test_listed_only_counts():
    r = rel(*[("part/x/nut", "listed")] * 12)
    assert audit.hardware_in_box(r, PART_OF) == 12


def test_other_roles_and_non_hardware_do_not_count():
    r = rel(("part/x/screw", "option"), ("part/x/screw", "upgrade"), ("part/x/body", "kit"), ("part/x/body", "listed"))
    assert audit.hardware_in_box(r, PART_OF) == 0


def test_unknown_part_does_not_count():
    r = rel(("part/x/missing", "listed"))
    assert audit.hardware_in_box(r, PART_OF) == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
