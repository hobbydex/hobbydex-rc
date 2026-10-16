"""Export everything under data/ as one JSON document for the website build.

This file is the contract between the data repo and hobbydex/hobbydex: the
site reads only this export, never the TOML tree. Bump schema_version when a
field changes meaning or disappears. Every record also carries `toml_path`,
its file in this repo (data/parts/...), which is not a field of the TOML.
A kit or release with a file in art/ carries `art`: the `d` attribute of its
path(s), joined with a space, to draw in a 48x24 viewBox (the viewBox is the
same for every file, so it is not repeated).

Run from the repo root: python3 -I tools/export.py [out.json]
"""
import datetime, json, os, sys, tomllib
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import ART_KINDS, art_path

KINDS = {"brands": "brand", "kits": "kit", "releases": "release", "parts": "part", "documents": "doc", "specs": "spec", "shops": "shop", "categories": "category", "standards": "standard", "companies": "company"}

def art_of(entity_id):
    """The path data of a kit's or release's art, or None when it has none."""
    path = art_path(entity_id)
    if not os.path.exists(path):
        return None
    root = ET.parse(path).getroot()
    return " ".join(" ".join(p.get("d", "").split()) for p in root.iter("{http://www.w3.org/2000/svg}path")) or None

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "dist/hobbydex-rc.json"
    doc = {"schema_version": 0, "dataset": "rc", "generated": datetime.date.today().isoformat()}
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
                    items.append(d)
        items.sort(key=lambda d: d["id"])
        doc[folder] = items
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    arts = sum("art" in d for k in KINDS for d in doc[k])
    print(out, ", ".join(f"{k}={len(doc[k])}" for k in KINDS), f"art={arts}", f"{os.path.getsize(out)/1e6:.1f} MB")

if __name__ == "__main__":
    main()
