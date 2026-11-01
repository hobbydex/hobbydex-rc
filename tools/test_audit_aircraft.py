"""is_aircraft_part: T2M aircraft, helicopter and drone parts are counted apart from the car-link queue.

Run: python3 -I tools/test_audit_aircraft.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit  # noqa: E402


def test_t2m_drone_part_is_aircraft():
    assert audit.is_aircraft_part({"brand": "brand/t2m", "number": "T5190-01"})
    assert audit.is_aircraft_part({"brand": "brand/t2m", "number": "T620-01"})


def test_t2m_car_part_is_not_aircraft():
    assert not audit.is_aircraft_part({"brand": "brand/t2m", "number": "T4919-01"})
    assert not audit.is_aircraft_part({"brand": "brand/t2m", "number": "T4900-6"})   # a wing for a car, not T4900 as aircraft


def test_prefix_matches_whole_code_only():
    assert not audit.is_aircraft_part({"brand": "brand/t2m", "number": "T62"})
    assert not audit.is_aircraft_part({"brand": "brand/t2m", "number": "T6200-1"})


def test_other_brand_is_not_aircraft():
    assert not audit.is_aircraft_part({"brand": "brand/xray", "number": "T5190-01"})


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
