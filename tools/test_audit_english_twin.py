"""non-english-link: a German maker link with its English twin beside it in the same record is resolved.

The record is the ScaleART switch panel 61000194 as it stands after hobbydex-rc#2462: the German shop
page and its English address are both in the links list. Run: python3 -I tools/test_audit_english_twin.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit  # noqa: E402

RECORD = """id = "part/scaleart/61000194"
brand = "brand/scaleart"
number = "61000194"
name = "Switch panel"
links = [
  { site = "ScaleART", url = "https://www.scaleart-shop.de/products/mittelkonsole-grau-lackiert" },
  { site = "ScaleART", url = "https://scaleart-shop.de/en-de/products/mittelkonsole-grau-lackiert" },
]
documents = ["doc/scaleart/scaleart-shop"]
category = "electronics"
"""
SWAPS = {"www.scaleart-shop.de": ("https://www.scaleart-shop.de/products/", "https://scaleart-shop.de/en-de/products/")}


def record():
    return RECORD


def test_german_link_with_english_twin_is_resolved():
    assert not audit.has_foreign_link(record(), SWAPS)


def test_german_link_alone_is_still_flagged():
    german_only = "\n".join(line for line in record().splitlines() if "en-de" not in line)
    assert audit.has_foreign_link(german_only, SWAPS)


def test_english_link_to_another_product_does_not_resolve():
    other = record().replace("en-de/products/mittelkonsole-grau-lackiert", "en-de/products/anderes-produkt")
    assert audit.has_foreign_link(other, SWAPS)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
