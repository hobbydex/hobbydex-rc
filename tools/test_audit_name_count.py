"""Cases for audit.name_count_strippable: a stated name keeps its count; a count that conflicts with pack_qty is no strip.

    python3 -I tools/test_audit_name_count.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402


def test_stated_name_keeps_its_count():
    assert not audit.name_count_strippable({"name_source": "manual", "pack_qty": 2}, 2, [])
    assert not audit.name_count_strippable({"name_source": "manufacturer"}, 1, [])


def test_unsourced_name_with_matching_count_is_stripped():
    assert audit.name_count_strippable({"pack_qty": 4}, 4, [])
    assert audit.name_count_strippable({}, 2, [])


def test_conflicting_count_is_not_a_strip():
    assert not audit.name_count_strippable({"pack_qty": 2}, 1, [])


def test_callout_is_stripped_from_an_unsourced_name():
    assert audit.name_count_strippable({"pack_qty": 2}, None, ["(MOUNTED x4)"])


def test_nothing_to_strip():
    assert not audit.name_count_strippable({}, None, [])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
