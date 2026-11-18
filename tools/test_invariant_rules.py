"""Cases for the word rules of the data invariants (tests/invariants/rules.py), which the suite runs on the real tree.

    python3 -I tools/test_invariant_rules.py
"""
import os, re, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "invariants"))
import rules  # noqa: E402


class PlaceholderTitle(unittest.TestCase):
    """doc-placeholder-title: a title of item numbers only, or one that repeats a token."""

    def test_repeated_item_number_is_flagged(self):
        self.assertTrue(rules.placeholder_title("Tamiya 43501 43501: instruction manual (tamiyausa.com, archived)"))
        self.assertTrue(rules.placeholder_title("Tamiya 58449 58449: supplement"))
        self.assertTrue(rules.placeholder_title("Kyosho KF01 KF01 Type 3: instructions"))
        self.assertTrue(rules.placeholder_title("PR Racing product page: 2023 2023 PR SB401-R"))

    def test_number_only_title_is_flagged(self):
        self.assertTrue(rules.placeholder_title("43501"))
        self.assertTrue(rules.placeholder_title("43501 43502"))

    def test_single_number_and_names_are_not_flagged(self):
        self.assertFalse(rules.placeholder_title("Tamiya 43501: instruction manual"))
        self.assertFalse(rules.placeholder_title("Tamiya 22007 Silicone Oil #5000: product page"))
        self.assertFalse(rules.placeholder_title("XRAY XB9 2026 spare parts list"))
        self.assertFalse(rules.placeholder_title("BD11"))   # a genuine video title: a model code, not a number
        self.assertFalse(rules.placeholder_title(""))
        self.assertFalse(rules.placeholder_title(None))


class ServicePack(unittest.TestCase):
    """service-pack-in-box: a service, rebuild or upgrade pack, not a part that names the kit it works with."""

    def test_service_pack(self):
        self.assertTrue(rules.is_service_pack("Rebuild kit, front differential"))
        self.assertTrue(rules.is_service_pack("Service pack, driveshafts"))
        self.assertTrue(rules.is_service_pack("Upgrade kit, extreme heavy duty"))

    def test_compat_clause_is_no_pack(self):
        self.assertFalse(rules.is_service_pack("Shock tower, front, extreme heavy duty, gray (for use with #9080 upgrade kit)"))
        self.assertFalse(rules.is_service_pack("Carriers, stub axle (for use with #9180, 9181, 9182 upgrade kit)"))

    def test_plain_part(self):
        self.assertFalse(rules.is_service_pack("Hinge pin set"))
        self.assertFalse(rules.is_service_pack(""))


class BodySet(unittest.TestCase):
    """body-manual-only: the manual of a body set sold apart, not a car's manual that names its body."""

    def test_body_set_manual(self):
        self.assertTrue(rules.is_body_set_doc("Tamiya 51578 body parts set: assembly manual", "doc/tamiya/spb-51578-manual"))

    def test_whole_car_manual_naming_its_body(self):
        self.assertFalse(rules.is_body_set_doc("Tamiya 47481 Super Avante (Painted Body) (TD4 Chassis): instruction manual", "doc/tamiya/47481-manual-de"))
        self.assertFalse(rules.is_body_set_doc("Carson 1:5 Chassis 100% RTR incl. Porsche Body: instruction manual", "doc/carson/x"))
        self.assertFalse(rules.is_body_set_doc("1/9 GP 4WD KIT DRX wo/Body: parts list", "doc/kyosho/31047-drx-parts-list-v01"))

    def test_missing_title(self):
        self.assertFalse(rules.is_body_set_doc(None, "doc/none"))


class TitleLanguage(unittest.TestCase):
    """title-language: Dutch, French, Spanish or German words in a title."""

    def test_localised_title_is_listed(self):
        self.assertTrue(re.search(rules.NON_ENGLISH, "Bekijk onze nieuwe buggy"))
        self.assertTrue(re.search(rules.NON_ENGLISH, "Guide de référence BX8SL"))

    def test_english_title(self):
        self.assertFalse(re.search(rules.NON_ENGLISH, "The new buggy"))
        self.assertFalse(re.search(rules.NON_ENGLISH, "Monster Van"))

    def test_own_language_files_keep_their_title(self):
        self.assertIn("manual", rules.OWN_LANGUAGE_FILES)
        self.assertIn("setup_sheet", rules.OWN_LANGUAGE_FILES)
        self.assertNotIn("video", rules.OWN_LANGUAGE_FILES)


class Brackets(unittest.TestCase):
    """name-unbalanced-bracket."""

    def test_unbalanced(self):
        self.assertTrue(rules.unbalanced("Shock Oil (500"))
        self.assertTrue(rules.unbalanced("Shock Oil 500)"))
        self.assertTrue(rules.unbalanced("Shock Oil （500"))
        self.assertFalse(rules.unbalanced("Shock Oil (500)"))
        self.assertFalse(rules.unbalanced("Shock Oil"))


if __name__ == "__main__":
    unittest.main()
