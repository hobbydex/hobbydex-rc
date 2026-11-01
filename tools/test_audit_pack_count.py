"""Cases for audit.count_unstated: a kit whose maker states no exact count is informational, not fillable.

    python3 -I tools/test_audit_pack_count.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

NO_COUNT_BRAND = {"brand/rcscrewz": {"pack_counts": False}}


def test_minimum_note_is_unstated():
    p = {"brand": "brand/rcscrewz", "notes": "180+ pieces. Holds all the socket screws."}
    assert audit.count_unstated(p, {})


def test_brand_marker_is_unstated():
    p = {"brand": "brand/rcscrewz", "notes": "Holds all the socket screws."}
    assert audit.count_unstated(p, NO_COUNT_BRAND)


def test_kit_of_a_brand_with_exact_counts_is_fillable():
    p = {"brand": "brand/acer-racing", "notes": "Contents not recorded: the description gives no count."}
    assert not audit.count_unstated(p, NO_COUNT_BRAND)


def test_pieces_without_a_plus_is_fillable():
    p = {"brand": "brand/acer-racing", "notes": "12 pieces in the bag."}
    assert not audit.count_unstated(p, {})


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
