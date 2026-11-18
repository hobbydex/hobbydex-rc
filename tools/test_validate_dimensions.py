"""python3 -I -m unittest discover -s tools -p test_validate_dimensions.py (from the repository root)

A kit or release states its size and weight in a `dimensions` table: millimetres and grams, each a number, a range
{ min, max } or (wheelbase and track) a list of configurable { mm, label } values, with the maker page as `source`.
A body states the wheelbase and track it is made for in the same forms.
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

SRC = "https://www.tamiya.com/english/products/58700/index.html"
IDS = {"doc/tamiya/58700-product-page": "x"}


def kit(**dims):
    return validate.dimension_problems("kits/x.toml", "kit", {"id": "kit/tamiya/m-07", "dimensions": dims}, IDS)


def body(**fields):
    d = {"id": "part/tamiya/51700", "category": "body", **fields}
    return validate.dimension_problems("parts/x.toml", "part", d, IDS)


class Dimensions(unittest.TestCase):
    def test_good_tables_pass(self):
        self.assertEqual(kit(length_mm=388, width_mm=171.5, height_mm=130, wheelbase_mm=239, track_front_mm=148,
                             track_rear_mm=148, weight_g=1200, source=SRC), [])
        self.assertEqual(kit(wheelbase_mm=[{"mm": 239, "label": "L"}, {"mm": 225, "label": "M"}, {"mm": 210, "label": "S"}],
                             source="doc/tamiya/58700-product-page"), [])
        self.assertEqual(kit(wheelbase_mm={"min": 256, "max": 262}, track_mm=170, source=SRC), [])
        self.assertEqual(kit(weight_g=3084, stated={"weight_g": "6.8 lb"}, source=SRC), [])

    def test_source_required(self):
        self.assertTrue(kit(wheelbase_mm=257))
        self.assertTrue(kit(wheelbase_mm=257, source="tamiya.com"))
        self.assertTrue(kit(wheelbase_mm=257, source="doc/tamiya/unknown"))

    def test_values(self):
        self.assertTrue(kit(wheelbase_mm=0, source=SRC))
        self.assertTrue(kit(wheelbase_mm="257", source=SRC))
        self.assertTrue(kit(wheelbase_mm={"min": 262, "max": 256}, source=SRC))
        self.assertTrue(kit(wheelbase_mm=[{"mm": 239}], source=SRC))          # one option is a number
        self.assertTrue(kit(wheelbase_mm=[{"mm": 239}, {"mm": 239}], source=SRC))
        self.assertTrue(kit(length_mm=[{"mm": 388}, {"mm": 400}], source=SRC))   # options only for wheelbase and track
        self.assertTrue(kit(weight_g=True, source=SRC))
        self.assertTrue(kit(weight_g=200000, source=SRC))

    def test_fields(self):
        self.assertTrue(kit(source=SRC))
        self.assertTrue(kit(wheelbase_in=10, source=SRC))
        self.assertTrue(kit(track_mm=170, track_front_mm=170, source=SRC))
        self.assertTrue(kit(weight_g=3084, stated={"length_mm": "21 in"}, source=SRC))
        self.assertTrue(validate.dimension_problems("parts/x.toml", "part", {"dimensions": {"weight_g": 1, "source": SRC}}, IDS))

    def test_body(self):
        self.assertEqual(body(wheelbase_mm=257, width_mm=190, track_mm=172), [])
        self.assertEqual(body(wheelbase_mm={"min": 251, "max": 257}), [])
        self.assertTrue(body(wheelbase_mm=-1))
        self.assertTrue(body(track_mm=172, track_rear_mm=172))
        self.assertTrue(validate.dimension_problems("parts/x.toml", "part", {"category": "tire", "track_mm": 172}, IDS))


if __name__ == "__main__":
    unittest.main()
