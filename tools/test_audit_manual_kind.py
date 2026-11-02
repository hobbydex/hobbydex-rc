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

    def test_car_named_files_without_a_kind_word_stay_gaps(self):
        # kind unknown: the cover must be read; a car name or a set name is not a non-manual
        self.assertFalse(audit.not_manual_name("300012657_Ducati_1199_Pinigale_Gabel-Set"))
        self.assertFalse(audit.not_manual_name("RA273"))
        self.assertFalse(audit.not_manual_name("25542-gambado"))

    def test_manuals_are_never_left_out(self):
        self.assertFalse(audit.not_manual_name("30618-javelin-manual"))
        self.assertFalse(audit.not_manual_name("300056045_Centurion_Mk.III_Bedienung_en"))


if __name__ == "__main__":
    unittest.main()
