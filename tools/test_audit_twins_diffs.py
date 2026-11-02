"""Cases for the twin-parts and too-many-diffs checks in tools/audit.py.

The Tamiya case reads one record of this repository's own data. Run from the repo root:

    python3 -I tools/test_audit_twins_diffs.py
"""
import importlib.util
import os
import tomllib
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RC = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def part(pid, brand, name, number=None, category="differential", **extra):
    return {"id": pid, "brand": brand, "name": name, "number": number or pid.split("/")[-1],
            "category": category, **extra}


class CompleteDiff(unittest.TestCase):
    def test_whole_assemblies_count(self):
        for name in ("Differential Assembly", "Diff Set Complete", "Complete Differential",
                     "Assembled Differential", "Front Complete Diff", "Differential complete",
                     "Zorro Brushless Complete Centre Differential Unit", "Center Differential Assembly",
                     "Assembled Front/Rear Differential Set", "Diff. Assembly"):
            with self.subTest(name=name):
                self.assertTrue(audit.complete_diff(part("part/x/1", "brand/x", name)))

    def test_cases_gears_cups_and_other_components_do_not(self):
        for name in ("Gear Differential Unit Cup Joint Set",   # Tamiya TA06 false case (qty 12 in its kit)
                     "Differential Case Set", "Differential Gear Set", "Diff Gear Set",
                     "Complete Differential (Steel Gears/Diff. Cups)", "Diff Cup Joint Complete",
                     "Complete Diff Gasket Set", "Complete Diff Shim Pack", "Complete Diff O-Ring Set",
                     "Differential Set", "Diff. Unit", "Differential Housing For F113"):
            with self.subTest(name=name):
                self.assertFalse(audit.complete_diff(part("part/x/1", "brand/x", name)))

    def test_category_must_be_differential(self):
        self.assertFalse(audit.complete_diff(part("part/x/1", "brand/x", "Complete Differential", category="screw")))

    def test_real_tamiya_false_case(self):
        with open(os.path.join(RC, "data", "parts", "tamiya", "51", "51466.toml"), "rb") as f:
            ta06 = tomllib.load(f)
        self.assertEqual(ta06["name"], "TA06 Gear Differential Unit Cup Joint Set")
        self.assertFalse(audit.complete_diff(ta06))


class TooManyDiffs(unittest.TestCase):
    def setUp(self):
        self.part_of = {p["id"]: p for p in (
            part("part/x/A", "brand/x", "Front Differential Assembly"),
            part("part/x/B", "brand/x", "Rear Differential Assembly"),
            part("part/x/C", "brand/x", "Center Differential Assembly"),
            part("part/x/D", "brand/x", "Assembled Differential Set"),
            part("part/x/G", "brand/x", "Differential Gear Set"),
            part("part/x/T", "brand/x", "Gear Differential Unit Cup Joint Set"),
        )}

    def release(self, *rows):
        return {"id": "release/x/r", "contains": [{"part": p, "role": role, **({"qty": q} if q else {})}
                                                    for p, role, q in rows]}

    def test_four_assemblies_flag(self):
        r = self.release(*[(p, "kit", None) for p in ("part/x/A", "part/x/B", "part/x/C", "part/x/D")])
        self.assertEqual(audit.diff_assemblies(r, self.part_of), 4)

    def test_three_do_not(self):
        r = self.release(*[(p, "kit", None) for p in ("part/x/A", "part/x/B", "part/x/C")])
        self.assertEqual(audit.diff_assemblies(r, self.part_of), 3)

    def test_qty_counts(self):
        r = self.release(("part/x/A", "kit", 2), ("part/x/B", "kit", 2))
        self.assertEqual(audit.diff_assemblies(r, self.part_of), 4)

    def test_only_kit_rows_count(self):
        r = self.release(("part/x/A", "kit", None), ("part/x/B", "option", None), ("part/x/C", "listed", None),
                         ("part/x/D", "option", 3))
        self.assertEqual(audit.diff_assemblies(r, self.part_of), 1)

    def test_false_cases_do_not_count(self):
        r = self.release(("part/x/G", "kit", 6), ("part/x/T", "kit", 12))
        self.assertEqual(audit.diff_assemblies(r, self.part_of), 0)


