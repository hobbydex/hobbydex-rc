"""Write the files of one Hobbydex release into a folder (the release job attaches them).

Run from the repository root, in a checkout with full history and tags:

    python3 -I tools/export_release.py OUT_DIR --version 2026.11.0 [--previous v2026.10.0]

OUT_DIR gets:
  hobbydex.json, hobbydex.min.json  every record by type, the document tools/export.py
                                    builds (the site's rc.json)
  <type>.csv                        one per record type (brands, makes, kits, releases,
                                    parts, documents, specs, ...); header row first.
                                    List fields of plain values are joined with "|",
                                    nested tables are JSON text.
  hobbydex.sqlite                   one table per type (id is the primary key; the same
                                    flattening as the CSVs), and fits (part_id,
                                    kit_or_release, kit, type, car, replaces, source): one
                                    row per fits row, one per release when the row names
                                    releases
  manifest.json                     version, date, git commit, licence, counts per type and
                                    per brand, sha256 and size of every other file
  ATTRIBUTION.md                    how to credit the data
  CHANGES.md                        records added, removed and changed per type since the
                                    previous release tag (git diff of data/); "first release"
                                    when there is none

Without --previous, the newest vYYYY.MM.N tag that is an ancestor of HEAD (other than
the version's own tag) is compared against.
"""
import argparse, collections, datetime, hashlib, json, os, re, sqlite3, subprocess, sys, tomllib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export

LICENCE = "CC-BY-4.0"
LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/"
SOURCE_URL = "https://github.com/hobbydex/hobbydex-rc"
ATTRIBUTION_LINE = "Data: Hobbydex (https://hobbydex.com), CC BY 4.0"
TAG = re.compile(r"^v\d{4}\.\d{2}\.\d+$")
TYPES = list(export.KINDS) + ["retired"]   # the export's folders, then data/retired.toml


def git(*args, input=None):
    return subprocess.run(["git", "-c", "core.quotepath=off", *args], input=input, capture_output=True, check=True).stdout


def head_commit():
    return git("rev-parse", "HEAD").decode().strip()


def previous_tag(version):
    own = f"v{version}"
    tags = [t for t in git("tag", "--list", "v*", "--merged", "HEAD", "--sort=-v:refname").decode().split()
            if TAG.match(t) and t != own]
    return tags[0] if tags else None


