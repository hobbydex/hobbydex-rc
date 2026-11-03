"""audit.kit_without_release: a kit with no release is flagged by fits-kit-no-release, except a family kit
(family = true: a platform or family label that parts fit, no single car sold under it; docs/schema.md "kit").

    python3 -I tools/test_audit_family_kit.py
"""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

PLAIN = "kit/wedico/plain-truck"
FAMILY = "kit/wedico/mercedes-actros"
CAR = "kit/kyosho/some-car"


class FamilyKitTest(unittest.TestCase):
    kits = {
        PLAIN: {"id": PLAIN, "brand": "brand/wedico", "name": "Plain"},
        FAMILY: {"id": FAMILY, "brand": "brand/wedico", "name": "Mercedes-Benz Actros", "family": True},
        CAR: {"id": CAR, "brand": "brand/kyosho", "name": "Some car"},
    }
    rels_of_kit = {CAR: ["release/kyosho/1"]}

    def test_kit_without_release_is_flagged(self):
        self.assertTrue(audit.kit_without_release(self.kits, self.rels_of_kit, PLAIN))

    def test_family_kit_without_release_is_skipped(self):
        self.assertFalse(audit.kit_without_release(self.kits, self.rels_of_kit, FAMILY))

    def test_kit_with_release_is_not_flagged(self):
        self.assertFalse(audit.kit_without_release(self.kits, self.rels_of_kit, CAR))

    def test_unknown_or_missing_kit_is_not_flagged(self):
        self.assertFalse(audit.kit_without_release(self.kits, self.rels_of_kit, "kit/x/none"))
        self.assertFalse(audit.kit_without_release(self.kits, self.rels_of_kit, None))

    def test_family_false_is_flagged_like_no_field(self):
        kits = dict(self.kits)
        kits[PLAIN] = dict(kits[PLAIN], family=False)
        self.assertTrue(audit.kit_without_release(kits, self.rels_of_kit, PLAIN))


if __name__ == "__main__":
    unittest.main()
