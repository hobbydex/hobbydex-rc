"""Cases for audit.horizon_no_page: a Horizon part named only by parts documents, whose item page is 404, has no maker page.

    python3 -I tools/test_audit_horizon_no_page.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

DOCS = {"doc/a": {"kind": "exploded_view"}, "doc/b": {"kind": "part_list"}, "doc/c": {"kind": "product_page"}, "doc/d": {"kind": "manual"}}
GONE = {"AR1", "AR2", "AR3"}


def part(number="AR1", documents=("doc/a",), source="doc/a"):
    return {"number": number, "documents": list(documents), "seen_by_source": source}


def test_exploded_view_and_parts_list_with_404_item_page():
    assert audit.horizon_no_page(part(documents=("doc/a", "doc/b"), source="doc/b"), DOCS, GONE)
    assert audit.horizon_no_page(part(documents=("doc/d",), source="doc/d"), DOCS, GONE)


def test_item_page_not_known_gone_stays_flagged():
    assert not audit.horizon_no_page(part(number="AR9"), DOCS, GONE)


def test_a_product_page_document_stays_flagged():
    assert not audit.horizon_no_page(part(documents=("doc/a", "doc/c")), DOCS, GONE)
    assert not audit.horizon_no_page(part(source="doc/c"), DOCS, GONE)


def test_no_document_stays_flagged():
    assert not audit.horizon_no_page(part(documents=()), DOCS, GONE)


def test_archived_product_image_source_counts_but_archived_page_does_not():
    img = "https://web.archive.org/web/2015/http://www.losi.com/ProdInfo/LOS/100/LOS210002-100.jpg"
    assert audit.horizon_no_page(part(source=img), DOCS, GONE)
    assert not audit.horizon_no_page(part(source="https://web.archive.org/web/2015/http://www.losi.com/product.html"), DOCS, GONE)


def test_gone_items_reads_the_404_markers():
    with tempfile.TemporaryDirectory() as t:
        d = os.path.join(t, "cache", "notes", "horizon-items")
        os.makedirs(d)
        for n in ("AR1-item.html.http404.txt", "AR2-product.html", "AR3-item.html"):
            open(os.path.join(d, n), "w").close()
        assert audit.horizon_gone_items(t) == {"AR1"}
        assert audit.horizon_gone_items(os.path.join(t, "none")) == set()