class TwinParts(unittest.TestCase):
    brands = {
        "brand/hpi": {"id": "brand/hpi", "website": "https://www.hpiracing.com", "owner": None},
        "brand/maverick": {"id": "brand/maverick", "website": "https://www.maverick-rc.com", "owner": "company/hpi-racing"},
        "brand/other": {"id": "brand/other", "website": "https://www.other-rc.com", "owner": None},
        "brand/blackzon": {"id": "brand/blackzon", "website": "https://www.blackzon.de", "owner": "company/hpi-racing"},
    }
    companies = {"company/hpi-racing": {"id": "company/hpi-racing", "brand": "brand/hpi"}}
    docs = {
        "doc/hpi/list": {"id": "doc/hpi/list", "brand": "brand/hpi"},
        "doc/maverick/list": {"id": "doc/maverick/list", "brand": "brand/maverick"},
        "doc/other/list": {"id": "doc/other/list", "brand": "brand/other"},
    }

    def test_related_brands_each_citing_own_source_are_shared(self):
        a = part("part/hpi/1", "brand/hpi", "LOCK NUT M2.5", documents=["doc/hpi/list"])
        b = part("part/maverick/1", "brand/maverick", "LOCK NUT M2.5", documents=["doc/maverick/list"])
        self.assertEqual(audit.twin_class(a, b, self.brands, self.companies, self.docs), "shared")

    def test_own_site_link_counts_as_own_source(self):
        a = part("part/hpi/1", "brand/hpi", "LOCK NUT", links=[{"url": "https://hpiracing.com/x"}])
        b = part("part/maverick/1", "brand/maverick", "LOCK NUT", links=[{"url": "https://www.maverick-rc.com/p"}])
        self.assertEqual(audit.twin_class(a, b, self.brands, self.companies, self.docs), "shared")

    def test_unrelated_brands_are_unclear(self):
        a = part("part/other/1", "brand/other", "25605", documents=["doc/other/list"])
        b = part("part/hpi/1", "brand/hpi", "25605", documents=["doc/hpi/list"])
        self.assertEqual(audit.twin_class(a, b, self.brands, self.companies, self.docs), "unclear")

    def test_other_brands_site_is_a_copy(self):
        # a BlackZon record that cites the Maverick site (owned by HPI, so related): not shared
        a = part("part/blackzon/1", "brand/blackzon", "Diff Shaft", links=[{"url": "https://www.maverick-rc.com/x"}])
        b = part("part/maverick/1", "brand/maverick", "Diff Shaft", documents=["doc/maverick/list"])
        self.assertEqual(audit.twin_class(a, b, self.brands, self.companies, self.docs), "copy")

    def test_other_brands_document_is_a_copy(self):
        a = part("part/other/1", "brand/other", "25605", documents=["doc/hpi/list"])
        b = part("part/hpi/1", "brand/hpi", "25605", documents=["doc/hpi/list"])
        self.assertEqual(audit.twin_class(a, b, self.brands, self.companies, self.docs), "copy")

    def test_pairs_need_one_number_and_one_name(self):
        same = [part("part/hpi/1", "brand/hpi", "Lock Nut"), part("part/maverick/1", "brand/maverick", "lock-nut")]
        other_name = [part("part/hpi/2", "brand/hpi", "Lock Nut"), part("part/maverick/2", "brand/maverick", "Nut")]
        other_number = [part("part/hpi/3", "brand/hpi", "Lock Nut"), part("part/maverick/4", "brand/maverick", "Lock Nut", number="4")]
        self.assertEqual(len(audit.twin_pairs(same + other_name + other_number)), 1)


if __name__ == "__main__":
    unittest.main()
