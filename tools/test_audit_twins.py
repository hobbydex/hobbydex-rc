"""twin_class: a pair is a copy only when one record cites the other brand's site and not its own.

Blitz is Team Titan's brand and both brands name the same website, so a pair of the same part under
both is shared, not a copy. Run: python3 -I -m pytest tools/test_audit_twins.py -q
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit  # noqa: E402

SITE = "https://www.team-titan.com.tw/"
BRANDS = {
    "brand/blitz": {"website": SITE, "owner": "company/team-titan"},
    "brand/team-titan": {"website": SITE},
    "brand/cross-rc": {"website": "https://www.cross-rc.com/"},
    "brand/hobao": {"website": "https://www.hobao-racing.com/"},
}
COMPANIES = {"company/team-titan": {"id": "company/team-titan", "brand": "brand/team-titan"}}
LINK = [{"site": "Team Titan", "url": SITE + "products_class101.php?cid=28", "kind": "maker"}]


def part(pid, brand, links=None, documents=None):
    return {"id": pid, "brand": brand, "number": "60419-1", "name": "TS050 Body Stiffener 0.5mm",
            "links": links or [], "documents": documents or []}


def test_same_site_pair_is_shared_not_copy():
    a = part("part/blitz/60419-1", "brand/blitz", links=LINK)
    b = part("part/team-titan/60419-1", "brand/team-titan", links=LINK)
    assert audit.twin_class(a, b, BRANDS, COMPANIES, {}) == "shared"


def test_record_citing_only_the_other_brand_is_a_copy():
    a = part("part/cross-rc/1", "brand/cross-rc", links=[{"url": "https://www.hobao-racing.com/p/1"}])
    b = part("part/hobao/1", "brand/hobao")
    assert audit.twin_class(a, b, BRANDS, COMPANIES, {}) == "copy"


def test_unrelated_brands_without_sources_are_unclear():
    a = part("part/cross-rc/2", "brand/cross-rc")
    b = part("part/hobao/2", "brand/hobao")
    assert audit.twin_class(a, b, BRANDS, COMPANIES, {}) == "unclear"


def test_number_only_names_never_pair():
    a = {"id": "part/cross-rc/11202", "brand": "brand/cross-rc", "number": "11202", "name": "11202"}
    b = {"id": "part/hobao/11202", "brand": "brand/hobao", "number": "11202", "name": "11202"}
    assert audit.twin_pairs([a, b]) == []


def test_same_number_and_real_name_pair():
    a = part("part/blitz/60419-1", "brand/blitz")
    b = part("part/team-titan/60419-1", "brand/team-titan")
    assert audit.twin_pairs([a, b]) == [(a, b)]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
