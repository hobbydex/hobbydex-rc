"""python3 -I -m unittest discover -s tools -p test_validate_spec_fields.py (from the repository root)

A category's spec_fields (docs/schema.md "Spec fields") type the values of its parts: a cited value needs its page in
`sources`, has the type and range its entry sets and sits only on the parts its `when` names.
"""
import os, sys, tomllib, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "..", "data", "categories", "radio.toml"), "rb") as fh:
    RADIO = tomllib.load(fh)
FIELDS = RADIO["spec_fields"]
IDS = {"part/radiolink/R8FG": "x"}
SRC = "https://www.radiolink.com/rc8p"


def errors(**extra):
    d = {"id": "part/radiolink/RC8P", "category": "radio", "radio_unit": "set"}
    d.update(extra)
    return validate.spec_field_problems("p.toml", d, FIELDS, IDS)


class SpecFields(unittest.TestCase):
    def test_the_radio_definition_is_valid(self):
        self.assertEqual(validate.spec_field_def_problems("radio.toml", RADIO), [])

    def test_a_radio_set_with_its_spec(self):
        vals = dict(latency_ms=[3, 4, 14], operating_v=[3.4, 4.2], range_m=600, model_memory=30, battery=["18650"],
                    battery_included=True, outputs=["PWM", "S.BUS"], antenna="built-in",
                    compatible_receivers=["part/radiolink/R8FG", "R16SM"])
        self.assertEqual(errors(sources={k: SRC for k in vals}, **vals), [])

    def test_a_value_without_its_page(self):
        self.assertTrue(any("needs sources.range_m" in e for e in errors(range_m=600)))

    def test_bad_values(self):
        for field, v in (("outputs", ["SBUS"]), ("operating_v", [12, 3]), ("latency_ms", 3), ("antenna", "triple"),
                         ("compatible_receivers", ["part/radiolink/NOPE"]), ("battery_included", "yes")):
            self.assertTrue(errors(sources={field: SRC}, **{field: v}), field)

    def test_a_transmitter_field_on_a_receiver(self):
        es = validate.spec_field_problems("p.toml", {"radio_unit": "receiver", "latency_ms": [3], "sources": {"latency_ms": SRC}}, FIELDS, IDS)
        self.assertTrue(any("only on parts with radio_unit" in e for e in es))

    def test_a_bad_definition(self):
        self.assertTrue(validate.spec_field_def_problems("c.toml", {"spec_fields": [{"field": "x", "label": "X", "type": "enum"}]}))


if __name__ == "__main__":
    unittest.main()
