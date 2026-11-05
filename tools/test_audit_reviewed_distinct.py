"""ocr-number-twins: a pair whose both numbers are listed in data/reviewed-distinct.tsv (each printed on its own
kit page) leaves the class; a pair with one listed number stays. The fixture is a small file in a temporary folder;
the last test checks the shipped list's format and that every manual it names is a document record.

Run: python3 -I tools/test_audit_reviewed_distinct.py
"""
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RC = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

LIST = """# a comment line
number\tname\tmanual\tpage
19415158\tMetal Parts Bag A\tdoc/tamiya/58169-manual-de\t24
19415168\tMetal Parts Bag A\tdoc/tamiya/58159-manual-de\t24
19415182\tMetal Parts Bag A\tdoc/tamiya/58173-manual-de\t24
"""


def part(number):
    return {"id": f"part/tamiya/{number}", "number": number, "name": "Metal Parts Bag A"}


class ReviewedDistinct(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "reviewed-distinct.tsv")
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
        path = os.path.join(RC, "data", "reviewed-distinct.tsv")
        rows = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("#") or line.startswith("number\t") or not line.strip():
                    continue
                rows.append(line.rstrip("\n").split("\t"))
        self.assertTrue(rows)
        for number, name, manual, page in rows:
            self.assertRegex(number, r"^\d{7,8}$")
            self.assertTrue(name)
            self.assertTrue(page.isdigit(), number)
            stem = manual.split("/")[-1]
            self.assertTrue(manual.startswith("doc/tamiya/"), number)
            self.assertTrue(os.path.exists(os.path.join(RC, "data", "documents", "tamiya", stem + ".toml")), manual)


if __name__ == "__main__":
    unittest.main()
