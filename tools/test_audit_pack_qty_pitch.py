"""Cases for audit.gear_pitch_as_count: a gear whose pack_qty is its pitch is flagged (tools#590).

    python3 -I tools/test_audit_pack_qty_pitch.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402


def test_count_equal_to_pitch_dp_is_flagged():
    p = {"id": "part/x/1", "category": "spur-gear", "name": "90T Spur Gear", "pack_qty": 48, "pitch_dp": 48}
    assert audit.gear_pitch_as_count(p) == "pack_qty 48 is the pitch_dp"


def test_count_equal_to_printed_pitch_is_flagged():
    p = {"id": "part/x/2", "category": "spur-gear", "name": "90T SPUR GEAR (48P)", "pack_qty": 48}
    assert audit.gear_pitch_as_count(p) == "pack_qty 48 is the pitch printed in the name"


def test_pitch_word_and_dp_forms_are_read():
    assert audit.gear_pitch_as_count({"id": "a", "category": "pinion", "name": "Drive Gear (32DP)", "pack_qty": 32})
    assert audit.gear_pitch_as_count({"id": "b", "category": "gear", "name": "32 Pitch Gear", "pack_qty": 32})


def test_pinion_named_with_a_pitch_and_one_piece_is_fine():
    p = {"id": "part/3racing/3RAC-PG4815", "category": "pinion", "name": "48 Pitch Pinion Gear (15T)", "pack_qty": 1, "pitch_dp": 48}
    assert audit.gear_pitch_as_count(p) is None


def test_gear_set_with_a_bracketed_count_is_fine():
    p = {"id": "part/treal/x", "category": "gear", "name": "Portal Gears Set 15T/20T (8P)", "pack_qty": 8}
    assert audit.gear_pitch_as_count(p) is None


def test_several_gears_with_a_bracketed_count_is_fine():
    p = {"id": "part/ftx/FTX7266", "category": "pinion", "name": "Motor Pinion Gears 13T + Set Screws 3*3mm(2P)", "pack_qty": 2}
    assert audit.gear_pitch_as_count(p) is None


def test_other_categories_are_not_read():
    p = {"id": "part/x/3", "category": "screw", "name": "Screw (48P)", "pack_qty": 48}
    assert audit.gear_pitch_as_count(p) is None


def test_a_count_without_pitch_match_is_fine():
    p = {"id": "part/x/4", "category": "gear", "name": "Idler Gear 40T", "pack_qty": 2, "pitch_dp": 48}
    assert audit.gear_pitch_as_count(p) is None


def test_no_pack_qty_is_fine():
    assert audit.gear_pitch_as_count({"id": "part/x/5", "category": "gear", "name": "Gear (48P)", "pitch_dp": 48}) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
