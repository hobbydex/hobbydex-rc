"""Cases for audit.german_names: a name with German words left is listed, with the words, in every brand.

    python3 -I tools/test_audit_name_german.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

GERMAN = {"Alugehäuse", "Gang", "Nür"}


def words(name):   # stands in for hobbydex-tools translate_de.german_words
    return [w for w in name.replace("-", " ").replace("Ⅱ", " ").split() if w in GERMAN]


def part(name, brand="tamiya", **extra):
    return {"id": f"part/{brand}/1", "brand": f"brand/{brand}", "name": name, **extra}


def test_name_with_german_word_is_listed_with_its_words():
    got = audit.german_names([part("TA-05 Alugehäuse")], words)
    assert [w for _, w in got] == [["Alugehäuse"]]


def test_english_name_is_not_listed():
    assert audit.german_names([part("TA05 Aluminum Bulkhead")], words) == []


def test_every_brand_is_checked():
    got = audit.german_names([part("CY 2-Gang gearbox", brand="carson")], words)
    assert [w for _, w in got] == [["Gang"]]


def test_name_from_an_english_page_is_the_makers_english():
    rel = part("MINI-Z AWD NISSAN SKYLINE GT-R R34 V.specⅡNür White", brand="kyosho",
               sources={"name": "https://rc.kyosho.com/en/32629w.html"})
    assert audit.german_names([rel], words) == []
    rel["sources"] = {"name": "https://rc.kyosho.com/ja/32629w.html"}
    assert len(audit.german_names([rel], words)) == 1


def test_record_without_a_name_is_skipped():
    assert audit.german_names([{"id": "part/tamiya/2", "brand": "brand/tamiya"}], words) == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
