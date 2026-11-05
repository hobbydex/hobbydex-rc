"""tamiya-usa-spare-mismatch: a (part, Tamiya USA page) pair listed in data/usa-spare-reviewed.toml leaves the class.
The fixture is a small file in a temporary folder; the last test checks the shipped list's format and that every
evidence document is a document record.
"""
import importlib.util
import os
import tempfile
import tomllib
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RC = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("audit", os.path.join(RC, "tools", "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

VERDICTS = {"usa-wrong", "same-item", "kit-position", "reused-number"}

FIXTURE = """# a comment line
[[reviewed]]
part = "part/tamiya/13455376"
usa = "https://www.tamiyausa.com/shop/7-digit-spare-parts/rc-6x18mm-axle-spacer-58367/"
verdict = "usa-wrong"
evidence = ["doc/tamiya/58367-manual"]
note = "fixture"
"""


class UsaSpareReviewed(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "usa-spare-reviewed.toml")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(FIXTURE)

    def tearDown(self):
        self.dir.cleanup()

    def test_pair_read_from_file(self):
        pairs = audit.usa_spare_reviewed(self.path)
        self.assertEqual(pairs, {("part/tamiya/13455376",
                                  "https://www.tamiyausa.com/shop/7-digit-spare-parts/rc-6x18mm-axle-spacer-58367/")})

    def test_missing_file_gives_none(self):
        self.assertEqual(audit.usa_spare_reviewed(os.path.join(self.dir.name, "nope.toml")), set())

    def test_shipped_list_format(self):
        with open(os.path.join(RC, "data", "usa-spare-reviewed.toml"), "rb") as fh:
            entries = tomllib.load(fh).get("reviewed", [])
        self.assertTrue(entries)
        keys = set()
        for e in entries:
            self.assertTrue(e["part"].startswith("part/tamiya/"), e["part"])
            self.assertTrue(e["usa"].startswith("https://www.tamiyausa.com/"), e["usa"])
            self.assertIn(e["verdict"], VERDICTS)
            self.assertTrue(e["evidence"] and e["note"])
            keys.add((e["part"], e["usa"]))
            for doc in e["evidence"]:
                slug = doc.split("/")[-1]
                self.assertTrue(os.path.exists(os.path.join(RC, "data", "documents", "tamiya", slug + ".toml")), doc)
        self.assertEqual(len(keys), len(entries), "a pair is listed twice")


if __name__ == "__main__":
    unittest.main()
