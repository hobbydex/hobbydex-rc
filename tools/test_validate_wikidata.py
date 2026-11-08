"""python3 -I -m unittest discover -s tools -p test_validate_wikidata.py (from the repository root)

A make's and a depicts' `wikidata` is a Wikidata item id; `wikipedia` is an English article title, set only with it
(docs/schema.md "Makes", depicts).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate  # noqa: E402

MAKE = {"id": "make/mercedes-benz", "name": "Mercedes-Benz", "country": "DE", "notes": "German maker.",
        "wikidata": "Q36", "wikipedia": "Mercedes-Benz"}


def release(depicts):
    return ("data/releases/x.toml", "release", {"id": "release/x/1", "depicts": depicts})


def errors_for(*docs):
    errors = []
    validate.check_wikidata([("data/makes/mercedes-benz.toml", "make", MAKE)] + list(docs), errors)
    return errors


class WikidataLinks(unittest.TestCase):
    def test_make_links_are_valid(self):
        self.assertEqual(errors_for(), [])

    def test_make_without_links_is_valid(self):
        plain = {k: v for k, v in MAKE.items() if k not in ("wikidata", "wikipedia")}
        errors = []
        validate.check_wikidata([("data/makes/m.toml", "make", plain)], errors)
        self.assertEqual(errors, [])

    def test_item_id_must_be_a_q_number(self):
        for bad in ("36", "Q", "Q0", "q36", "https://www.wikidata.org/wiki/Q36", "Q36 "):
            errors = []
            validate.check_wikidata([("data/makes/m.toml", "make", dict(MAKE, wikidata=bad))], errors)
            self.assertEqual(len(errors), 1, bad)

    def test_wikipedia_needs_wikidata(self):
        plain = {k: v for k, v in MAKE.items() if k != "wikidata"}
        errors = []
        validate.check_wikidata([("data/makes/m.toml", "make", plain)], errors)
        self.assertEqual(len(errors), 1)

    def test_wikipedia_title_has_no_url_or_fragment(self):
        for bad in ("https://en.wikipedia.org/wiki/Unimog", "Unimog#History", " Unimog", ""):
            errors = []
            validate.check_wikidata([("data/makes/m.toml", "make", dict(MAKE, wikipedia=bad))], errors)
            self.assertEqual(len(errors), 1, bad)

    def test_depicts_links_are_valid(self):
        self.assertEqual(errors_for(release({"make": "Mercedes-Benz", "model": "Unimog", "wikidata": "Q1234", "wikipedia": "Unimog"})), [])

    def test_depicts_without_make_is_valid(self):
        self.assertEqual(errors_for(release({"model": "M4 Sherman", "wikidata": "Q5678", "wikipedia": "M4 Sherman"})), [])

    def test_depicts_bad_id_is_an_error(self):
        self.assertEqual(len(errors_for(release({"make": "Mercedes-Benz", "model": "Unimog", "wikidata": "Unimog"}))), 1)

    def test_part_depicts_too(self):
        part = ("data/parts/x.toml", "part", {"id": "part/x/1", "depicts": {"make": "Mercedes-Benz", "model": "Unimog", "wikidata": "Q1234", "wikipedia": "Unimog"}})
        self.assertEqual(errors_for(part), [])


if __name__ == "__main__":
    unittest.main()
