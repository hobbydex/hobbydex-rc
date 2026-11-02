"""No Yeah Racing model kit is one that data/retired.toml retired.

The kit ids are the ones the Yeah Racing importer gives its car models (the MODELS table in
hobbydex-tools/tools/import_yeah_racing.py). Update this list when that table changes.

    python3 -I tools/test_yeah_models_not_retired.py
"""
import os
import tomllib
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RC = os.path.dirname(HERE)

MADE = [
    "kit/tamiya/tt-02-type-s",
    "kit/tamiya/tt-02b",
    "kit/tamiya/tt-02",
    "kit/tamiya/tt-01e",
    "kit/tamiya/xv-01",
    "kit/tamiya/dt-02",
    "kit/tamiya/dt-03",
    "kit/tamiya/dt-04",
    "kit/tamiya/mb-01",
    "kit/tamiya/bt-01",
    "kit/tamiya/m-05",
    "kit/tamiya/m-06",
    "kit/tamiya/xm-01",
    "kit/tamiya/gf-02",
    "kit/traxxas/trx-4m",
    "kit/traxxas/trx-4",
    "kit/axial/scx24",
    "kit/kyosho/mini-z-mr-04",
    "kit/kyosho/mini-z-awd",
    "kit/kyosho/mini-z-buggy",
    "kit/kyosho/ultima",
    "kit/kyosho/optima",
    "kit/kyosho/fazer-mk2",
    "kit/team-associated/rc10",
    "kit/team-associated/rc10b7",
    "kit/yokomo/super-dog-fighter",
    "kit/losi/micro-b",
]


class YeahModelsNotRetired(unittest.TestCase):
    def test_no_model_is_a_retired_kit(self):
        with open(os.path.join(RC, "data", "retired.toml"), "rb") as f:
            retired = {r["id"] for r in tomllib.load(f).get("retired", [])}
        self.assertFalse(set(MADE) & retired, set(MADE) & retired)


if __name__ == "__main__":
    unittest.main()
