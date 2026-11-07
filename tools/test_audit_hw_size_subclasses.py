"""Cases for audit.not_specable and audit.thickness_only: hw-size-no-spec keeps only the parts a spec kind can hold.

The linkers' reasons are passed in as stubs, so the test reads no tools checkout.

    python3 -I tools/test_audit_hw_size_subclasses.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402


def no_reason(p):
    return None


def no_ball(name):
    return None


def test_thickness_only_washer_shim():
    assert audit.thickness_only({"category": "washer-shim", "name": "3mm SPACER 0.5mm"})
    assert audit.thickness_only({"category": "washer-shim", "name": "Carisma CRF1 5mm Ride Height Spacers"})


def test_sized_washer_is_not_thickness_only():
    assert not audit.thickness_only({"category": "washer-shim", "name": "M4 washer"})
    assert not audit.thickness_only({"category": "washer-shim", "name": "Washer 3.2x7x0.5"})
    assert not audit.thickness_only({"category": "washer-shim", "name": "Crush Tube, 5x7x5mm"})
    assert not audit.thickness_only({"category": "screw", "name": "3mm spacer"})


def test_thickness_only_goes_to_subclass():
    p = {"category": "washer-shim", "name": "4mm Lock Washer", "id": "part/a/1"}
    assert audit.not_specable(p, no_reason, no_ball) == "hw-size-thickness-only"


def test_loose_ball_goes_to_subclass():
    p = {"category": "ball-end", "name": "Ball End 19mm", "id": "part/a/2"}
    assert audit.not_specable(p, no_reason, lambda n: "ball type not stated") == "hw-size-loose-ball"


def test_typed_ball_stays_main():
    p = {"category": "ball-end", "name": "Ball Stud 4.8 x 6mm", "id": "part/a/3"}
    assert audit.not_specable(p, no_reason, no_ball) is None


def test_screw_reasons_map_to_subclasses():
    cases = {
        "drive not stated": "hw-size-screw-no-drive",
        "tapping": "hw-size-screw-no-drive",
        "unparsed": "hw-size-screw-unparsed",
        "several sizes": "hw-size-screw-not-one-spec",
        "special": "hw-size-screw-not-one-spec",
        "silent": "hw-size-screw-not-one-spec",
    }
    for reason, cls in cases.items():
        p = {"category": "screw", "name": "3x8 screw", "id": "part/a/4"}
        assert audit.not_specable(p, lambda q, r=reason: r, no_ball) == cls, reason


def test_linkable_screw_stays_main():
    p = {"category": "screw", "name": "M3x8 Cap Head Screw Hex", "id": "part/a/5"}
    assert audit.not_specable(p, no_reason, no_ball) is None


def test_retired_spec_id_stays_main():
    p = {"category": "screw", "name": "M3x8 Cap Head Screw Hex", "id": "part/a/6"}
    assert audit.not_specable(p, lambda q: "retired spec id", no_ball) is None


def test_other_categories_stay_main():
    p = {"category": "nut", "name": "M3 Nut", "id": "part/a/7"}
    assert audit.not_specable(p, lambda q: "drive not stated", lambda n: "ball type not stated") is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
