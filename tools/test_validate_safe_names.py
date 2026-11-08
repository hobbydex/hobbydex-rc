"""python3 -I -m unittest discover -s tools -p test_validate_safe_names.py (from the repository root)

A data or art file name and the segments of an id use only letters, digits and . _ + -. A '*' or a space is refused
(Kaggle refused the repository over one), and a former id, which is a string and never a file, is not checked.
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate


class SafeNames(unittest.TestCase):
    def test_safe_names_pass(self):
        self.assertEqual(validate.unsafe_name_problems("data/parts/absima/J-/J-026-15+red.toml", "part/absima/J-026-15+red"), [])
        self.assertEqual(validate.unsafe_name_problems("data/releases/arrma/arad12.toml", "release/arrma/arad12"), [])
        self.assertEqual(validate.unsafe_name_problems("art/releases/redcat/EVEREST-GEN7-SPORT-BURNT-ORANGE.svg"), [])

    def test_star_in_file_name_is_refused(self):
        problems = validate.unsafe_name_problems("data/documents/arrma/arad12**-product-page.toml")
        self.assertEqual(len(problems), 1)
        self.assertIn("(*)", problems[0])

    def test_space_in_file_name_is_refused(self):
        problems = validate.unsafe_name_problems("art/releases/redcat/EVEREST-GEN7-SPORT-BURNT ORANGE.svg")
        self.assertEqual(len(problems), 1)
        self.assertIn("( )", problems[0])

    def test_unsafe_id_is_refused_but_its_slashes_are_not(self):
        self.assertEqual(validate.unsafe_name_problems("data/releases/redcat/x.toml", "release/redcat/EVEREST GEN7"),
                         ["data/releases/redcat/x.toml: id 'release/redcat/EVEREST GEN7' has characters outside A-Za-z0-9._+- ( ); "
                          "give it a safe id and keep the old one in former_ids"])
        self.assertEqual(validate.unsafe_name_problems("data/documents/arrma/arad12-product-page.toml", "doc/arrma/arad12-product-page"), [])

    def test_former_id_is_not_checked(self):
        d = {"id": "doc/arrma/arad12-product-page", "former_ids": ["doc/arrma/arad12**-product-page"]}
        self.assertEqual(validate.unsafe_name_problems("data/documents/arrma/arad12-product-page.toml", d["id"]), [])


if __name__ == "__main__":
    unittest.main()
