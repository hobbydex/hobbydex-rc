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

def last_commit_dates():
    """{path: UTC date of the last commit touching it} for data/ and art/, from one pass over
    the history, newest first. A pure rename (R100) hands the old path's earlier commits to the
    new path; a rename with edits is a change dated at that commit. None without usable history."""
    git = ["git", "-c", "core.quotepath=off"]
    try:
        if subprocess.run(git + ["rev-parse", "--is-shallow-repository"], capture_output=True, text=True, check=True).stdout.strip() != "false":
            return None
        log = subprocess.run(git + ["log", "-M", "--name-status", "--format=C %ct", "--", "data", "art"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    dates, alias, when = {}, {}, 0
    def canon(path):
        while path in alias:
            path = alias[path]
        return path
    for line in log.splitlines():
        if line.startswith("C "):
            when = int(line[2:])
        elif line.startswith("R"):
            _, old, new = line.split("\t")
            new = canon(new)
            if not line.startswith("R100"):
                dates.setdefault(new, when)
            alias[old] = new
        elif line and line[0] in "AMT":
            dates.setdefault(canon(line.split("\t", 1)[1]), when)
    return {p: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date().isoformat() for p, t in dates.items()}

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "dist/hobbydex-rc.json"
    doc = {"schema_version": 0, "dataset": "rc", "generated": datetime.date.today().isoformat()}
    dates = last_commit_dates()
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
                    items.append(d)
        items.sort(key=lambda d: d["id"])
        doc[folder] = items
    with open(os.path.join("data", "retired.toml"), "rb") as f:
        doc["retired"] = tomllib.load(f).get("retired", [])
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    arts = sum("art" in d for k in KINDS for d in doc[k])
    mods = sum("modified" in d for k in KINDS for d in doc[k])
    print(out, ", ".join(f"{k}={len(doc[k])}" for k in KINDS), f"art={arts}", f"modified={mods}", f"{os.path.getsize(out)/1e6:.1f} MB")

if __name__ == "__main__":
    main()
