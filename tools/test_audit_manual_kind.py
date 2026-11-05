"""Cases for the manual-unlinked check's non-manual rule in tools/audit.py.

A cached PDF whose name states no manual kind is left out of the gap count only when its name
says it is not a manual (safety sheet, battery notice, press release, product sheet). A car-named
file with no kind word stays a gap ("kind unknown"). The names are real cache file names.

    python3 -I tools/test_audit_manual_kind.py
"""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class NotManualName(unittest.TestCase):
    def test_named_non_manuals_are_left_out(self):
        self.assertTrue(audit.not_manual_name("msds_tamiya_spruehfarbe_ps_10-2020"))
        self.assertTrue(audit.not_manual_name("22540-Akku-Sicherheitshinweise"))
        self.assertTrue(audit.not_manual_name("20182-PressRelease_011821_20182-Enduro24-Trailrunner"))
        self.assertTrue(audit.not_manual_name("300047500_Product_Sheet"))
        # declarations of conformity are not manuals (FTX and other makers name them "...-Declaration-of-Conformity")
        self.assertTrue(audit.not_manual_name("ftx5473r-Declaration-of-Conformity"))
        self.assertTrue(audit.not_manual_name("ftx5529g-Declaration-of-Conformity"))
        # a kit's list of items needed apart, a radio setting sheet, a price list and a catalogue are not manuals
        self.assertTrue(audit.not_manual_name("25603-Required-separately"))
        self.assertTrue(audit.not_manual_name("ModelsSetting Sheet_RSx4S_one10X_EN"))
        self.assertTrue(audit.not_manual_name("Price-List-2024_Gambado"))
        self.assertTrue(audit.not_manual_name("YOKOMO_CATALOG_Autumn"))

    def test_car_named_files_without_a_kind_word_stay_gaps(self):
        # kind unknown: the cover must be read; a car name or a set name is not a non-manual
        self.assertFalse(audit.not_manual_name("300012657_Ducati_1199_Pinigale_Gabel-Set"))
        self.assertFalse(audit.not_manual_name("RA273"))
        self.assertFalse(audit.not_manual_name("25542-gambado"))

    def test_manuals_are_never_left_out(self):
        self.assertFalse(audit.not_manual_name("30618-javelin-manual"))
        self.assertFalse(audit.not_manual_name("300056045_Centurion_Mk.III_Bedienung_en"))
        self.assertFalse(audit.not_manual_name("300058084_Ferrari_F189_F101"))
        self.assertFalse(audit.not_manual_name("MZW403_Carbon_Rear_Sus_m"))


class NameSlug(unittest.TestCase):
    def test_hyphens_and_underscores_make_one_name(self):
        self.assertEqual(audit.name_slug("dp_yd4_160612_tatsuhiro.pdf"), audit.name_slug("dp-yd4-160612-tatsuhiro.PDF"))
        self.assertEqual(audit.name_slug("https://x.com/a/B6D_2016%20Thielke.pdf?v=1"), "b6d2016thielke")
        self.assertNotEqual(audit.name_slug("b6-4.pdf"), audit.name_slug("b6-4d.pdf"))


class CopiesOfLinked(unittest.TestCase):
    def test_identical_copy_of_a_linked_file_counts_as_linked(self):
        import tempfile
        with tempfile.TemporaryDirectory() as cache:
            os.makedirs(os.path.join(cache, "manuals", "acme"))
            os.makedirs(os.path.join(cache, "manuals", "other"))
            for name, data in (("10-B6D_sheet.pdf", b"%PDF-same"), ("b6d-sheet.pdf", b"%PDF-same"),
                               ("b6d-other.pdf", b"%PDF-diff"), ("tiny.pdf", b"x")):
                with open(os.path.join(cache, "manuals", "acme", name), "wb") as fh:
                    fh.write(data)
            with open(os.path.join(cache, "manuals", "other", "same.pdf"), "wb") as fh:
                fh.write(b"%PDF-same")
            linked = ["manuals/acme/10-B6D_sheet.pdf"]
            left = audit.drop_copies_of_linked(cache, ["manuals/acme/b6d-sheet.pdf", "manuals/acme/b6d-other.pdf",
                                                       "manuals/other/same.pdf", "manuals/acme/tiny.pdf"], linked)
            # another brand's identical file stays; so does a file of another size or content
            self.assertEqual(left, ["manuals/acme/b6d-other.pdf", "manuals/other/same.pdf", "manuals/acme/tiny.pdf"])


if __name__ == "__main__":
    unittest.main()
