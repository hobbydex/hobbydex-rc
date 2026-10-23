import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import validate


class RestatedName(unittest.TestCase):
    def bad(self, name, former, brand=""):
        return validate.former_names_problems({"name": name, "former_names": former}, brand)

    def test_brand_word_in_front_restates(self):
        self.assertEqual(self.bad("Pin", ["HUDY PIN"], "HUDY"), ["HUDY PIN"])
        self.assertEqual(self.bad("Bearing Grease - Blue", ["HUDY BEARING GREASE - BLUE"], "HUDY"),
                         ["HUDY BEARING GREASE - BLUE"])

    def test_brand_word_needs_the_brand(self):
        self.assertEqual(self.bad("Pin", ["HUDY PIN"]), [])
        self.assertEqual(self.bad("Pin", ["HUDY PIN"], "XRAY"), [])

    def test_catalogue_number_in_front_restates(self):
        self.assertEqual(self.bad("1621 Parts Screws F5274", ["1625 Parts Screws F5274"]), ["1625 Parts Screws F5274"])
        self.assertEqual(self.bad("Big Shock Spring", ["714 Big Shock Spring"]), ["714 Big Shock Spring"])
        self.assertEqual(self.bad("REMO 1621 Pin", ["Pin"], "REMO"), ["Pin"])

    def test_real_renames_stay(self):
        self.assertEqual(self.bad("Hex Socket Screws", ["Hex Socket Tapping Screws"], "REMO"), [])
        self.assertEqual(self.bad("Pin 2", ["Pin"], "HUDY"), [])
        self.assertEqual(self.bad("Pin 3x12", ["Pin 3x14"], "HUDY"), [])

    def test_repeat_still_rejected(self):
        self.assertEqual(self.bad("Pin", ["Shaft", "shaft"]), ["shaft"])


if __name__ == "__main__":
    unittest.main()
