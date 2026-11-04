"""Cases for audit.is_service_pack: a "for use with ... upgrade kit" clause does not make a part a pack.

    python3 -I tools/test_audit_service_pack.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402


def test_service_pack():
    assert audit.is_service_pack("Rebuild kit, front differential")
    assert audit.is_service_pack("Service pack, driveshafts")
    assert audit.is_service_pack("Upgrade kit, extreme heavy duty")


def test_compat_clause_is_no_pack():
    assert not audit.is_service_pack("Shock tower, front, extreme heavy duty, gray (for use with #9080 upgrade kit)")
    assert not audit.is_service_pack("Carriers, stub axle (for use with #9180, 9181, 9182 upgrade kit)")


def test_plain_part():
    assert not audit.is_service_pack("Hinge pin set")
    assert not audit.is_service_pack("")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
