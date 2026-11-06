"""python3 -I -m unittest discover -s tools -p test_validate_spring_pin.py (from the repository root)

A spring pin spec has a nominal diameter of ISO 8752 / ISO 8750, a length from 2 to 100 mm, an id with its type
when it has one, and the standard its type gives (none without a type). Other specs are not its business.
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

GOOD = dict(id="spec/spring-pin/slotted-2x10", category="spring-pin", name="2x10mm slotted spring pin",
            type="slotted", diameter_mm=2, length_mm=10, standards=["ISO 8752"])


def problems(**changes):
    d = dict(GOOD)
    for k, v in changes.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    return validate.spring_pin_problems("spec/spring-pin/x.toml", d)


class SpringPinSpec(unittest.TestCase):
    def test_typed_and_untyped_pass(self):
        self.assertEqual(problems(), [])
        self.assertEqual(problems(id="spec/spring-pin/coiled-2.5x12", type="coiled", diameter_mm=2.5, length_mm=12, standards=["ISO 8750"]), [])
        self.assertEqual(problems(id="spec/spring-pin/1.5x8", type=None, standards=None, diameter_mm=1.5, length_mm=8), [])

    def test_diameter_must_be_a_standard_size(self):
        self.assertTrue(problems(id="spec/spring-pin/slotted-1.6x10", diameter_mm=1.6))
        self.assertTrue(problems(diameter_mm=None))

    def test_length_range(self):
        self.assertTrue(problems(id="spec/spring-pin/slotted-2x1", length_mm=1))
        self.assertTrue(problems(id="spec/spring-pin/slotted-2x101", length_mm=101))

    def test_id_must_state_the_type(self):
        self.assertTrue(problems(id="spec/spring-pin/2x10"))
        self.assertTrue(problems(type=None, standards=None))

    def test_standard_follows_the_type(self):
        self.assertTrue(problems(standards=["ISO 8750"]))
        self.assertTrue(problems(type=None, id="spec/spring-pin/2x10"))   # no type: no standard may be cited
        self.assertTrue(problems(standards=[]))


if __name__ == "__main__":
    unittest.main()
