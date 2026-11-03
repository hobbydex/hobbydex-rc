"""Cases for audit.gtin_in_cache_not_stored and load_gtin_holes: a barcode the cache states for a record without a gtin.

    python3 -I -m pytest tools/test_audit_gtin_in_cache.py -q
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

HOLES = {"part/a/1": ["4006381333931", "ean", "notes/a/1.html"], "part/a/2": ["4006381333931", "ean", "notes/a/2.html"],
         "part/a/gone": ["4006381333931", "ean", "notes/a/3.html"]}


def test_only_records_without_gtin_are_flagged():
    by_id = {"part/a/1": {"id": "part/a/1"}, "part/a/2": {"id": "part/a/2", "gtin": "4006381333931"}}
    assert audit.gtin_in_cache_not_stored(HOLES, by_id) == ["part/a/1"]


def test_record_gone_from_the_data_is_not_flagged():
    assert audit.gtin_in_cache_not_stored(HOLES, {}) == []


def test_holes_file_is_read_and_absent_file_is_none():
    with tempfile.TemporaryDirectory() as d:
        assert audit.load_gtin_holes(d) is None
        os.makedirs(os.path.join(d, "cache"))
        with open(os.path.join(d, "cache", "gtin_sweep_holes.json"), "w") as f:
            json.dump({"stamp": "2026-11-03", "holes": HOLES}, f)
        assert audit.load_gtin_holes(d) == HOLES
