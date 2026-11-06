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


def test_small_items_in_bags_are_sold_in_packs():
    for cat, name in (("screw", "M3x6 Screw"), ("nut", "Lock Nut M4"), ("nut", "Locknut"), ("pin", "Hinge Pin 2x10mm"),
                      ("ball-end", "Ball Head Set (10)"), ("bearing", "Ceramic Bearing set 14pcs"), ("rod-end", "Rod End Set"),
                      ("turnbuckle", "Ti Turnbuckle Set 7pcs"), ("clip", "E-Clip"), ("o-ring-seal", "O Ring For Shock")):
        assert audit.sold_in_packs({"category": cat, "name": name}), name


def test_a_single_item_needs_no_pack_count():
    assert not audit.sold_in_packs({"category": "turnbuckle", "name": "Adjustable Front Tie Rod, 1/18 LM"})
    assert not audit.sold_in_packs({"category": "rod-end", "name": "Steering Rod End"})
    assert not audit.sold_in_packs({"category": "rod-end", "name": "Steering servo rod end"})
    assert not audit.sold_in_packs({"category": "rod-end", "name": "Sway Bar Rod Ends"})   # no set or pack word: a single end


def test_other_categories_are_not_hardware_packs():
    assert not audit.sold_in_packs({"category": "wheel", "name": "Wheel Set (4)"})


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
