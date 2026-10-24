"""python3 -I -m unittest discover -s tools -p test_regression_check.py (from the repository root)"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regression_check as rc


class Repointed(unittest.TestCase):
    old = {"part": "part/arrma/ARA330200", "role": "listed", "source": "doc/arrma/ara8406-manual"}

    def test_superseding_part_in_same_release_is_a_repoint(self):
        rows = [{"part": "part/arrma/ARAC9074", "role": "listed", "source": "doc/arrma/ara8406-manual"}]
        self.assertEqual(rc.repointed(self.old, rows, {"part/arrma/ARA330200": "part/arrma/ARAC9074"}), "part/arrma/ARAC9074")

    def test_no_supersedes_is_a_removal(self):
        rows = [{"part": "part/arrma/ARAC9074", "role": "listed", "source": "doc/arrma/ara8406-manual"}]
        self.assertIsNone(rc.repointed(self.old, rows, {}))

    def test_superseding_part_without_row_is_a_removal(self):
        self.assertIsNone(rc.repointed(self.old, [], {"part/arrma/ARA330200": "part/arrma/ARAC9074"}))

    def test_same_part_in_another_role_still_repoints(self):
        rows = [{"part": "part/arrma/ARAC9074", "role": "kit", "source": "doc/arrma/horizon-part-pages"}]
        self.assertEqual(rc.repointed(self.old, rows, {"part/arrma/ARA330200": "part/arrma/ARAC9074"}), "part/arrma/ARAC9074")

    def test_unrelated_part_is_a_removal(self):
        rows = [{"part": "part/arrma/ARAC9080", "role": "listed", "source": "doc/arrma/ara8406-manual"}]
        self.assertIsNone(rc.repointed(self.old, rows, {"part/arrma/ARA330200": "part/arrma/ARAC9074"}))


if __name__ == "__main__":
    unittest.main()
