"""Cases for audit.is_body_set_doc: only a body set's own manual counts as a body manual.

    python3 -I tools/test_audit_body_set.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402


def test_body_set_manual():
    assert audit.is_body_set_doc({"title": "Tamiya 51578 body parts set: assembly manual"}, "doc/tamiya/spb-51578-manual")


def test_whole_car_manual_naming_its_body():
    assert not audit.is_body_set_doc({"title": "Tamiya 47481 Super Avante (Painted Body) (TD4 Chassis): instruction manual"}, "doc/tamiya/47481-manual-de")
    assert not audit.is_body_set_doc({"title": "Carson 1:5 Chassis 100% RTR incl. Porsche Body: instruction manual"}, "doc/carson/x")
    assert not audit.is_body_set_doc({"title": "1/9 GP 4WD KIT DRX wo/Body: parts list"}, "doc/kyosho/31047-drx-parts-list-v01")


def test_missing_doc():
    assert not audit.is_body_set_doc(None, "doc/none")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
