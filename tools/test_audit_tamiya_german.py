"""Cases for audit.tamiya_german_names: a Tamiya name with German words left is listed, with the words.

    python3 -I tools/test_audit_tamiya_german.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

GERMAN = {"Alugehäuse", "Gang"}


def words(name):   # stands in for hobbydex-tools translate_de.german_words
    return [w for w in name.replace("-", " ").split() if w in GERMAN]


def part(name, brand="tamiya"):
    return {"id": f"part/{brand}/1", "brand": f"brand/{brand}", "name": name}


def test_tamiya_name_with_german_word_is_listed_with_its_words():
    got = audit.tamiya_german_names([part("TA-05 Alugehäuse")], words)
    assert [w for _, w in got] == [["Alugehäuse"]]


def test_english_tamiya_name_is_not_listed():
    assert audit.tamiya_german_names([part("TA05 Aluminum Bulkhead")], words) == []


def test_other_brands_are_not_checked():
    assert audit.tamiya_german_names([part("CY 2-Gang gearbox", brand="carson")], words) == []


def test_record_without_a_name_is_skipped():
    assert audit.tamiya_german_names([{"id": "part/tamiya/2", "brand": "brand/tamiya"}], words) == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
