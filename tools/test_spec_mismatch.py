"""Cases for audit.spec_mismatches: a spec link whose family the part's category or name does not carry.

    python3 -I -m pytest tools/test_spec_mismatch.py
    python3 -I tools/test_spec_mismatch.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402


def part(name, category, **fields):
    return dict(id="part/x/1", name=name, category=category, **fields)


def test_bearing_include_on_a_clip_is_flagged():
    p = part("E-Clip 4mm", "clip", includes=[dict(spec="spec/bearing/8x16x5", notes="Size from the name")])
    assert [m[2] for m in audit.spec_mismatches([p])] == ["spec/bearing/8x16x5"]


def test_bearing_include_on_a_ball_end_is_flagged():
    p = part("Ball Stud. φ5.8", "ball-end", includes=[dict(spec="spec/bearing/6x10x3")])
    assert len(audit.spec_mismatches([p])) == 1


def test_motor_include_on_a_decal_is_flagged():
    p = part("MOTOR W/DECAL SET", "decal", includes=[dict(spec="spec/motor/brushed-540-3.175mm")])
    assert len(audit.spec_mismatches([p])) == 1


def test_accessories_are_fine():
    parts = [
        part("Pinion gears 13T + set screws 3*3mm", "pinion", includes=[dict(spec="spec/screw/m3x3-set-hex", qty=2)]),
        part("Gear set, differential (2x14.8mm pin)", "differential", includes=[dict(spec="spec/pin/2x14.8")]),
        part("Input gear, transmission, 20-tooth/ 2.5x12mm pin", "gear", includes=[dict(spec="spec/pin/2.5x12")]),
        part("Steering drag link/ 5x8x2.5 ball bearing", "steering", includes=[dict(spec="spec/bearing/5x8x2.5")]),
        part("Screw", "screw", includes=[dict(spec="spec/washer/3x6x0.5")]),
        part("Brass pipe & screw", "washer-shim", includes=[dict(spec="spec/screw/m3x15-pan-jis")]),
    ]
    assert audit.spec_mismatches(parts) == []


def test_sourced_include_is_checked_by_category_only():
    p = part("Reinforced set", "shock", includes=[dict(spec="spec/bearing/4x10x4", source="doc/x/list")])
    assert audit.spec_mismatches([p]) == []


def test_equivalent_bearing_on_a_clip_is_flagged():
    p = part("E-Clip 4mm", "clip", equivalent_to=[dict(spec="spec/bearing/8x16x5", match="functional")])
    assert len(audit.spec_mismatches([p])) == 1


def test_equivalent_motor_on_a_rebuild_kit_is_flagged():
    p = part("Rebuild kit, Velineon 380 (4x9x4mm ball bearings)", "motor", equivalent_to=[dict(spec="spec/motor/brushed-380-2.3mm", match="functional")])
    assert len(audit.spec_mismatches([p])) == 1


def test_equivalent_on_the_right_kind_stays():
    parts = [
        part("Ball Bearing 5x8x2.5", "bearing", equivalent_to=[dict(spec="spec/bearing/5x8x2.5", match="functional")]),
        part("Retaining washer 3.2 DIN 6799", "clip", equivalent_to=[dict(spec="spec/eclip/3mm", match="functional")]),
        part("Motor 540 kit", "motor", equivalent_to=[dict(spec="spec/motor/brushed-540-3.175mm", match="functional")]),
        part("XT60 plug", "wire", equivalent_to=[dict(spec="spec/connector/xt60", match="functional")]),
    ]
    assert audit.spec_mismatches(parts) == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
