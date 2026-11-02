"""non-english-link: a German maker link with its English twin beside it in the same record is resolved.

The fixture is the ScaleART switch panel 61000194 as it stands after hobbydex-rc#2462: the German shop
page and its English address are both in the links list. Run: python3 -I tools/test_audit_english_twin.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit  # noqa: E402

FIXTURE = os.path.join(HERE, "..", "tests", "fixtures", "scaleart", "61000194.toml")
SWAPS = {"www.scaleart-shop.de": ("https://www.scaleart-shop.de/products/", "https://scaleart-shop.de/en-de/products/")}


def record():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


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
