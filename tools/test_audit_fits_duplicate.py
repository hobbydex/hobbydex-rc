"""audit.duplicate_fits: a part with two fits rows that name one claim (the same kit, releases and car) is flagged;
rows of different releases or cars are different claims. Run: python3 -I -m pytest tools/test_audit_fits_duplicate.py -q
(or python3 -I tools/test_audit_fits_duplicate.py)."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit  # noqa: E402

KIT = "kit/maverick/phantom-xb"


def part(pid, *fits):
    return {"id": pid, "brand": "brand/maverick", "fits": list(fits)}


def test_same_kit_twice_is_flagged():
    p = part("part/maverick/150625",
             {"kit": KIT, "type": "replaces", "source": "doc/maverick/part-pages"},
             {"kit": KIT, "type": "replaces", "source": "doc/maverick/150075-kit-page"})
    hits = audit.duplicate_fits([p])
    assert [x[0]["id"] for x in hits] == ["part/maverick/150625"]
    assert hits[0][1] == [(KIT, None, None)]


def test_different_releases_are_not_duplicates():
    p = part("part/maverick/1", {"kit": KIT, "releases": ["release/maverick/1"], "type": "direct", "source": "a"},
             {"kit": KIT, "releases": ["release/maverick/2"], "type": "direct", "source": "b"})
    assert audit.duplicate_fits([p]) == []


def test_whole_kit_and_a_narrowed_row_are_different_claims():
    p = part("part/maverick/2", {"kit": KIT, "type": "direct", "source": "a"},
             {"kit": KIT, "releases": ["release/maverick/1"], "type": "direct", "source": "b"})
    assert audit.duplicate_fits([p]) == []


def test_different_car_is_a_different_claim():
    p = part("part/maverick/3", {"kit": KIT, "car": "Phantom XB", "type": "direct", "source": "a"},
             {"kit": KIT, "car": "Phantom MT", "type": "direct", "source": "b"})
    assert audit.duplicate_fits([p]) == []


def test_replaces_rows_naming_different_stock_parts_are_not_duplicates():
    p = part("part/maverick/5",
             {"kit": KIT, "type": "replaces", "replaces": "part/maverick/10", "source": "a"},
             {"kit": KIT, "type": "replaces", "replaces": "part/maverick/11", "source": "a"})
    assert audit.duplicate_fits([p]) == []


def test_replaces_rows_naming_one_stock_part_are_duplicates():
    p = part("part/maverick/6",
             {"kit": KIT, "type": "replaces", "replaces": "part/maverick/10", "source": "a"},
             {"kit": KIT, "type": "replaces", "replaces": "part/maverick/10", "source": "b"})
    assert len(audit.duplicate_fits([p])) == 1


def test_direct_beside_replaces_is_flagged():
    p = part("part/maverick/7", {"kit": KIT, "type": "direct", "source": "a"},
             {"kit": KIT, "type": "replaces", "replaces": "part/maverick/10", "source": "a"})
    assert len(audit.duplicate_fits([p])) == 1


def test_a_part_without_fits_is_not_flagged():
    assert audit.duplicate_fits([{"id": "part/maverick/4", "brand": "brand/maverick"}]) == []


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                failed += 1; print("FAIL", name, repr(e))
    sys.exit(1 if failed else 0)
