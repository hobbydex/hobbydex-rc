"""The required facts of a part category (data/required-facts.toml): which a part has, which it lacks, which its source
does not state. Read by the invariants (tests/invariants/test_required_facts.py) and imported by hobbydex-tools (the
daily metrics, the importers and the descriptor engine), so the rules live in one place.

    import required_facts as rf
    reg = rf.load()                          # {category: Category}
    rf.missing(part, reg, specs)             # fact ids the part lacks and marks neither unstated nor unchecked
    rf.mark_unstated(part, source, reg, specs)   # set `unstated` for every fact the part lacks: the page that was read
                                             # (an https URL or a doc id) states none of them
    rf.mark_unchecked(part, source, reg, specs)  # set `unchecked`: the part's page, not yet looked at for the facts
    rf.confirm_unstated(part, facts)         # a check of the cited page found no value: unchecked becomes unstated
    rf.drop_stale(part, reg, specs)          # a writer that fills a fact drops its marker (either kind)

`specs` maps a spec id to its record (the specs a part is `equivalent_to` are read for its facts); pass {} when there
are none at hand, and a fact that only a spec gives is then counted as missing.
"""
import os, re, tomllib
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join("data", "required-facts.toml")
FACT_ID = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass
class Fact:
    fact: str
    label: str
    any: list
    when: dict = field(default_factory=dict)


@dataclass
class Category:
    category: str
    facts: list
    exclude_name: object = None   # a compiled regex, or None
    when: dict = field(default_factory=dict)
    marks: list = field(default_factory=list)   # fields only this category's parts carry (the importer contract)

    def fact(self, fid):
        return next((f for f in self.facts if f.fact == fid), None)


def parse(doc):
    """The registry from its parsed TOML; the first malformed entry raises ValueError with what is wrong (validate.py
    prints it; the Rust validator of hobbydex-tools has the same messages)."""
    reg = {}
    for cat, t in doc.items():
        if not isinstance(t, dict) or not isinstance(t.get("facts"), list) or not t["facts"]:
            raise ValueError(f"[{cat}] needs a non-empty facts list")
        ex = t.get("exclude_name")
        try:
            ex = re.compile(ex) if ex is not None else None
        except (re.error, TypeError):
            raise ValueError(f"[{cat}] exclude_name is not a valid regex") from None
        when = _when(cat, "", t.get("when"))
        facts = []
        for f in t["facts"]:
            if not isinstance(f, dict):
                raise ValueError(f"[{cat}] a fact is not a table")
            fid = f.get("fact")
            if not isinstance(fid, str) or not FACT_ID.match(fid):
                raise ValueError(f"[{cat}] a fact needs an id of lower-case letters, digits and hyphens")
            if not isinstance(f.get("any"), list) or not f["any"] or not all(isinstance(a, str) and a for a in f["any"]):
                raise ValueError(f"[{cat}] {fid}: any must be a non-empty list of field names or spec/<kind>/")
            if any(x.fact == fid for x in facts):
                raise ValueError(f"[{cat}] {fid} is listed twice")
            label = f.get("label") if isinstance(f.get("label"), str) and f.get("label") else fid
            facts.append(Fact(fid, label, list(f["any"]), _when(cat, fid, f.get("when"))))
        marks = t.get("marks", [])
        if not isinstance(marks, list) or not all(isinstance(m, str) and m for m in marks):
            raise ValueError(f"[{cat}] marks must be a list of field names")
        reg[cat] = Category(cat, facts, ex, when, list(marks))
    return reg


def _when(cat, fid, w):
    if w is None:
        return {}
    if not isinstance(w, dict) or not w or not all(isinstance(v, list) and v for v in w.values()):
        raise ValueError(f"[{cat}]{' ' + fid if fid else ''}: when maps a field to a non-empty list of values")
    return w


def load(root=ROOT):
    """The registry of the checkout at root ({} when the file is not there: an older commit)."""
    path = os.path.join(root, REGISTRY)
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        try:
            doc = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"parse error: {e}") from None
    return parse(doc)


def stated(v):
    """A value that states something: not missing, not an empty string, list or table (false and 0 are stated)."""
    return v is not None and v != "" and v != [] and v != {}


def linked_specs(part):
    """The spec ids the part names in `equivalent_to` and `includes`."""
    out = []
    for key in ("equivalent_to", "includes"):
        for r in part.get(key) or []:
            if isinstance(r, dict) and isinstance(r.get("spec"), str):
                out.append(r["spec"])
    return out


def value(part, name, specs):
    """A field of the part, else of the first spec it is `equivalent_to` that has it."""
    if stated(part.get(name)):
        return part[name]
    for r in part.get("equivalent_to") or []:
        s = specs.get(r.get("spec")) if isinstance(r, dict) else None
        if s and stated(s.get(name)):
            return s[name]
    return None


def has(part, fact, specs):
    for a in fact.any:
        if a.startswith("spec/"):
            if any(s.startswith(a) for s in linked_specs(part)):
                return True
        elif stated(value(part, a, specs)):
            return True
    return False


def _holds(part, when, specs):
    return all(value(part, k, specs) in vs for k, vs in when.items())


