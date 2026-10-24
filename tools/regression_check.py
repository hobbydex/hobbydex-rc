#!/usr/bin/env python3
"""Compare the data/ of a change with its base and report what it removes or changes.

tools/check_ids.py guards ids; this check guards values. Every record (a TOML file
under data/) is compared at the base revision and at the head revision, per field
and, inside a list of tables, per row. The values added, removed and changed are
counted by entity type and by field. A removed or changed value is a regression
when a source stated it:

- a record removed, unless data/retired.toml lists it with replaced_by, or a record
  of the head names it in former_ids (a rename);
- a field removed or changed while it is sourced: links, fits, includes, material,
  color, former_names, name_de, name_fr, name_ja, documents, contains, notes; category with
  category_source = "curated"; pack_qty with a stated pack_qty_basis (name, page,
  maker, owner, includes, photos); any field with a <field>_source beside it or a
  key in `sources`; equivalent_to rows that carry a source;
- a link removed or changed, unless its page is known gone (a document of the head
  with gone set and that page). Marking a link gone (`gone = "<date>"` added, the
  link kept) is not a regression.

Not regressions: values added; values that only differ in form (TOML layout,
whitespace, letter form of a URL: https, no www, no trailing slash); a convention
value (pack_qty without a stated basis, material "unknown") replaced by any value.

    python3 -I tools/regression_check.py                      # origin/main against HEAD
    python3 -I tools/regression_check.py --base origin/main --head HEAD \\
        --body pr-body.md --report report.txt --json result.json --markdown summary.md

--body: a PR description. A line "Regressions: expected" with the reason on the
same line or on the next non-empty line lets the change through; the reason is
printed. --report writes every removed and changed value, flagged or not.
--json writes the result for tools that act on it (tools/local_loop.py).

Exit: 0 no regressions (or expected), 1 regressions, 2 the check could not run.
Run from the repository root.
"""
import argparse, collections, datetime, json, os, re, subprocess, sys, tomllib, unicodedata, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_ids import id_of

RETIRED = "data/retired.toml"
SOURCED_FIELDS = {"links", "fits", "includes", "material", "color", "former_names", "name_de", "name_fr", "name_ja",
                 "documents", "contains", "notes"}   # list rows and notes: each is some tool's provenance
STATED_PACK_BASIS = {"maker", "page", "name", "owner", "includes", "photos"}   # pack_qty_basis; "photo" is the weakest, not stated
CONVENTION = {"material": {"unknown"}}   # placeholder values, never a stated fact
# keys that name a row, in the order they are tried; rows are paired by them when their content changed
IDENT_KEYS = ("url", "kit", "spec", "part", "release", "doc", "brand", "item", "site", "name", "text", "role", "relation")
MISSING = object()
FIELD_ROWS_LOG = 60    # field rows printed to stdout; the report file has all


def git(*args, check=True):
    """stdout of a git command; a failure raises, unless check is False (grep finds nothing: exit 1)."""
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def blobs(rev, paths):
    """The bytes of rev:path for each path (None when the path is absent), in one git cat-file call."""
    if not paths:
        return {}
    inp = "\n".join(f"{rev}:{p}" for p in paths) + "\n"
    r = subprocess.run(["git", "cat-file", "--batch"], input=inp.encode("utf-8"), capture_output=True, check=True)
    out, pos, res = r.stdout, 0, {}
    for p in paths:
        nl = out.index(b"\n", pos)
        head = out[pos:nl].decode("utf-8", "replace").split()
        pos = nl + 1
        if len(head) < 3:   # "<spec> missing"
            res[p] = None
            continue
        size = int(head[2])
        res[p] = out[pos:pos + size]
        pos += size + 1
    return res


def parse(data, path):
    try:
        return tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise RuntimeError(f"{path}: does not parse: {e}")


