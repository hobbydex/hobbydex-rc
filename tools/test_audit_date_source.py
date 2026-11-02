"""date_without_source: a year or released date needs released_source.

Run: python3 -I -m pytest tools/test_audit_date_source.py -q
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit  # noqa: E402


def rel(**kw):
    return {"id": "release/x/1", "brand": "brand/x", "name": "1", "status": "released", **kw}


def test_year_without_source_is_flagged():
    assert audit.date_without_source(rel(year=2025))


def test_released_without_source_is_flagged():
    assert audit.date_without_source(rel(released="2025-11"))


def test_year_and_released_with_source_pass():
    assert not audit.date_without_source(rel(year=2025, released="2025-11", released_source="doc/x/1-product-page"))


def test_undated_release_is_not_flagged():
    assert not audit.date_without_source(rel())


def test_seen_by_and_announced_are_not_dates_of_release():
    assert not audit.date_without_source(rel(seen_by="2024", seen_by_source="doc/x/1-manual"))
    assert not audit.date_without_source(rel(announced="2025-03", announced_source="https://x.example/news"))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
