"""Validate every TOML file under data/.

Checks: file parses, the file is where tools/layout.py puts its id, required
fields per entity kind, every reference resolves, no duplicate ids. Exit code 1
on any error.

Run from the repo root: python3 -I tools/validate.py
"""
import os, re, sys, tomllib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import DIRS, path_for

ROOT = "data"
REQUIRED = {
    "brand": ["id", "name", "status"],
    "kit": ["id", "brand", "name", "category"],
    "release": ["id", "kit", "brand", "name", "year", "kind", "status"],
    "part": ["id", "brand", "number", "name"],
    "spec": ["id", "category"],
    "doc": ["id", "kind", "title"],
    "shop": ["id", "name", "status"],
}
KINDS = {k: dict(dir=DIRS[k], required=REQUIRED[k]) for k in REQUIRED}
REFS = {  # field -> expected id prefix
    "brand": "brand/", "kit": "kit/", "part": "part/", "spec": "spec/", "source": "doc/",
    "publisher": "brand/", "replaces": "part/", "supersedes": "part/",
}
LIST_REFS = {"documents": "doc/", "releases": "release/"}
ENUMS = {
    "release.status": {"announced", "released", "discontinued"},
    "release.kind": {"kit", "rtr", "arr"},
    "brand.status": {"active", "dormant", "gone"},
    "contains.role": {"kit", "option", "listed"},
    "doc.kind": {"manual", "part_list", "exploded_view", "supplement", "catalog", "product_page"},
    "equivalent_to.match": {"exact", "functional", "close"},
    "fits.type": {"direct", "replaces", "modification"},
    "part.material": {"steel", "stainless", "titanium", "aluminium", "brass", "plastic", "unknown"},
}

def main():
    errors, ids, docs = [], {}, []
    for dirpath, _, files in os.walk(ROOT):
        for fn in sorted(files):
            if not fn.endswith(".toml"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "rb") as f:
                    d = tomllib.load(f)
            except Exception as e:
                errors.append(f"{path}: parse error: {e}")
                continue
            rel = os.path.relpath(path, ROOT)
            top = rel.split(os.sep)[0]
            kind = next((k for k, v in KINDS.items() if v["dir"] == top), None)
            if kind is None:
                errors.append(f"{path}: unknown entity directory {top}")
                continue
            try:
                expected_path = path_for(str(d.get("id", "")), ROOT)
            except ValueError as e:
                expected_path = None
                errors.append(f"{path}: {e}")
            if expected_path and os.path.normpath(expected_path) != os.path.normpath(path):
                errors.append(f"{path}: id {d.get('id')!r} belongs at {expected_path}")
            if not str(d.get("id", "")).startswith(f"{kind}/"):
                errors.append(f"{path}: id {d.get('id')!r} is not a {kind} id")
            if d.get("id") in ids:
                errors.append(f"{path}: duplicate id {d['id']} (also {ids[d['id']]})")
            ids[d.get("id")] = path
            for r in KINDS[kind]["required"]:
                if r not in d:
                    errors.append(f"{path}: missing required field {r}")
            docs.append((path, kind, d))
    for path, kind, d in docs:
        def check_ref(field, value, where):
            prefix = REFS.get(field)
            if prefix is None:
                return
            if not isinstance(value, str) or not value.startswith(prefix):
                errors.append(f"{path}: {where}{field} = {value!r} should start with {prefix}")
            elif value not in ids:
                errors.append(f"{path}: {where}{field} -> {value} does not exist")
        for k, v in d.items():
            if k in REFS:
                check_ref(k, v, "")
            elif k in LIST_REFS and isinstance(v, list):
                for x in v:
                    if x not in ids:
                        errors.append(f"{path}: {k} -> {x} does not exist")
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                for i, row in enumerate(v):
                    for kk, vv in row.items():
                        check_ref(kk, vv, f"{k}[{i}].")
                        key = f"{k}.{kk}"
                        if key in ENUMS and vv not in ENUMS[key]:
                            errors.append(f"{path}: {key} = {vv!r} not in {sorted(ENUMS[key])}")
            key = f"{kind}.{k}"
            if key in ENUMS and v not in ENUMS[key]:
                errors.append(f"{path}: {key} = {v!r} not in {sorted(ENUMS[key])}")
        if kind == "part" and "gtin" in d:
            g = str(d["gtin"])
            digits = [int(c) for c in g] if g.isdigit() else []
            ok = len(digits) in (8, 12, 13, 14) and (10 - sum(x * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(digits[:-1]))) % 10) % 10 == digits[-1]
            if not ok:
                errors.append(f"{path}: gtin {g!r} is not a valid GTIN-8/12/13/14 (length or check digit)")
        if kind == "part" and not re.match(r"^[A-Za-z0-9][A-Za-z0-9.\-]*$", str(d.get("number", ""))):
            errors.append(f"{path}: odd part number {d.get('number')!r}")
    counts = {}
    for _, kind, _ in docs:
        counts[kind] = counts.get(kind, 0) + 1
    print("entities:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if errors:
        print(f"{len(errors)} error(s):")
        for e in errors[:200]:
            print(" ", e)
        sys.exit(1)
    print("ok")

if __name__ == "__main__":
    main()
