"""python3 -I -m unittest discover -s tools -p test_validate_inch_screw.py (from the repository root)

An inch screw spec (UNC or UNF thread) states length_in as a reduced inch fraction, never length_mm, and its id is
spec/screw/<standard>-<thread>x<length>in-<head>-<drive>. Other specs and a bad id or length are refused.
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

GOOD = dict(id="spec/screw/unc-4-40x1-2in-button-hex", category="screw", name="4-40 UNC x 1/2 in button head screw, hex socket",
            thread="4-40", thread_standard="UNC", length_in="1/2", head="button", drive="hex")


def problems(**changes):
    d = dict(GOOD)
    for k, v in changes.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    return validate.inch_screw_problems("spec/screw/x.toml", d)


class InchScrewSpec(unittest.TestCase):
    def test_good_spec_passes(self):
        self.assertEqual(problems(), [])

    def test_mixed_and_whole_lengths_are_ids(self):
        self.assertEqual(problems(id="spec/screw/unc-4-40x1_1-4in-socket-cap-hex", head="socket-cap", length_in="1 1/4"), [])
        self.assertEqual(problems(id="spec/screw/unc-2-56x2in-socket-cap-hex", thread="2-56", length_in="2", head="socket-cap"), [])
        self.assertEqual(problems(id="spec/screw/unf-10-32x3-8in-set-hex", thread="10-32", thread_standard="UNF", length_in="3/8", head="set"), [])

    def test_self_tapping_id_ends_tapping(self):
        d = dict(GOOD, id="spec/screw/unc-4-40x1-2in-button-hex-tapping", thread_type="self-tapping")
        self.assertEqual(validate.inch_screw_problems("x", d), [])

    def test_length_mm_is_refused(self):
        self.assertTrue(any("no length_mm" in p for p in problems(length_mm=12.7)))

    def test_length_must_be_a_reduced_fraction(self):
        for bad in ("2/4", "0.5", "3/2", "1/3", "0", "1 2/4"):
            self.assertTrue(any("length_in" in p for p in problems(length_in=bad)), bad)

    def test_id_must_match(self):
        self.assertTrue(any("id should be" in p for p in problems(id="spec/screw/m4x12-button-hex")))
        self.assertTrue(any("id should be" in p for p in problems(id="spec/screw/unc-4-40x1-2in-socket-cap-hex")))

    def test_thread_and_standard(self):
        self.assertTrue(any("thread_standard" in p for p in problems(thread_standard=None)))
        self.assertTrue(any("thread like" in p for p in problems(thread="M4")))

    def test_drive_is_listed(self):
        self.assertTrue(any("drive" in p for p in problems(drive=None)))

    def test_only_screws(self):
        self.assertTrue(problems(category="pin"))


if __name__ == "__main__":
    unittest.main()