def in_scope(part, cat):
    """The part is the item of its category itself (not an accessory its name names) and meets the category's `when`."""
    name = part.get("name") if isinstance(part.get("name"), str) else ""
    if cat.exclude_name and cat.exclude_name.search(name):
        return False
    return _holds(part, cat.when, {}) if cat.when else True


def applicable(part, reg, specs):
    """The facts that apply to the part ([] when its category has none, or the part is out of scope)."""
    cat = reg.get(part.get("category"))
    if not cat or not in_scope(part, cat):
        return []
    return [f for f in cat.facts if not f.when or _holds(part, f.when, specs)]


MARKERS = ("unstated", "unchecked")


def unstated(part):
    u = part.get("unstated")
    return u if isinstance(u, dict) else {}


def unchecked(part):
    """The `unchecked` table: facts a part lacks whose page nobody has looked at for them yet (the refresh net writes
    it); the facts-on-pages sweep reads the page and the marker becomes `unstated` when the page states no value."""
    u = part.get("unchecked")
    return u if isinstance(u, dict) else {}


def status(part, reg, specs):
    """{fact id: "have" | "unstated" | "unchecked" | "missing"} for every fact that applies to the part."""
    marks, open_ = unstated(part), unchecked(part)
    out = {}
    for f in applicable(part, reg, specs):
        out[f.fact] = ("have" if has(part, f, specs) else "unstated" if f.fact in marks
                       else "unchecked" if f.fact in open_ else "missing")
    return out


def missing(part, reg, specs):
    return [k for k, v in status(part, reg, specs).items() if v == "missing"]


def valid_source(s):
    return isinstance(s, str) and (s.startswith("https://") or s.startswith("doc/"))


def marker_problems(part, reg, specs):
    """What is wrong with a part's `unstated` or `unchecked` table: not a table, a fact its category does not list, a
    source that is no https URL or doc id, or a fact in both tables. (A marker beside a fact that is set is stale, not
    wrong: stale_markers.)"""
    cat = reg.get(part.get("category"))
    out = []
    for key in MARKERS:
        u = part.get(key)
        if u is None:
            continue
        if not isinstance(u, dict) or not u:
            out.append(f"{key} is not a table of fact = source")
            continue
        for fid, src in sorted(u.items()):
            if not (cat and cat.fact(fid)):
                out.append(f"{key} {fid}: not a required fact of category {part.get('category')}")
            elif not valid_source(src):
                out.append(f"{key} {fid}: source {src!r} is not an https URL or a doc id")
    out += [f"unchecked {fid}: also marked unstated" for fid in sorted(set(unstated(part)) & set(unchecked(part)))]
    return out


def stale_markers(part, reg, specs):
    """The facts the part marks (unstated or unchecked) and has after all (a later source filled them): drop_stale
    removes them."""
    cat = reg.get(part.get("category"))
    if not cat:
        return []
    marked = set(unstated(part)) | set(unchecked(part))
    return sorted(fid for fid in marked if cat.fact(fid) and has(part, cat.fact(fid), specs))


def _drop(part, key, facts):
    table = part.get(key) if isinstance(part.get(key), dict) else {}
    left = {k: v for k, v in table.items() if k not in facts}
    if left:
        part[key] = left
    else:
        part.pop(key, None)


def drop_stale(part, reg, specs):
    """Remove the markers (both kinds) of facts the part has, in place (a table goes when it is empty); returns the
    facts."""
    gone = stale_markers(part, reg, specs)
    if gone:
        for key in MARKERS:
            if key in part:
                _drop(part, key, gone)
    return gone


def mark_unstated(part, source, reg, specs, facts=None):
    """Mark the facts the part lacks as not stated by `source` (an https URL or a doc id), in place; only the given
    facts when `facts` is a list. A marker already there is kept; an `unchecked` marker of the fact becomes this one
    (the page was read now). Returns the facts marked now."""
    if not valid_source(source):
        raise ValueError(f"unstated source {source!r} is not an https URL or a doc id")
    want = [k for k, v in status(part, reg, specs).items() if v in ("missing", "unchecked")]
    if facts is not None:
        want = [f for f in want if f in facts]
    if want:
        part["unstated"] = {**unstated(part), **{f: source for f in want}}
        if "unchecked" in part:
            _drop(part, "unchecked", want)
    return want


def mark_unchecked(part, source, reg, specs, facts=None):
    """Mark the facts the part lacks as not yet looked for on `source` (the part's own page: an https URL or a doc id),
    in place; only the given facts when `facts` is a list. A marker of either kind already there is kept. The ratchets
    count the fact as marked, the facts-on-pages sweep still looks for it. Returns the facts marked now."""
    if not valid_source(source):
        raise ValueError(f"unchecked source {source!r} is not an https URL or a doc id")
    want = missing(part, reg, specs)
    if facts is not None:
        want = [f for f in want if f in facts]
    if want:
        part["unchecked"] = {**unchecked(part), **{f: source for f in want}}
    return want


def confirm_unstated(part, facts, source=None):
    """A check of the cited page found no value for `facts`: their `unchecked` markers become `unstated` with the same
    page, in place (only those citing `source` when it is given). Returns the facts moved."""
    open_ = unchecked(part)
    moved = [f for f in facts if f in open_ and (source is None or open_[f] == source)]
    if moved:
        part["unstated"] = {**unstated(part), **{f: open_[f] for f in moved}}
        _drop(part, "unchecked", moved)
    return moved
