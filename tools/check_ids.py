"""Fail when an id that existed at a base revision is gone without a trace.

Ids are permanent: people and search engines link to the pages built from
them. An id that disappears must be listed in `former_ids` of the record that
took it over (a renamed kit, a corrected part number, a merge), or in
data/retired.toml with a reason (an OCR misread that was never a real part).

    python3 -I tools/check_ids.py origin/main
"""
import os, subprocess, sys, tomllib
sys.path.insert(0, os.path.dirname(__file__))
from layout import DIRS

KIND = {v: k for k, v in DIRS.items()}

def id_of(path):
    parts = path.split("/")
    if len(parts) < 3 or parts[0] != "data" or not path.endswith(".toml") or parts[1] not in KIND:
        return None
    kind = KIND[parts[1]]
    if kind == "part":
        return f"part/{parts[2]}/{parts[-1][:-5]}"
    return f"{kind}/{'/'.join(parts[2:])[:-5]}"

def main(base):
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", base, "--", "data/"], capture_output=True, text=True, check=True).stdout
    before = {i for i in map(id_of, out.split()) if i}
    now, traced = set(), set()
    for dirpath, _, files in os.walk("data"):
        for fn in files:
            path = os.path.join(dirpath, fn)
            if path == "data/retired.toml":
                with open(path, "rb") as f:
                    traced |= {r["id"] for r in tomllib.load(f).get("retired", [])}
                continue
            i = id_of(path)
            if not i: continue
            now.add(i)
            with open(path, "rb") as f:
                traced |= set(tomllib.load(f).get("former_ids", []))
    gone = sorted(before - now - traced)
    for i in gone:
        print(f"{i}: removed since {base}; add it to former_ids of its successor or to data/retired.toml")
    print(f"{len(before)} ids at {base}, {len(now)} now, {len(gone)} gone without a trace")
    sys.exit(1 if gone else 0)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "origin/main")
