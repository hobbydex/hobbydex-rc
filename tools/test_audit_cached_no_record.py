"""Cases for the cached-manual-no-record check in tools/audit.py.

A cached manual PDF counts as a gap when no document record matches it: not by its file name, its maker's
address or its name slug, linked or not. A safety sheet or a static Tamiya kit is left out, and a record that
matches only by name still counts as a record. The names are real cache file names.

    python3 -I tools/test_audit_cached_no_record.py
"""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class RecordGap(unittest.TestCase):
    def test_a_matching_record_is_a_record_linked_or_not(self):
        doc = {"id": "doc/kyosho/32237r-mr03s2-t02-sp", "releases": []}
        self.assertEqual(audit.record_gap([doc], excluded=False), "record")
        self.assertEqual(audit.record_gap([doc], excluded=True), "record")

    def test_no_record_for_a_manual_is_a_gap(self):
        self.assertEqual(audit.record_gap([], excluded=False), "gap")

    def test_no_record_for_a_non_manual_is_left_out(self):
        self.assertEqual(audit.record_gap([], excluded=audit.not_manual_name("22540-Akku-Sicherheitshinweise")), "left out")
        self.assertEqual(audit.record_gap([], excluded=audit.not_manual_name("32234r-MR03S2-T02_SP")), "gap")


if __name__ == "__main__":
    unittest.main()