def cell(value):
    """A value for CSV or SQLite: plain values as they are (booleans as true/false), lists of
    plain values joined with "|", anything nested as JSON text."""
    if isinstance(value, bool):   # before int: a bool is an int in Python
        return "true" if value else "false"
    if value is None or isinstance(value, (int, float, str)):
        return value
    if isinstance(value, list) and all(not isinstance(x, (dict, list)) for x in value):
        return "|".join(str(cell(x)) for x in value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def columns(records):
    """Every key any record has, id first, in first-seen order."""
    seen = {"id": None}
    for r in records:
        for k in r:
            seen.setdefault(k, None)
    return list(seen)


def fits_rows(parts):
    for p in parts:
        for f in p.get("fits", []):
            kit = f.get("kit")
            common = (p["id"], kit, f.get("type"), f.get("car"), f.get("replaces"), f.get("source"))
            if f.get("releases"):
                for rel in f["releases"]:
                    yield (common[0], rel, *common[1:])
            else:
                yield (common[0], kit, *common[1:])


FITS_COLUMNS = ["part_id", "kit_or_release", "kit", "type", "car", "replaces", "source"]


def write_csv(path, records, cols):
    import csv
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in records:
            w.writerow(["" if (v := cell(r.get(c))) is None else v for c in cols])


def write_sqlite(path, doc):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    try:
        for name in TYPES:
            records = doc[name]
            cols = columns(records)
            defs = ", ".join(f'"{c}" TEXT PRIMARY KEY' if c == "id" else f'"{c}"' for c in cols)
            con.execute(f'CREATE TABLE "{name}" ({defs})')
            marks = ", ".join("?" for _ in cols)
            con.executemany(f'INSERT INTO "{name}" VALUES ({marks})',
                            ([cell(r.get(c)) for c in cols] for r in records))
        fits = list(fits_rows(doc["parts"]))
        con.execute('CREATE TABLE "fits" ("part_id" TEXT, "kit_or_release" TEXT, "kit" TEXT, "type" TEXT, '
                    '"car" TEXT, "replaces" TEXT, "source" TEXT)')
        con.executemany("INSERT INTO fits VALUES (?, ?, ?, ?, ?, ?, ?)", fits)
        con.commit()
    finally:
        con.close()


def blobs(rev, paths):
    """{path: text} of the files at rev; a path missing at rev maps to None."""
    if not paths:
        return {}
    out = subprocess.run(["git", "cat-file", "--batch"], input="".join(f"{rev}:{p}\n" for p in paths).encode(),
                         capture_output=True, check=True).stdout
    result, pos = {}, 0
    for p in paths:
        nl = out.index(b"\n", pos)
        header = out[pos:nl].split()
        if len(header) == 2:   # "<object> missing"
            result[p] = None
            pos = nl + 1
        else:
            size = int(header[2])
            result[p] = out[nl + 1:nl + 1 + size].decode("utf-8")
            pos = nl + 2 + size
    return result


def is_record_file(path):
    """A file of an exported type: data/<type>/...toml, or data/retired.toml."""
    return path == "data/retired.toml" or (path.endswith(".toml") and path.split("/")[1] in export.KINDS)


def records_of(path, text):
    """[(type, id, record)] in one data file (retired.toml lists its entries under [[retired]])."""
    if text is None:
        return []
    parts = path.split("/")
    data = tomllib.loads(text)
    if path == "data/retired.toml":
        return [("retired", r["id"], r) for r in data.get("retired", [])]
    return [(parts[1], data["id"], data)] if parts[1] in export.KINDS and "id" in data else []


def changes_since(tag):
    """{type: (added, removed, changed)} of records between tag and HEAD, from the diff of data/."""
    pairs = []
    for line in git("diff", "--name-status", "-M", tag, "HEAD", "--", "data").decode().splitlines():
        fields = line.split("\t")
        status = fields[0][0]
        if status == "R":
            old, new = fields[1], fields[2]
        elif status == "A":
            old, new = None, fields[1]
        elif status == "D":
            old, new = fields[1], None
        else:   # M, T
            old = new = fields[1]
        if any(p and not is_record_file(p) for p in (old, new)):
            continue
        pairs.append((old, new))
    old_text = blobs(tag, [old for old, _ in pairs if old])
    new_text = blobs("HEAD", [new for _, new in pairs if new])
    old_map, new_map = {}, {}
    for old, new in pairs:
        for t, i, r in records_of(old, old_text.get(old)) if old else []:
            old_map[(t, i)] = r
        for t, i, r in records_of(new, new_text.get(new)) if new else []:
            new_map[(t, i)] = r
    counts = {t: [0, 0, 0] for t in TYPES}
    for key in set(old_map) | set(new_map):
        if key not in old_map:
            counts[key[0]][0] += 1
        elif key not in new_map:
            counts[key[0]][1] += 1
        elif old_map[key] != new_map[key]:
            counts[key[0]][2] += 1
    return counts


def changes_md(tag, counts):
    if tag is None:
        return "first release\n"
    lines = [f"Changes since {tag}, counted by record id from the git diff of data/.", "",
             "| Type | Added | Removed | Changed |", "|---|---:|---:|---:|"]
    for t in TYPES:
        a, r, c = counts[t]
        if a or r or c:
            lines.append(f"| {t} | {a} | {r} | {c} |")
    if len(lines) == 4:
        lines.append("| (none) | 0 | 0 | 0 |")
    return "\n".join(lines) + "\n"


def attribution_md(version):
    return f"""# Attribution

Hobbydex {version} data is licensed under the Creative Commons Attribution 4.0
International licence ({LICENCE_URL}).

To credit it, use:

    {ATTRIBUTION_LINE}

Releases made before the switch to CC BY 4.0 were released under CC0 1.0
Universal (public domain dedication, https://creativecommons.org/publicdomain/zero/1.0/).

Source: {SOURCE_URL}
"""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out", help="folder to write the release files into (created)")
    ap.add_argument("--version", required=True, help="CalVer version, e.g. 2026.11.0")
    ap.add_argument("--previous", help="tag to compare with (default: the newest release tag before this one)")
    args = ap.parse_args()
    if not re.fullmatch(r"\d{4}\.\d{2}\.\d+", args.version):
        ap.error("--version must look like 2026.11.0")
    out = args.out
    os.makedirs(out, exist_ok=True)
    previous = args.previous or previous_tag(args.version)

    doc = export.build_document()
    with open(os.path.join(out, "hobbydex.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "hobbydex.min.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    for name in TYPES:
        write_csv(os.path.join(out, f"{name}.csv"), doc[name], columns(doc[name]))
    fits = list(fits_rows(doc["parts"]))
    write_sqlite(os.path.join(out, "hobbydex.sqlite"), doc)

    counts = {t: len(doc[t]) for t in TYPES}
    per_brand = collections.defaultdict(lambda: collections.Counter())
    for t in TYPES:
        for r in doc[t]:
            if "brand" in r:
                per_brand[r["brand"]][t] += 1
    per_brand = {b: dict(sorted(c.items())) for b, c in sorted(per_brand.items())}

    with open(os.path.join(out, "ATTRIBUTION.md"), "w", encoding="utf-8") as f:
        f.write(attribution_md(args.version))
    with open(os.path.join(out, "CHANGES.md"), "w", encoding="utf-8") as f:
        f.write(changes_md(previous, changes_since(previous) if previous else None))

    files = {}
    for name in sorted(os.listdir(out)):
        path = os.path.join(out, name)
        files[name] = {"sha256": sha256(path), "bytes": os.path.getsize(path)}
    manifest = {
        "name": "Hobbydex",
        "version": args.version,
        "date": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "git_commit": head_commit(),
        "previous": previous,
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
        "attribution": ATTRIBUTION_LINE,
        "source": SOURCE_URL,
        "counts": counts,
        "fits": len(fits),
        "per_brand": per_brand,
        "files": files,
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(out, f"version={args.version}", ", ".join(f"{t}={counts[t]}" for t in TYPES), f"fits={len(fits)}",
          f"previous={previous}")


if __name__ == "__main__":
    main()
