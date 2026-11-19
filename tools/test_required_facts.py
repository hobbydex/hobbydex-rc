"""Cases for the required facts rules (tools/required_facts.py, data/required-facts.toml).

    python3 -I tools/test_required_facts.py
"""
import os, sys, tomllib, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import required_facts as rf  # noqa: E402

REG = rf.parse(tomllib.loads('''
[servo]
exclude_name = '(?i)\\b(case|horns?)\\b'
facts = [
  { fact = "torque", label = "Torque", any = ["torque_kgcm"] },
  { fact = "size", label = "Size spec", any = ["spec/servo/"] },
]
[motor]
facts = [
  { fact = "can", label = "Can", any = ["can", "diameter_mm"] },
  { fact = "sensored", label = "Sensored", any = ["sensored"], when = { motor_type = ["brushless"] } },
]
[shock]
when = { shock_part = ["complete"] }
facts = [{ fact = "length", label = "Length", any = ["length_mm"] }]
'''))
SPECS = {"spec/motor/brushless-3652-3.175mm": {"can": "3652", "motor_type": "brushless"}}
PAGE = "https://maker.example/servo-1"


class Facts(unittest.TestCase):
    def test_missing_and_have(self):
        p = {"category": "servo", "name": "Servo 1", "torque_kgcm": 10}
        self.assertEqual(rf.status(p, REG, {}), {"torque": "have", "size": "missing"})
        p["equivalent_to"] = [{"spec": "spec/servo/standard-25t"}]
        self.assertEqual(rf.missing(p, REG, {}), [])

    def test_accessory_out_of_scope(self):
        self.assertEqual(rf.status({"category": "servo", "name": "Servo case (lower)"}, REG, {}), {})

    def test_category_without_facts(self):
        self.assertEqual(rf.status({"category": "chassis", "name": "Plate"}, REG, {}), {})

    def test_fact_read_from_linked_spec(self):
        p = {"category": "motor", "name": "Motor", "equivalent_to": [{"spec": "spec/motor/brushless-3652-3.175mm"}]}
        self.assertEqual(rf.status(p, REG, SPECS), {"can": "have", "sensored": "missing"})   # brushless by its spec

    def test_when_leaves_fact_out(self):
        self.assertEqual(rf.status({"category": "motor", "name": "540", "motor_type": "brushed", "can": "540"}, REG, {}), {"can": "have"})
        self.assertEqual(rf.status({"category": "motor", "name": "x", "can": "540"}, REG, {}), {"can": "have"})

    def test_false_is_stated(self):
        p = {"category": "motor", "name": "m", "motor_type": "brushless", "can": "3652", "sensored": False}
        self.assertEqual(rf.missing(p, REG, {}), [])

    def test_category_when(self):
        self.assertEqual(rf.status({"category": "shock", "name": "Shock body", "shock_part": "body"}, REG, {}), {})
        self.assertEqual(rf.status({"category": "shock", "name": "Shock", "shock_part": "complete"}, REG, {}), {"length": "missing"})

    def test_mark_unstated(self):
        p = {"category": "servo", "name": "Servo 1", "torque_kgcm": 10}
        self.assertEqual(rf.mark_unstated(p, PAGE, REG, {}), ["size"])
        self.assertEqual(p["unstated"], {"size": PAGE})
        self.assertEqual(rf.status(p, REG, {}), {"torque": "have", "size": "unstated"})
        self.assertEqual(rf.marker_problems(p, REG, {}), [])
        self.assertEqual(rf.mark_unstated(p, PAGE, REG, {}), [])   # nothing left to mark
        with self.assertRaises(ValueError):
            rf.mark_unstated({"category": "servo", "name": "s"}, "http://x", REG, {})

    def test_mark_only_given_facts(self):
        p = {"category": "servo", "name": "Servo 1"}
        self.assertEqual(rf.mark_unstated(p, "doc/maker/catalogue", REG, {}, facts=["torque"]), ["torque"])
        self.assertEqual(p["unstated"], {"torque": "doc/maker/catalogue"})

    def test_marker_problems(self):
        p = {"category": "servo", "name": "Servo 1", "torque_kgcm": 10,
             "unstated": {"torque": PAGE, "speed": PAGE, "size": "a page"}}
        self.assertEqual(rf.marker_problems(p, REG, {}), [
            "unstated size: source 'a page' is not an https URL or a doc id",
            "unstated speed: not a required fact of category servo"])
        self.assertEqual(rf.marker_problems({"category": "servo", "unstated": []}, REG, {}), ["unstated is not a table of fact = source"])

    def test_stale_marker_dropped(self):
        p = {"category": "servo", "name": "Servo 1", "torque_kgcm": 10, "unstated": {"torque": PAGE, "size": PAGE}}
        self.assertEqual(rf.stale_markers(p, REG, {}), ["torque"])
        self.assertEqual(rf.status(p, REG, {}), {"torque": "have", "size": "unstated"})
        self.assertEqual(rf.drop_stale(p, REG, {}), ["torque"])
        self.assertEqual(p["unstated"], {"size": PAGE})
        p["equivalent_to"] = [{"spec": "spec/servo/mini-25t"}]
        rf.drop_stale(p, REG, {})
        self.assertNotIn("unstated", p)

    def test_bad_registry(self):
        for bad in ('[servo]\nfacts = []', '[servo]\nfacts = [{ fact = "Torque", any = ["x"] }]',
                    '[servo]\nfacts = [{ fact = "t", any = [] }]', '[servo]\nfacts = [{ fact = "t", any = ["x"], when = { a = "b" } }]',
                    '[servo]\nfacts = [{ fact = "t", any = ["x"] }, { fact = "t", any = ["y"] }]'):
            with self.assertRaises(ValueError, msg=bad):
                rf.parse(tomllib.loads(bad))

    def test_the_data_registry_parses(self):
        reg = rf.load()
        self.assertIn("servo", reg)
        self.assertTrue(all(c.facts for c in reg.values()))


if __name__ == "__main__":
    unittest.main()
