"""Cases for audit.tamiya_maker_linked: a Tamiya record with a capture of its maker's gone product page has a maker link.

    python3 -I tools/test_audit_tamiya_item.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

CAPTURE = "https://web.archive.org/web/20060320220448/http://www.tamiyausa.com:80/product/item.php?product-id=40101"


def test_archive_capture_of_tamiya_usa_is_a_maker_link():
    assert audit.tamiya_maker_linked([{"site": "Tamiya USA (Internet Archive)", "url": CAPTURE, "kind": "archive"}])


def test_archive_capture_of_tamiya_english_page_is_a_maker_link():
    url = "https://web.archive.org/web/20131201011405/http://www.tamiya.com:80/english/products/56338/index.htm"
    assert audit.tamiya_maker_linked([{"site": "Tamiya (Internet Archive)", "url": url, "kind": "archive"}])


def test_live_tamiya_link_and_maker_kind_still_count():
    assert audit.tamiya_maker_linked([{"site": "Tamiya", "url": "https://www.tamiya.com/japan/products/51331/index.html"}])
    assert audit.tamiya_maker_linked([{"site": "Tamiya USA", "url": "https://www.tamiyausa.com/shop/x", "kind": "maker"}])


def test_dealer_and_fan_site_captures_do_not_count():
    assert not audit.tamiya_maker_linked([{"site": "TamiyaBase", "url": "https://www.tamiyabase.com/parts/7619-51331", "kind": "fan-site"}])
    assert not audit.tamiya_maker_linked([{"site": "tamico.de", "url": "https://tamico.de/x", "kind": "dealer"}])
    assert not audit.tamiya_maker_linked([{"site": "RC", "url": "https://web.archive.org/web/20100101000000/https://www.example.com/x", "kind": "archive"}])


def test_archive_capture_of_a_non_maker_page_does_not_count():
    url = "https://web.archive.org/web/20100101000000/https://www.hobbyking.com/product/51331"
    assert not audit.tamiya_maker_linked([{"site": "HobbyKing (Internet Archive)", "url": url, "kind": "archive"}])


def test_no_links():
    assert not audit.tamiya_maker_linked([])


def test_label_only_spares():
    assert audit.tamiya_label_only({"name": "A Parts", "name_source": "ocr", "category": "parts-tree"})
    assert audit.tamiya_label_only({"name": "Differential Gear Bag", "name_source": "ocr", "category": "hardware-set"})
    assert not audit.tamiya_label_only({"name": "Idler Gear", "name_source": "ocr", "category": "gear"})
    assert not audit.tamiya_label_only({"name": "Differential Gear Bag", "name_source": "manual", "category": "hardware-set"})


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
