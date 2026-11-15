"""python3 -I tools/test_validate_qualifier_names.py (from the repository root)

A part name of qualifiers only ("Soft", "Front Lower", "Orange+Grey", "2 pcs") is refused: it is the side, colour,
hardness, size or set of a longer name. A name with a noun, a code or model word, a non-Latin word, the number itself,
a paint's colour and a body's model pass.
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate


class QualifierNames(unittest.TestCase):
    def test_qualifiers_only_are_refused(self):
        for name in ("Soft", "Front Lower", "Orange+Grey", "HARD (BLUE)", "B/H TITANIUM", "2 pcs", "Set", "Front & Rear",
                     "Rear Purple (Super Hard)", "H (Hard)", "Brass - Rear Front", "Center(F)"):
            self.assertTrue(validate.qualifier_only_name(name, "X1"), name)

    def test_names_pass(self):
        for name in ("Rear Tire/Soft (Dirt Hog)", "Front Lower Suspension Arms", "M3x8", "12x18x4", "Super Soft Inner",
                     "TS050 0.8mm Standard Version", "1/10 3303 Hard", "2nd.Gear 19T (7075 Hard)", "T-piece 1.5",
                     "Under Neon Set Red", "スーパーソフト", "Light Set", "EHRC Set"):
            self.assertFalse(validate.qualifier_only_name(name, "X1"), name)

    def test_number_paint_and_body_pass(self):
        self.assertFalse(validate.qualifier_only_name("C-00140-049", "C-00140-049"))
        self.assertFalse(validate.qualifier_only_name("Clear Green", "62785", "paint"))
        self.assertFalse(validate.qualifier_only_name("P 9X8 1/12", None, "body"))

    def test_check_reports_the_part(self):
        errors = []
        docs = [("data/parts/x/FA/FAT202S.toml", "part", {"id": "part/x/FAT202S", "number": "FAT202S", "name": "Soft"}),
                ("data/parts/x/FA/FAT202.toml", "part", {"id": "part/x/FAT202", "number": "FAT202", "name": "Rear Tire"})]
        validate.check_qualifier_names(docs, errors)
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("data/parts/x/FA/FAT202S.toml: name 'Soft' is only qualifiers"), errors[0])


if __name__ == "__main__":
    unittest.main()
