"""Report gaps in the data: what is missing, not what is wrong (that is validate.py).

    python3 -I tools/audit.py                 # summary per check and brand
    python3 -I tools/audit.py --list unnamed  # every entity a check flags
    python3 -I tools/audit.py --brand mst     # one brand only

Checks:
  unnamed       parts whose name is just their number
  ocr           parts whose name was read by OCR (notes say so): worth a look
  uncategorised named parts without a category
  screw-unlinked  parts named like a metric screw with no screw spec link
  bearing-unlinked  parts named like a bearing with a size and no bearing spec
  empty-release releases with no contains rows
  kit-fields    kits missing scale, drive or power
  doc-source    documents with neither url nor file
  orphan-spec   specs no part links to
Exit code is always 0; this is a to-do list, not a gate.
"""
import collections, os, re, sys, tomllib

ROOT = "data"

def load():
    out = collections.defaultdict(list)
    for dirpath, _, files in os.walk(ROOT):
        for fn in files:
            if fn.endswith(".toml"):
                with open(os.path.join(dirpath, fn), "rb") as f:
                    d = tomllib.load(f)
                out[d["id"].split("/", 1)[0]].append(d)
    return out

def brand_of(d):
    return d.get("brand", "").removeprefix("brand/") or d["id"].split("/")[1]

def checks(db):
    linked = {e["spec"] for p in db["part"] for e in p.get("equivalent_to", [])}
    for p in db["part"]:
        name, notes = p["name"], p.get("notes", "")
        if name == p["number"]:
            yield "unnamed", p
        elif re.search(r"\bOCR\b", notes):
            yield "ocr", p
        if name != p["number"] and not p.get("category"):
            yield "uncategorised", p
        specs = [e["spec"] for e in p.get("equivalent_to", [])]
        n = name.lower()
        if re.search(r"\bscrews?\b", n) and re.search(r"\bm?\d(\.\d)?\s?x\s?\d", n) and not any(s.startswith("spec/screw/") for s in specs):
            yield "screw-unlinked", p
        if re.search(r"bearing", n) and re.search(r"\d+\s?[x*]\s?\d+\s?[x*]\s?\d", n) and not any(s.startswith("spec/bearing/") for s in specs):
            yield "bearing-unlinked", p
    for r in db["release"]:
        if not r.get("contains"):
            yield "empty-release", r
    for k in db["kit"]:
        if any(f not in k for f in ("scale", "drive", "power")):
            yield "kit-fields", k
    for d in db["doc"]:
        if not d.get("url") and not d.get("file"):
            yield "doc-source", d
    for s in db["spec"]:
        if s["id"] not in linked:
            yield "orphan-spec", s

def main():
    args = sys.argv[1:]
    only = args[args.index("--list") + 1] if "--list" in args else None
    brand = args[args.index("--brand") + 1] if "--brand" in args else None
    db = load()
    found = collections.defaultdict(list)
    for check, d in checks(db):
        if brand and brand_of(d) != brand:
            continue
        found[check].append(d)
    if only:
        for d in sorted(found.get(only, []), key=lambda d: d["id"]):
            print(f"{d['id']}\t{d.get('name', d.get('title', ''))}")
        return
    total = {"part": len(db["part"]), "release": len(db["release"]), "kit": len(db["kit"]), "doc": len(db["doc"]), "spec": len(db["spec"])}
    for check in ("unnamed", "ocr", "uncategorised", "screw-unlinked", "bearing-unlinked", "empty-release", "kit-fields", "doc-source", "orphan-spec"):
        ds = found.get(check, [])
        kind = ds[0]["id"].split("/")[0] if ds else ""
        per = collections.Counter(brand_of(d) for d in ds)
        top = ", ".join(f"{b} {n}" for b, n in per.most_common(6))
        print(f"{check:18} {len(ds):6}" + (f" of {total[kind]}" if kind else "") + (f"   {top}" if top else ""))

if __name__ == "__main__":
    main()
