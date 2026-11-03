"""python3 -I -m unittest discover -s tools -p test_validate_universal_class.py (from the repository root)

A universal part of basis size may keep an applies_to that names only a vehicle class (and a scale); a named car,
a brand + model or a chassis is refused, and so is any other basis.
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate


class ClassOnly(unittest.TestCase):
    def test_classes(self):
        for v in ("Buggy", "Truggy", "Short Course", "Stadium Truck", "Rock Crawlers", "Fit for 1/10 RC Touring Car",
                  "1/8 on-road", "Monster Truck", "Off-Road Buggy"):
            self.assertTrue(validate.class_only_applies_to(v), v)

    def test_named_cars(self):
        for v in ("Wasteland Buggy", "Losi 1/5 Desert Buggy", "Kyosho Inferno Truggy", "Mugen MBX-7 Super Touring", "SCX10 Rock Crawler",
                  "1/10", "", "Traxxas Slash"):
            self.assertFalse(validate.class_only_applies_to(v), v)


if __name__ == "__main__":
    unittest.main()
