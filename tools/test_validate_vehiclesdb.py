"""python3 -I -m unittest discover -s tools -p test_validate_vehiclesdb.py (from the repository root)

A make's `vehiclesdb` is its VehiclesDB make page; a depicts `vehiclesdb` is a car page of the depicted make, whose
make has the same VehiclesDB slug (docs/schema.md "Makes", depicts).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate  # noqa: E402

MAKE = {"id": "make/mercedes-benz", "name": "Mercedes-Benz", "country": "DE", "notes": "German maker.",
        "vehiclesdb": "https://vehiclesdb.com/makes/mercedes-benz"}
UNIMOG = "https://vehiclesdb.com/trucks/mercedes-benz/unimog"


def release(depicts):
    return ("data/releases/x.toml", "release", {"id": "release/x/1", "depicts": depicts})


def errors_for(*docs):
    errors = []
    validate.check_vehiclesdb([("data/makes/mercedes-benz.toml", "make", MAKE)] + list(docs), errors)
    return errors


class VehiclesDBLinks(unittest.TestCase):
    def test_unimog_truck_link_is_valid(self):
        self.assertEqual(errors_for(release({"make": "Mercedes-Benz", "model": "Unimog", "vehiclesdb": UNIMOG})), [])

    def test_make_link_must_be_a_make_page(self):
        bad = dict(MAKE, vehiclesdb="https://vehiclesdb.com/cars/mercedes-benz/unimog")
        errors = []
        validate.check_vehiclesdb([("data/makes/m.toml", "make", bad)], errors)
        self.assertEqual(len(errors), 1)

    def test_kind_segment_must_be_a_kind(self):
        self.assertTrue(errors_for(release({"make": "Mercedes-Benz", "model": "Unimog", "vehiclesdb": "https://vehiclesdb.com/truck/mercedes-benz/unimog"})))

    def test_needs_the_make(self):
        self.assertTrue(errors_for(release({"model": "Unimog", "vehiclesdb": UNIMOG})))

    def test_make_must_have_a_link(self):
        plain = {k: v for k, v in MAKE.items() if k != "vehiclesdb"}
        errors = []
        validate.check_vehiclesdb([("data/makes/m.toml", "make", plain), release({"make": "Mercedes-Benz", "model": "Unimog", "vehiclesdb": UNIMOG})], errors)
        self.assertEqual(len(errors), 1)

    def test_car_slug_must_be_the_makes(self):
        self.assertTrue(errors_for(release({"make": "Mercedes-Benz", "model": "Unimog", "vehiclesdb": "https://vehiclesdb.com/trucks/ford/unimog"})))

    def test_car_link_on_a_body_part_too(self):
        part = ("data/parts/x.toml", "part", {"id": "part/x/1", "depicts": {"make": "Mercedes-Benz", "model": "Unimog", "vehiclesdb": UNIMOG}})
        self.assertEqual(errors_for(part), [])


if __name__ == "__main__":
    unittest.main()