def normalize_url(u):
    p = urllib.parse.urlsplit(u.strip())
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return urllib.parse.urlunsplit(("https", host, p.path.rstrip("/"), p.query, ""))


def normalize(v):
    if isinstance(v, str):
        if v.startswith(("http://", "https://")):
            return normalize_url(v)
        return re.sub(r"\s+", " ", unicodedata.normalize("NFC", v)).strip()
    if isinstance(v, bool):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: normalize(x) for k, x in v.items()}
    if isinstance(v, list):
        return [normalize(x) for x in v]
    return v


def canon(v):
    if v is MISSING:
        return "<absent>"
    return json.dumps(normalize(v), sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def show(v):
    if v is MISSING:
        return "-"
    s = canon(v)
    return s if len(s) <= 160 else s[:157] + "..."


def ident(row):
    if isinstance(row, dict):
        for key in IDENT_KEYS:
            if key in row:
                return (key, canon(normalize_url(row[key]) if key == "url" else row[key]))
        return ("canon", canon(row))
    return ("value", canon(row))


def values(v):
    return len(v) if isinstance(v, list) else 1


def field_sourced(rec, k, val=MISSING):
    if val is not MISSING and isinstance(val, str) and val in CONVENTION.get(k, ()):
        return False
    if k == "category":
        return rec.get("category_source") == "curated"
    if k == "pack_qty":
        return rec.get("pack_qty_basis") in STATED_PACK_BASIS
    if k in SOURCED_FIELDS or f"{k}_source" in rec:
        return True
    return k in (rec.get("sources") or {})


def element_sourced(rec, k, row):
    if k == "equivalent_to":
        return isinstance(row, dict) and "source" in row
    return field_sourced(rec, k)


class Check:
    def __init__(self, base, head):
        self.base, self.head = base, head
        self.events = []                       # every removed or changed value and every removed record
        self.counts = collections.defaultdict(collections.Counter)   # (kind, field) -> added/removed/changed/regressions
        self.recs = collections.defaultdict(collections.Counter)     # kind -> records added/removed/changed
        self._former = self._gone = self._replaced = self._docs = None

    def count(self, kind, field, what, n=1):
        self.counts[(kind, field)][what] += n

    def event(self, kind, rid, field, change, old, new, regression, reason):
        self.events.append(dict(kind=kind, id=rid, field=field, change=change, old=show(old), new=show(new),
                                regression=regression, reason=reason))
        if regression:
            self.count(kind, field, "regressions")

    # lookups in the head, made only when a record is removed or a link goes
    def retired_replaced(self):
        if self._replaced is None:
            blob = blobs(self.head, [RETIRED])[RETIRED]
            rows = parse(blob, RETIRED).get("retired", []) if blob else []
            self._replaced = {r["id"] for r in rows if r.get("replaced_by")}
        return self._replaced

    def former_map(self):
        if self._former is None:
            self._former = {}
            for p, b in blobs(self.head, self._grep("former_ids", "data")).items():
                for f in (parse(b, p).get("former_ids", []) if b else []):
                    self._former[f] = id_of(p)
        return self._former

    def doc_pages(self):
        """normalized page URL -> the doc ids whose page it is (documents of the head)."""
        if self._docs is None:
            self._docs = collections.defaultdict(set)
            for line in git("grep", "-e", "^page = ", self.head, "--", "data/documents", check=False).splitlines():
                path_part, _, value = line[len(self.head) + 1:].partition(":")
                m = re.match(r'page = "(.*)"\s*$', value)
                if m and path_part.endswith(".toml"):
                    self._docs[normalize_url(m.group(1))].add(id_of(path_part))
        return self._docs

    def gone_pages(self):
        if self._gone is None:
            self._gone = set()
            for p, b in blobs(self.head, self._grep("^gone = ", "data/documents", regex=True)).items():
                d = parse(b, p) if b else {}
                if "gone" in d:
                    self._gone |= {normalize_url(d[k]) for k in ("page", "url") if isinstance(d.get(k), str)}
        return self._gone

    def _grep(self, pattern, where, regex=False):
        args = ["grep", "-l"] + ([] if regex else ["-F"]) + ["-e", pattern, self.head, "--", where]
        out = git(*args, check=False)
        return [line[len(self.head) + 1:] for line in out.splitlines() if line.startswith(self.head + ":")]

    def run(self):
        changes = []
        toks = git("diff", "--no-renames", "--name-status", "-z", self.base, self.head, "--", "data").split("\0")
        for i in range(0, len(toks) - 1, 2):
            status, path = toks[i], toks[i + 1]
            rid = id_of(path) if path.endswith(".toml") else None
            if rid:
                changes.append((status[:1], path, rid))
        old = blobs(self.base, [p for s, p, _ in changes if s in "DMT"])
        new = blobs(self.head, [p for s, p, _ in changes if s in "AMT"])
        for status, path, rid in changes:
            kind = rid.split("/", 1)[0]
            o = parse(old[path], path) if status in "DMT" and old.get(path) is not None else None
            n = parse(new[path], path) if status in "AMT" and new.get(path) is not None else None
            if o is None and n is None:
                continue
            if o is None:
                self.recs[kind]["added"] += 1
                for k, v in n.items():
                    self.count(kind, k, "added", values(v))
            elif n is None:
                self.removed_record(kind, rid, o)
            elif canon(o) != canon(n):
                self.compare(kind, rid, o, n)
        return self

    def removed_record(self, kind, rid, o):
        self.recs[kind]["removed"] += 1
        for k, v in o.items():
            self.count(kind, k, "removed", values(v))
        if rid in self.retired_replaced():
            self.event(kind, rid, "(record)", "removed", MISSING, MISSING, False, "listed in retired.toml with replaced_by")
        elif rid in self.former_map():
            self.event(kind, rid, "(record)", "removed", MISSING, MISSING, False, f"renamed: former_ids of {self.former_map()[rid]}")
        else:
            self.event(kind, rid, "(record)", "removed", MISSING, MISSING, True, "record removed; not retired with replaced_by and no successor names it")

    def compare(self, kind, rid, o, n):
        changed = False
        for k in sorted(set(o) | set(n)):
            ov, nv = o.get(k, MISSING), n.get(k, MISSING)
            if ov is MISSING:
                self.count(kind, k, "added", values(nv))
                changed = True
                continue
            if nv is MISSING:
                self.count(kind, k, "removed", values(ov))
                self.drop(kind, rid, o, n, k, ov)
                changed = True
                continue
            if isinstance(ov, list) and isinstance(nv, list):
                if canon(ov) != canon(nv):
                    changed = True
                    self.list_diff(kind, rid, o, n, k, ov, nv)
            elif canon(ov) != canon(nv):
                changed = True
                self.count(kind, k, "changed")
                if k == "name" and name_key(ov, o.get("brand")) == name_key(nv, n.get("brand")):
                    self.event(kind, rid, k, "changed", ov, nv, False, "same name in canonical form (brand, pack count)")
                    continue
                reg = field_sourced(o, k, ov)
                self.event(kind, rid, k, "changed", ov, nv, reg, "stated value changed" if reg else "not stated")
        if changed:
            self.recs[kind]["changed"] += 1

    def drop(self, kind, rid, o, n, k, ov):
        if isinstance(ov, list):
            for row in ov:
                self.removed_row(kind, rid, o, n, k, row)
            return
        why = canonical_removal(o, n, k, ov)
        if why:
            self.event(kind, rid, k, "removed", ov, MISSING, False, why)
            return
        reg = field_sourced(o, k, ov)
        self.event(kind, rid, k, "removed", ov, MISSING, reg, "stated field removed" if reg else "not stated")

    def removed_row(self, kind, rid, o, n, k, row):
        if not element_sourced(o, k, row):
            self.event(kind, rid, k, "removed", row, MISSING, False, "not stated")
            return
        why = canonical_removal(o, n, k, row)
        if why:
            self.event(kind, rid, k, "removed", row, MISSING, False, why)
            return
        if k == "links":
            url = normalize_url(row.get("url", ""))
            if url in self.gone_pages():
                self.event(kind, rid, k, "removed", row, MISSING, False, "link page known gone")
                return
            if set(n.get("documents", [])) & self.doc_pages().get(url, set()):
                self.event(kind, rid, k, "removed", row, MISSING, False, "page kept as a document of the record")
                return
        self.event(kind, rid, k, "removed", row, MISSING, True, "stated link removed" if k == "links" else f"stated {k} row removed")

    def list_diff(self, kind, rid, o, n, k, ov, nv):
        left = collections.Counter(canon(x) for x in ov)
        right = collections.Counter(canon(x) for x in nv)
        removed, added = [], []
        for x in ov:
            c = canon(x)
            if right[c] > 0:
                right[c] -= 1
            else:
                removed.append(x)
        for x in nv:
            c = canon(x)
            if left[c] > 0:
                left[c] -= 1
            else:
                added.append(x)
        used = [False] * len(added)
        pure = []
        for r in removed:
            hit = next((j for j, a in enumerate(added) if not used[j] and ident(a) == ident(r)), None)
            if hit is None:
                pure.append(r)
                continue
            used[hit] = True
            self.count(kind, k, "changed")
            a = added[hit]
            if isinstance(r, dict) and isinstance(a, dict) and differs_only_in_provenance(r, a):
                self.event(kind, rid, k, "changed", r, a, False, "source or note only")
                continue
            if k == "links" and isinstance(r, dict) and isinstance(a, dict) and "gone" in a and \
                    all(canon(r[x]) == canon(a.get(x, MISSING)) for x in r if x != "gone"):
                self.event(kind, rid, k, "changed", r, a, False, "page marked gone (link kept)")
                continue
            if isinstance(r, dict) and isinstance(a, dict) and all(canon(r[x]) == canon(a.get(x, MISSING)) for x in r):
                self.event(kind, rid, k, "changed", r, a, False, "key added, nothing lost")
                continue
            reg = element_sourced(o, k, r)
            self.event(kind, rid, k, "changed", r, a, reg, "stated row changed" if reg else "not stated")
        for j, a in enumerate(added):
            if not used[j]:
                self.count(kind, k, "added")
        for r in pure:
            self.count(kind, k, "removed")
            self.removed_row(kind, rid, o, n, k, r)


PROVENANCE = {"source", "sources", "notes", "note"}


def differs_only_in_provenance(a, b):
    keys = set(a) | set(b)
    diff = {x for x in keys if canon(a.get(x, MISSING)) != canon(b.get(x, MISSING))}
    return bool(diff) and all(x in PROVENANCE or x.endswith("_source") for x in diff)


# a pack count or bag callout at the end of a name: "(10)", "(2pcs.)", "(BBS x10)", " x10", " 10pcs"
PACK_COUNT = r"(\s*\((?:[A-Za-z ]{0,12}x\s?)?\d+\s*(?:pcs?\.?|pieces)?\)|\s+x\s?\d+|\s+\d+\s*pcs\.?)\s*$"


def name_key(name, brand):
    """A name as the schema writes it: no brand in front, no trailing pack count or bag callout, no punctuation."""
    if not isinstance(name, str):
        return None
    s = re.sub(PACK_COUNT, "", name.strip()).strip()
    if isinstance(brand, str):
        slug = brand.split("/")[-1].replace("-", " ")
        if s.casefold().startswith(slug.casefold()):
            s = s[len(slug):]
    return re.sub(r"[^0-9a-z]", "", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().casefold())


def is_dealer(link):
    """A shop's page: kind = "dealer", or a site label that says so ("taylorrc.co.uk (dealer)")."""
    return link.get("kind") == "dealer" or "(dealer)" in str(link.get("site", ""))


LISTING = re.compile(r"\(\s*\d+\s*\)|\bx\s?\d+\b|\b\d+\s?pcs\b|\b\d{5,}\b", re.I)


def canonical_removal(o, n, k, row):
    """Why a removed value is not a loss: the schema moved it or wrote it another way. None when it is a loss."""
    c = canon(row)
    if k in ("seen_by", "seen_by_source") and any(f in n for f in ("released", "year", "announced")):
        return "seen_by dropped: a real date now stands"
    for k2, v2 in n.items():   # moved: the other field gained the value (it did not hold it before)
        if k2 == k:
            continue
        had = o.get(k2, MISSING)
        if (canon(v2) == c or (isinstance(v2, list) and any(canon(x) == c for x in v2))) and \
                not (canon(had) == c or (isinstance(had, list) and any(canon(x) == c for x in had))):
            return f"moved to {k2}"
    if k == "former_names" and isinstance(row, str):
        if LISTING.search(row):
            return "listing line, never a former name"
        if name_key(row, o.get("brand")) == name_key(n.get("name"), n.get("brand")):
            return "former name is the current name"
    if k == "links" and is_dealer(row) and any(isinstance(x, dict) and not is_dealer(x) for x in n.get("links", [])):
        return "dealer link beside a maker link (validate.py form)"
    return None


def kind_rows(ck):
    """One row per entity type: records and values by change, and the regressions."""
    rows = []
    for kind in sorted({k for k, _ in ck.counts} | set(ck.recs)):
        vals = collections.Counter()
        for (kk, f), c in ck.counts.items():
            if kk == kind and f != "(record)":
                vals.update(c)
        r = ck.recs[kind]
        rows.append(dict(kind=kind, rec_added=r["added"], rec_removed=r["removed"], rec_changed=r["changed"],
                         added=vals["added"], removed=vals["removed"], changed=vals["changed"],
                         regressions=sum(c["regressions"] for (kk, _), c in ck.counts.items() if kk == kind)))
    return rows


def kind_table(rows):
    out = [f"  {'entity':<10} {'records +':>10} {'-':>8} {'~':>8} | {'values +':>10} {'-':>9} {'~':>9} | {'regressions':>11}"]
    for r in rows:
        out.append(f"  {r['kind']:<10} {r['rec_added']:>10} {r['rec_removed']:>8} {r['rec_changed']:>8} |"
                   f" {r['added']:>10} {r['removed']:>9} {r['changed']:>9} | {r['regressions']:>11}")
    return out


def field_rows(ck):
    """Fields with any change, regressions first, then the most removed or changed."""
    rows = [(k, c) for k, c in ck.counts.items() if c["added"] or c["removed"] or c["changed"] or c["regressions"]]
    return sorted(rows, key=lambda kv: (-kv[1]["regressions"], -(kv[1]["removed"] + kv[1]["changed"]), kv[0]))


def verdict(ck, expected):
    regs = [e for e in ck.events if e["regression"]]
    if not regs:
        return "no regressions"
    if expected is not None:
        return f"{len(regs)} regressions, expected: {expected}"
    return f"{len(regs)} regressions"


def body_reason(path):
    """The reason of a 'Regressions: expected' line, "" when the line has none, None when there is no such line."""
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^\s*Regressions:\s*expected\b[\s:.\-]*(.*?)\s*$", line)
        if m:
            reason = m.group(1)
            if not reason:
                reason = next((x.strip() for x in lines[i + 1:] if x.strip()), "")
            return reason
    return None


def write_markdown(ck, path, base, head, verdict_text):
    cell = lambda x: str(x).replace("|", "\\|").replace("\n", " ")
    md = ["### Data regression check", "",
          f"`{base[:10]}` to `{head[:10]}`: **{cell(verdict_text)}**", "",
          "| entity | records added | removed | changed | values added | removed | changed | regressions |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in kind_rows(ck):
        md.append(f"| {r['kind']} | {r['rec_added']} | {r['rec_removed']} | {r['rec_changed']} | {r['added']} | "
                  f"{r['removed']} | {r['changed']} | {r['regressions']} |")
    regs = [e for e in ck.events if e["regression"]]
    if regs:
        md += ["", "| record | field | change | old | new | why |", "|---|---|---|---|---|---|"]
        for e in regs[:100]:
            md.append(f"| {cell(e['id'])} | {cell(e['field'])} | {e['change']} | {cell(e['old'])} | "
                      f"{cell(e['new'])} | {cell(e['reason'])} |")
        if len(regs) > 100:
            md.append(f"\n{len(regs) - 100} more in the job log.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Data regression check of a change to data/ (see the module docstring).")
    ap.add_argument("--base", default="origin/main", help="the revision the change is based on (its merge base is used)")
    ap.add_argument("--head", default="HEAD", help="the revision with the change")
    ap.add_argument("--body", help="file with the PR description (a 'Regressions: expected' line lets regressions through)")
    ap.add_argument("--report", help="write every removed and changed value to this file")
    ap.add_argument("--json", help="write the result as JSON to this file")
    ap.add_argument("--markdown", help="write a summary in Markdown (for the job summary)")
    args = ap.parse_args()
    try:
        head = git("rev-parse", "--verify", "-q", args.head + "^{commit}").strip()
        base = git("merge-base", args.base, head).strip()
        ck = Check(base, head).run()
    except RuntimeError as e:
        print(f"regression check could not run: {e}", file=sys.stderr)
        sys.exit(2)
    expected = None
    if args.body:
        reason = body_reason(args.body)
        if reason:
            expected = reason
        elif reason == "":
            print("'Regressions: expected' has no reason; the regressions still fail the check.")
    regs = [e for e in ck.events if e["regression"]]
    text = verdict(ck, expected)
    print(f"Data regression check: base {base[:10]}, head {head[:10]}")
    print("\n".join(kind_table(kind_rows(ck))))
    rows = field_rows(ck)
    if rows:
        print(f"\nFields with changes ({len(rows)}; the report file has all)")
        print(f"  {'entity/field':<30} {'added':>7} {'removed':>8} {'changed':>8} {'regressions':>12}")
        for (kind, f), c in rows[:FIELD_ROWS_LOG]:
            print(f"  {kind + '/' + f:<30} {c['added']:>7} {c['removed']:>8} {c['changed']:>8} {c['regressions']:>12}")
    if regs:
        print(f"\nRegressions ({len(regs)}):")
        for e in regs:
            print(f"  {e['id']} {e['field']} {e['change']}: {e['old']} -> {e['new']} ({e['reason']})")
    others = [e for e in ck.events if not e["regression"]]
    if others:
        print(f"\nRemoved or changed, not regressions: {len(others)} (the report file lists them)")
        for e in others[:25]:
            print(f"  {e['id']} {e['field']} {e['change']}: {e['old']} -> {e['new']} ({e['reason']})")
    print(f"\nResult: {text}")
    if regs and expected is None:
        print("To let these through, add a line 'Regressions: expected' with the reason to the PR description.")
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            for e in ck.events:
                f.write("\t".join(["REGRESSION" if e["regression"] else "ok", e["kind"], e["id"], e["field"],
                                   e["change"], e["old"], e["new"], e["reason"]]) + "\n")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(dict(base=base, head=head, regressions=regs, expected=expected,
                           counts={f"{k}/{f}": dict(c) for (k, f), c in ck.counts.items()}),
                      f, indent=1, ensure_ascii=True)
    if args.markdown:
        write_markdown(ck, args.markdown, base, head, text)
    sys.exit(1 if regs and expected is None else 0)


if __name__ == "__main__":
    main()
