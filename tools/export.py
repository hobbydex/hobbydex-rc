"""Export everything under data/ as one JSON document for the website build.

This file is the contract between the data repo and hobbydex/hobbydex: the
site reads only this export, never the TOML tree. Bump schema_version when a
field changes meaning or disappears.

Run from the repo root: python3 -I tools/export.py [out.json]
"""
import datetime, json, os, sys, tomllib

KINDS = {"brands": "brand", "kits": "kit", "releases": "release", "parts": "part", "documents": "doc", "specs": "spec", "shops": "shop", "categories": "category"}

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "dist/hobbydex-rc.json"
    doc = {"schema_version": 0, "dataset": "rc", "generated": datetime.date.today().isoformat()}
    for folder in KINDS:
        items = []
        base = os.path.join("data", folder)
        for dirpath, _, files in os.walk(base):
            for fn in sorted(files):
                if fn.endswith(".toml"):
                    with open(os.path.join(dirpath, fn), "rb") as f:
                        items.append(tomllib.load(f))
        items.sort(key=lambda d: d["id"])
        doc[folder] = items
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(out, ", ".join(f"{k}={len(doc[k])}" for k in KINDS), f"{os.path.getsize(out)/1e6:.1f} MB")

if __name__ == "__main__":
    main()
