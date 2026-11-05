"""ocr-number-twins: a pair whose both numbers are listed in data/reviewed-distinct.toml (each printed on its own
kit page) leaves the class; a pair with one listed number stays. The fixture is a small file in a temporary folder;
the last test checks the shipped list's format and that every manual it names is a document record.

Run: python3 -I tools/test_audit_reviewed_distinct.py
"""
import importlib.util
import os
import tempfile
import tomllib
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RC = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

LIST = """# a comment line
[[reviewed]]
number = "19415158"
name = "Metal Parts Bag A"
manual = "doc/tamiya/58169-manual-de"
page = 24

[[reviewed]]
number = "19415168"
name = "Metal Parts Bag A"
manual = "doc/tamiya/58159-manual-de"
page = 24

[[reviewed]]
number = "19415182"
name = "Metal Parts Bag A"
manual = "doc/tamiya/58173-manual-de"
page = 24
"""


def part(number):
    return {"id": f"part/tamiya/{number}", "number": number, "name": "Metal Parts Bag A"}


class ReviewedDistinct(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "reviewed-distinct.toml")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(LIST)

    def tearDown(self):
        self.dir.cleanup()

    def test_gives_the_numbers_only(self):
        self.assertEqual(audit.reviewed_distinct(self.path), {"19415158", "19415168", "19415182"})

    def test_missing_file_gives_none(self):
        self.assertEqual(audit.reviewed_distinct(os.path.join(self.dir.name, "none.tsv")), set())

    def test_both_listed_leaves_the_class(self):
        listed = audit.reviewed_distinct(self.path)
        self.assertTrue(audit.both_reviewed(part("19415158"), part("19415168"), listed))

    def test_one_listed_stays_in_the_class(self):
        listed = audit.reviewed_distinct(self.path)
        self.assertFalse(audit.both_reviewed(part("19415158"), part("19415199"), listed))
        self.assertFalse(audit.both_reviewed(part("19415199"), part("19415168"), listed))

    def test_shipped_list_names_a_document_for_each_number(self):
        path = os.path.join(RC, "data", "reviewed-distinct.toml")
        with open(path, "rb") as fh:
            rows = tomllib.load(fh)["reviewed"]
        self.assertTrue(rows)
        for r in rows:
            self.assertRegex(r["number"], r"^\d{7,8}$")
            self.assertTrue(r["name"])
            self.assertIsInstance(r["page"], int)
            self.assertTrue(r["manual"].startswith("doc/tamiya/"), r["number"])
            stem = r["manual"].split("/")[-1]
            self.assertTrue(os.path.exists(os.path.join(RC, "data", "documents", "tamiya", stem + ".toml")), r["manual"])


if __name__ == "__main__":
    unittest.main()
