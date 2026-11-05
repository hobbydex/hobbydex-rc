"""ocr-number-twins: a pair whose both numbers a maker text layer prints leaves the class; a pair with one printed
number stays. The index is a small fixture written to a temporary folder (the cache is never read here).

Run: python3 -I tools/test_audit_twins_text_layer.py
"""
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

INDEX = """# tamiya: full-length numbers in the text layers of 2 PDFs
number\tname\tcount
10115241\tK Parts\t1
10115247\tK Parts\t1
19225101\tZ Parts\t2
"""


def part(number):
    return {"id": f"part/tamiya/{number}", "number": number, "name": "K Parts"}


class TextLayerTwins(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "text-layer-numbers.tsv")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(INDEX)

    def tearDown(self):
        self.dir.cleanup()

    def test_index_gives_its_first_column_only(self):
        self.assertEqual(audit.text_layer_numbers(self.path), {"10115241", "10115247", "19225101"})

    def test_missing_index_gives_no_numbers(self):
        self.assertEqual(audit.text_layer_numbers(os.path.join(self.dir.name, "none.tsv")), set())
        self.assertEqual(audit.text_layer_numbers(""), set())

    def test_both_printed_leaves_the_class(self):
        printed = audit.text_layer_numbers(self.path)
        self.assertTrue(audit.printed_pair(part("10115241"), part("10115247"), printed))

    def test_one_printed_stays_in_the_class(self):
        printed = audit.text_layer_numbers(self.path)
        self.assertFalse(audit.printed_pair(part("19225101"), part("19225187"), printed))

    def test_nothing_printed_stays_in_the_class(self):
        self.assertFalse(audit.printed_pair(part("10115241"), part("10115247"), set()))


if __name__ == "__main__":
    unittest.main()
