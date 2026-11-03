"""python3 -I -m unittest discover -s tools -p test_validate_gtin.py (from the repository root)

A part or release gtin is 8, 12, 13 or 14 digits with a valid GS1 check digit and is not a placeholder: the example
code 1234567890128 and counted or repeated digits pass the check digit but were never printed on a product.
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

REAL = ["8718057261863", "5056135754511", "4950344182114", "784695272330", "96385074"]   # 96385074 is a GTIN-8


class GtinProblem(unittest.TestCase):
    def test_real_codes_pass(self):
        for code in REAL:
            with self.subTest(code=code):
                self.assertIsNone(validate.gtin_problem(code))

    def test_placeholders_are_refused_with_valid_check_digit(self):
        for code in ["1234567890128", "0000000000000", "1111111111116", "123456789012", "0123456789012"]:
            with self.subTest(code=code):
                self.assertIsNotNone(validate.gtin_problem(code))

    def test_url_length_and_check_digit_are_refused(self):
        self.assertIn("not 8, 12, 13 or 14 digits", validate.gtin_problem("https://www.toprc.nl/fms.html"))
        self.assertIn("not 8, 12, 13 or 14 digits", validate.gtin_problem("12345678901"))
        self.assertIn("check digit", validate.gtin_problem("5056135754512"))


if __name__ == "__main__":
    unittest.main()
