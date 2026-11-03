"""Cases for the doc-placeholder-title check in tools/audit.py.

A document title that is only item numbers, or that repeats one token, is the placeholder the old
Tamiya importer wrote ("Tamiya 43501 43501: instruction manual"). A title that keeps a single number
("Tamiya 43501: ...") or a model code that is the whole genuine title ("BD11", a video) is not flagged.

    python3 -I tools/test_audit_placeholder_title.py
"""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PlaceholderTitle(unittest.TestCase):
    def test_repeated_item_number_is_flagged(self):
        self.assertTrue(audit.placeholder_title("Tamiya 43501 43501: instruction manual (tamiyausa.com, archived)"))
        self.assertTrue(audit.placeholder_title("Tamiya 58449 58449: supplement"))
        self.assertTrue(audit.placeholder_title("Kyosho KF01 KF01 Type 3: instructions"))
        self.assertTrue(audit.placeholder_title("PR Racing product page: 2023 2023 PR SB401-R"))

    def test_number_only_title_is_flagged(self):
        self.assertTrue(audit.placeholder_title("43501"))
        self.assertTrue(audit.placeholder_title("43501 43502"))

    def test_single_number_and_names_are_not_flagged(self):
        self.assertFalse(audit.placeholder_title("Tamiya 43501: instruction manual"))
        self.assertFalse(audit.placeholder_title("Tamiya 22007 Silicone Oil #5000: product page"))
        self.assertFalse(audit.placeholder_title("XRAY XB9 2026 spare parts list"))
        self.assertFalse(audit.placeholder_title("BD11"))   # a genuine video title: a model code, not a number
        self.assertFalse(audit.placeholder_title(""))
        self.assertFalse(audit.placeholder_title(None))


if __name__ == "__main__":
    unittest.main()
