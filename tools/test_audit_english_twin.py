"""non-english-link: a German maker link with its English twin beside it in the same record is resolved, and a
link whose English address the crawl found gone is not listed.

The record is the ScaleART switch panel 61000194 as it stands after hobbydex-rc#2462: the German shop
page and its English address are both in the links list. Run: python3 -I tools/test_audit_english_twin.py
"""
import os, sqlite3, sys, tempfile

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


def test_german_link_whose_english_twin_is_gone_is_not_listed():
    german_only = "\n".join(line for line in record().splitlines() if "en-de" not in line)
    gone = frozenset({"https://scaleart-shop.de/en-de/products/mittelkonsole-grau-lackiert"})
    assert not audit.has_foreign_link(german_only, SWAPS, gone)


def test_pending_english_twin_is_still_listed():
    german_only = "\n".join(line for line in record().splitlines() if "en-de" not in line)
    pending = frozenset({"https://scaleart-shop.de/en-de/products/other"})
    assert audit.has_foreign_link(german_only, SWAPS, pending)


def test_gone_urls_reads_only_gone_rows_of_the_english_hosts():
    with tempfile.TemporaryDirectory() as cache:
        con = sqlite3.connect(os.path.join(cache, "crawl.db"))
        con.execute("create table queue (url text primary key, path text, host text, status text)")
        rows = [
            ("https://scaleart-shop.de/en-de/products/a", "scaleart-shop.de", "gone"),
            ("https://scaleart-shop.de/en-de/products/b", "scaleart-shop.de", "done"),
            ("https://www.scaleart-shop.de/products/c", "www.scaleart-shop.de", "gone"),
        ]
        con.executemany("insert into queue values (?, '', ?, ?)", [(u, h, s) for u, h, s in rows])
        con.commit()
        con.close()
        gone = audit.gone_urls(cache, SWAPS)
    assert gone == {"https://scaleart-shop.de/en-de/products/a"}


def test_gone_urls_without_a_cache_is_empty():
    assert audit.gone_urls(None, SWAPS) == frozenset()


LRP_RECORD = """id = "part/lrp/920500"
brand = "brand/lrp"
number = "920500"
name = "End plate"
links = [
  { site = "LRP", url = "https://www.lrp.cc/de/produkt/920500/" },
]
"""
LRP_DE = "https://www.lrp.cc/de/produkt/920500/"
LRP_EN = "https://www.lrp.cc/en/product/920500/"
LRP_SWAPS = {"www.lrp.cc": ("https://www.lrp.cc/de/produkt/", "https://www.lrp.cc/en/product/")}


def _english(status, page_text=None, tmp=None):
    path = None
    if page_text is not None:
        path = os.path.join(tmp, "en.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page_text)
    return {LRP_EN: (status, path)}


def test_failed_english_page_is_not_listed():
    unavailable = audit.english_unavailable(_english("failed"))
    assert not audit.has_foreign_link(LRP_RECORD, LRP_SWAPS, frozenset(), unavailable)


def test_english_page_with_php_error_is_not_listed():
    with tempfile.TemporaryDirectory() as tmp:
        eng = _english("done", "<b>Fatal error</b>: Call to a member function on null", tmp)
        assert not audit.has_foreign_link(LRP_RECORD, LRP_SWAPS, frozenset(), audit.english_unavailable(eng))


def test_english_page_naming_another_item_is_not_listed():
    with tempfile.TemporaryDirectory() as tmp:
        eng = _english("done", "<h1>Other end plate</h1> article 920821", tmp)
        assert not audit.has_foreign_link(LRP_RECORD, LRP_SWAPS, frozenset(), audit.english_unavailable(eng))


def test_english_page_naming_the_item_is_still_listed():
    with tempfile.TemporaryDirectory() as tmp:
        eng = _english("done", "<h1>End plate</h1> article 920500", tmp)
        assert audit.has_foreign_link(LRP_RECORD, LRP_SWAPS, frozenset(), audit.english_unavailable(eng))


def test_pending_english_page_is_still_listed():
    assert audit.has_foreign_link(LRP_RECORD, LRP_SWAPS, frozenset(), audit.english_unavailable({}))


def test_maker_link_number_counts_for_a_record_without_one():
    doc = 'id = "doc/lrp/n45-quickstart"\nurl = "https://www.lrp.cc/fileadmin/x.pdf"\nlinks = ["https://www.lrp.cc/de/produkt/920821/"]\n'
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "en.html")
        open(path, "w", encoding="utf-8").write("<h1>N45</h1> article 920821")
        eng = {"https://www.lrp.cc/en/product/920821/": ("done", path)}
        assert audit.has_foreign_link(doc, LRP_SWAPS, frozenset(), audit.english_unavailable(eng))
        open(path, "w", encoding="utf-8").write("<h1>N45</h1> article 920500")
        assert not audit.has_foreign_link(doc, LRP_SWAPS, frozenset(), audit.english_unavailable(eng))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
