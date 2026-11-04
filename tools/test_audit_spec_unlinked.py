"""Cases for audit.used_spec_ids: a spec is in use through equivalent_to, includes or protocols, not otherwise.

    python3 -I tools/test_audit_spec_unlinked.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402


def test_equivalent_to_counts():
    parts = [{"id": "part/a/1", "equivalent_to": [{"spec": "spec/screw/m3x8-button-hex", "match": "functional"}]}]
    assert "spec/screw/m3x8-button-hex" in audit.used_spec_ids(parts)


def test_includes_count():
    parts = [{"id": "part/a/2", "includes": [{"spec": "spec/pin/3x30", "qty": 1}]}]
    assert "spec/pin/3x30" in audit.used_spec_ids(parts)


def test_protocols_count():
    parts = [{"id": "part/a/3", "protocols": ["spec/protocol/sanwa-fh5"]}]
    assert "spec/protocol/sanwa-fh5" in audit.used_spec_ids(parts)


def test_unlinked_spec_is_not_used():
    parts = [{"id": "part/a/4", "name": "3x8 screw", "equivalent_to": [], "includes": [{"qty": 1, "notes": "no spec"}]}]
    assert audit.used_spec_ids(parts) == set()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
