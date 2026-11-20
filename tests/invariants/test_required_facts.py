"""Required facts (data/required-facts.toml, docs/schema.md "Required facts"): per part category and fact, the parts
that lack the fact and mark it neither as not stated by their source (`unstated`) nor as not yet checked on their page
(`unchecked`). One blocking ratchet per category and fact,
named fact-<category>-<fact>: a change may lower a count, never raise it."""
import functools, json

import pytest

import required_facts as rf
import snapshot

REGISTRY = rf.load(snapshot.RC)
PAIRS = [(c, f.fact) for c, cat in REGISTRY.items() for f in cat.facts]


@functools.cache
def _status(db):
    """({(category, fact): [(part id, problem)]} of the parts that lack a fact, the parts with an `unstated` table that
    is wrong, the parts with a stale marker), from one pass over the parts of the registry's categories."""
    specs = {i: json.loads(d) for i, d in db.execute("SELECT id, data FROM records WHERE kind = 'spec'")}
    cats = sorted(REGISTRY)
    out = {pair: [] for pair in PAIRS}
    bad, stale = [], []
    q = f"""SELECT id, data FROM records WHERE kind = 'part' AND (json_extract(data, '$.category') IN ({','.join('?' * len(cats))})
            OR json_type(data, '$.unstated') IS NOT NULL OR json_type(data, '$.unchecked') IS NOT NULL)"""
    for pid, d in db.execute(q, cats):
        p = json.loads(d)
        bad += [(pid, m) for m in rf.marker_problems(p, REGISTRY, specs)]
        stale += [(pid, f"marked {fid}, but the fact is set") for fid in rf.stale_markers(p, REGISTRY, specs)]
        cat = REGISTRY.get(p.get("category"))
        for fid in rf.missing(p, REGISTRY, specs):
            out[(p["category"], fid)].append((pid, f"no {cat.fact(fid).label.lower()}: {p.get('name', '')}"))
    return out, bad, stale


@pytest.mark.parametrize("category,fact", PAIRS, ids=[f"{c}-{f}" for c, f in PAIRS])
def test_required_fact(ratchet, db, category, fact):
    """A part of a category in data/required-facts.toml carries each of its required facts, or marks the fact
    `unstated = { <fact> = "<page or doc id>" }` when the page its importer read does not state it, or
    `unchecked = { <fact> = "<page>" }` when nobody has looked at that page for it yet (docs/schema.md "Required
    facts"). Blocking: fill the fact from the maker's page, or add the marker with that page."""
    ratchet(f"fact-{category}-{fact}", _status(db)[0][(category, fact)])


def test_required_fact_unstated_valid(hard, db):
    """A part's `unstated` and `unchecked` tables name required facts of its category (data/required-facts.toml), each
    with the https page or doc id it cites, and no fact is in both."""
    hard(_status(db)[1], name="required-fact-unstated-valid")


def test_required_fact_unstated_stale(ratchet, db):
    """A part does not mark a fact it has as unstated or unchecked: the writer that filled the fact drops the marker
    (tools/required_facts.py drop_stale). Reported, not blocking."""
    ratchet("required-fact-unstated-stale", _status(db)[2], blocking=False)
