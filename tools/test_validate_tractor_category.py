"""python3 -I -m unittest discover -s tools -p test_validate_tractor_category.py (from the repository root)

"tractor" (a farm tractor) is a kit category; road tractor units stay tractor-truck.
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate


class TractorCategory(unittest.TestCase):
    def test_kit_categories(self):
        cats = validate.ENUMS["kit.category"]
        self.assertIn("tractor", cats)
        self.assertIn("tractor-truck", cats)
        self.assertIn("tractor", validate.ENUMS["release.category"])


if __name__ == "__main__":
    unittest.main()
