"""release-suffix-twin: releases whose numbers differ by a suffix and that name one product (one barcode or one maker page).

Inline fixtures only. Run: python3 -I -m pytest tools/test_audit_suffix_twins.py -q
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit  # noqa: E402


def rel(rid, number, brand="brand/kyosho", **extra):
    return dict(id=rid, number=number, brand=brand, **extra)


def test_number_relation_suffix_either_way_only():
    assert audit.number_relation("34902", "34902D")
    assert audit.number_relation("34902D", "34902")
    assert audit.number_relation("10428", "10428-2")
    assert not audit.number_relation("34902", "34902")
    assert not audit.number_relation("34902", "34903D")
    assert not audit.number_relation("1234", "1234D")


def test_same_barcode_is_one_product():
    a = rel("release/kyosho/34902", "34902", gtin="4548565475131")
    b = rel("release/kyosho/34902d", "34902D", gtin="4548565475131")
    assert audit.suffix_twin_pairs([a, b]) == [(a, b)]


def test_different_barcodes_are_distinct_even_on_one_page():
    a = rel("release/kyosho/34118t1s", "34118T1S", gtin="4548565523504", released_source="https://rc.kyosho.com/en/newitem/2026-8/kit.html")
    b = rel("release/kyosho/34118t2s", "34118T2S", gtin="4548565523511", released_source="https://rc.kyosho.com/en/newitem/2026-8/kit.html")
    assert audit.suffix_twin_pairs([a, b]) == []


def test_same_page_without_barcodes_is_one_product():
    a = rel("release/team-associated/30128", "30128", released_source="https://www.associatedelectrics.com/x/")
    b = rel("release/team-associated/30128rc", "30128RC", released_source="https://www.associatedelectrics.com/x")
    assert audit.suffix_twin_pairs([a, b]) == [(a, b)]


def test_reviewed_pair_is_not_flagged():
    a = rel("release/xray/350021", "350021", brand="brand/xray", gtin="1")
    b = rel("release/xray/350021-c", "350021-C", brand="brand/xray", gtin="1")
    reviewed = {frozenset((a["id"], b["id"]))}
    assert audit.suffix_twin_pairs([a, b], reviewed) == []
    assert audit.suffix_twin_pairs([a, b]) == [(a, b)]


def test_other_brand_or_unrelated_number_is_not_paired():
    a = rel("release/kyosho/34902", "34902", gtin="9")
    b = rel("release/traxxas/34902d", "34902D", gtin="9", brand="brand/traxxas")
    c = rel("release/kyosho/34903d", "34903D", gtin="9")
    assert audit.suffix_twin_pairs([a, b, c]) == []


def test_records_without_number_or_brand_are_skipped():
    a = {"id": "release/kyosho/x", "gtin": "9"}
    b = rel("release/kyosho/34902d", "34902D", gtin="9")
    assert audit.suffix_twin_pairs([a, b]) == []
