"""Export everything under data/ as one JSON document for the website build.

This file is the contract between the data repo and hobbydex/hobbydex: the
site reads only this export, never the TOML tree. Bump schema_version when a
field changes meaning or disappears. Every record also carries `toml_path`,
its file in this repo (data/parts/...), which is not a field of the TOML.
`retired` lists data/retired.toml: ids that are gone, each with its reason
and, when one took its place, replaced_by (the site redirects those).
A kit, release or body part with a file in art/ carries `art`: the `d`
attribute of its path(s), joined with a space, to draw in a 48x24 viewBox (the
viewBox is the same for every file, so it is not repeated).

Every record also carries `modified`, the UTC date (YYYY-MM-DD) of the last
commit that changed its file (or its art file); the site turns it into the
sitemap's <lastmod>. Renames are followed: a pure move keeps the date of the
content, a move with edits counts as a change. Left out when the repo has no
usable history (not a git checkout, or a shallow one: CI must fetch it all).

`content_modified` is the same for the record's content only: the last commit
that changed a field other than bookkeeping (BOOKKEEPING below: where a value
came from, former ids, the seen_by bound; at any depth, so a fits row that
only gains a `source` is no change), or its art file. It is written only
where it differs from `modified`; the site's sitemap <lastmod> reads it.

Run from the repo root: python3 -I tools/export.py [out.json]
"""
import datetime, json, os, subprocess, sys, tomllib
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import ART_KINDS, art_path

KINDS = {"brands": "brand", "kits": "kit", "releases": "release", "parts": "part", "documents": "doc", "specs": "spec", "shops": "shop", "categories": "category", "standards": "standard", "companies": "company", "makes": "make"}

def art_of(entity_id):
    """The path data of a kit's, release's or body part's art, or None when it has none."""
    path = art_path(entity_id)
    if not os.path.exists(path):
        return None
    root = ET.parse(path).getroot()
    return " ".join(" ".join(p.get("d", "").split()) for p in root.iter("{http://www.w3.org/2000/svg}path")) or None

# Fields that record how a value was found, not what the record says: changes to them alone leave
# `content_modified` as it was. Also every key ending in _source or _basis (name_source, pack_qty_basis).
BOOKKEEPING = {"sources", "source", "listed_in", "basis", "former_ids", "seen_by", "seen_by_source", "reported_by", "ocr_names"}

def is_bookkeeping(key):
    return key in BOOKKEEPING or key.endswith("_source") or key.endswith("_basis")

def content_of(value):
    """The value with every bookkeeping key removed, at any depth (tables in lists included)."""
    if isinstance(value, dict):
        return {k: content_of(v) for k, v in value.items() if not is_bookkeeping(k)}
    if isinstance(value, list):
        return [content_of(v) for v in value]
    return value

def last_commit_dates():
    """{path: UTC date of the last commit touching it}; see history()."""
    got = history()
    return got and got[0]

def history():
    """({path: UTC date of the last commit touching it}, {toml path: UTC date of the last commit that
    changed its content}) for data/ and art/, from one pass over the history, newest first, or None
    without usable history. A pure rename (R100) hands the old path's earlier commits to the new
    path; a rename with edits is a change dated at that commit. Content dates compare each commit's
    old and new blob of a file (git cat-file) until the first one whose content_of differs."""
    git = ["git", "-c", "core.quotepath=off"]
    try:
        if subprocess.run(git + ["rev-parse", "--is-shallow-repository"], capture_output=True, text=True, check=True).stdout.strip() != "false":
            return None
    except (OSError, subprocess.CalledProcessError):
        return None
    log = subprocess.Popen(git + ["log", "-M", "--raw", "--no-abbrev", "--format=C %ct", "--", "data", "art"], stdout=subprocess.PIPE, text=True)
    cat = subprocess.Popen(git + ["cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    none = "0" * 40
    def content(sha):
        if sha == none:
            return None
        cat.stdin.write(sha.encode() + b"\n"); cat.stdin.flush()
        size = int(cat.stdout.readline().split()[2])
        data = cat.stdout.read(size); cat.stdout.read(1)
        try:
            return content_of(tomllib.loads(data.decode("utf-8")))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            return data   # an unreadable version: compared as bytes
    dates, changed, alias, when = {}, {}, {}, 0
    def canon(path):
        while path in alias:
            path = alias[path]
        return path
    try:
        for line in log.stdout:
            if line.startswith("C "):
                when = int(line[2:])
                continue
            if not line.startswith(":"):
                continue
            meta, *paths = line.rstrip("\n").split("\t")
            _, _, old, new, status = meta.split()
            if status[0] == "R":
                path = canon(paths[1])
                alias[paths[0]] = path
                if status == "R100":
                    continue
            elif status[0] in "AMT":
                path = canon(paths[0])
            else:
                continue
            dates.setdefault(path, when)
            if path.endswith(".toml") and path not in changed and (old == none or content(old) != content(new)):
                changed[path] = when
    finally:
        cat.stdin.close(); cat.wait()
        log.stdout.close()
    if log.wait() != 0:
        raise RuntimeError("git log failed")
    day = lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date().isoformat()
    return {p: day(t) for p, t in dates.items()}, {p: day(t) for p, t in changed.items()}

def build_document():
    """The export as a dict (run from the repository root): every record under data/ by type,
    plus `retired`. tools/export_release.py writes the same dict for the release files."""
    doc = {"schema_version": 0, "dataset": "rc", "generated": datetime.date.today().isoformat()}
    got = history()
    dates, changed = got or (None, None)
    if dates is None:
        print("no usable git history: records get no `modified`", file=sys.stderr)
    for folder in KINDS:
        items = []
        base = os.path.join("data", folder)
        for dirpath, _, files in os.walk(base):
            for fn in sorted(files):
                if fn.endswith(".toml"):
                    path = os.path.join(dirpath, fn)
                    with open(path, "rb") as f:
                        d = tomllib.load(f)
                    d["toml_path"] = path.replace(os.sep, "/")   # the record's file in this repo, for "view/edit on GitHub" links
                    if KINDS[folder] in ART_KINDS and (art := art_of(d["id"])):
                        d["art"] = art
                    if dates:
                        stamps = [dates[x] for x in (d["toml_path"], art_path(d["id"]) if KINDS[folder] in ART_KINDS else None) if x in dates]
                        if stamps:
                            d["modified"] = max(stamps)
                        art = [dates[x] for x in (art_path(d["id"]) if KINDS[folder] in ART_KINDS else None,) if x in dates]
                        shown = max([changed[d["toml_path"]]] + art) if d["toml_path"] in changed else None
                        if shown and shown != d.get("modified"):
                            d["content_modified"] = shown
                    items.append(d)
        items.sort(key=lambda d: d["id"])
        doc[folder] = items
    with open(os.path.join("data", "retired.toml"), "rb") as f:
        doc["retired"] = tomllib.load(f).get("retired", [])
    return doc

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "dist/hobbydex-rc.json"
    doc = build_document()
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    arts = sum("art" in d for k in KINDS for d in doc[k])
    mods = sum("modified" in d for k in KINDS for d in doc[k])
    older = sum("content_modified" in d for k in KINDS for d in doc[k])
    print(out, ", ".join(f"{k}={len(doc[k])}" for k in KINDS), f"art={arts}", f"modified={mods}", f"content_modified={older}", f"{os.path.getsize(out)/1e6:.1f} MB")

if __name__ == "__main__":
    main()
