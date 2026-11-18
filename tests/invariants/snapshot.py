"""The data tree as one SQLite file, built once per test run and opened read-only by every pytest-xdist worker.

`records(id, kind, path, data)` holds every record file under data/ (kind: part, release, kit, doc, brand, ...; data:
the record as JSON, read with json_extract and json_each). TABLES below derive the lists the checks join on, each
with its indexes. SQL functions on every connection: norm_url(u), video_id(u), truthy(v) and REGEXP (`text REGEXP 'pattern'`:
Python's re.search, so (?i), \b and lookarounds work; a value that is not text never matches).

The files are parsed by a process pool (tomllib is CPU-bound): about 20 s for the full tree with 4 processes.
"""
import concurrent.futures, functools, json, multiprocessing, os, re, sqlite3, subprocess, sys, tomllib, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
RC = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(RC, "tools"))
from layout import DIRS  # noqa: E402

KIND = {v: k for k, v in DIRS.items()}
WORKERS = int(os.environ.get("INVARIANTS_WORKERS") or min(4, os.cpu_count() or 1))   # parse processes (the owner's PC: at most 4)
CHUNK = 2000   # files per task


def norm_url(u):
    """A URL as a key: no scheme, no leading www., no fragment, no trailing slash, the host in lower case."""
    if not isinstance(u, str) or not u.strip():
        return None
    s = urllib.parse.urlsplit(u.strip())
    host = (s.hostname or "").removeprefix("www.")
    if s.port:
        host += f":{s.port}"
    return host + s.path.rstrip("/") + (f"?{s.query}" if s.query else "")


def video_id(u):
    """The YouTube video id a URL names (watch?v=, youtu.be/, /shorts/, /embed/, /live/), else None."""
    if not isinstance(u, str):
        return None
    s = urllib.parse.urlsplit(u)
    host = (s.hostname or "").removeprefix("www.").removeprefix("m.")
    if host == "youtu.be":
        v = s.path.strip("/")
    elif host == "youtube.com":
        m = re.match(r"/(?:shorts|embed|live)/([^/?#]+)", s.path)
        v = m.group(1) if m else urllib.parse.parse_qs(s.query).get("v", [None])[0]
    else:
        return None
    return v if v and re.fullmatch(r"[A-Za-z0-9_-]{11}", v) else None


# derived tables: (name, select, indexed columns); built in this order
TABLES = [
    ("docs", """SELECT id, path, json_extract(data, '$.kind') AS kind, json_extract(data, '$.url') AS url,
        json_extract(data, '$.page') AS page, norm_url(json_extract(data, '$.url')) AS nurl,
        norm_url(json_extract(data, '$.page')) AS npage, video_id(json_extract(data, '$.url')) AS video
        FROM records WHERE kind = 'doc'""", ["id", "nurl", "video"]),
    ("links", """SELECT r.id AS owner, r.kind AS owner_kind, CAST(j.key AS INTEGER) AS idx,
        json_extract(j.value, '$.url') AS url, norm_url(json_extract(j.value, '$.url')) AS nurl,
        json_extract(j.value, '$.kind') AS kind, json_extract(j.value, '$.gone') AS gone
        FROM records r, json_each(r.data, '$.links') j WHERE json_type(r.data, '$.links') = 'array'""", ["owner"]),
    # the plain string lists of a record (ids, numbers or names), one row per entry
    ("list_values", """SELECT r.id AS owner, f.field AS field, j.value AS value
        FROM records r, (SELECT 'documents' AS field UNION ALL SELECT 'aliases' UNION ALL SELECT 'numbers'
          UNION ALL SELECT 'former_ids' UNION ALL SELECT 'former_numbers' UNION ALL SELECT 'listed_as'
          UNION ALL SELECT 'releases' UNION ALL SELECT 'kits' UNION ALL SELECT 'parts' UNION ALL SELECT 'requires') f,
        json_each(r.data, '$.' || f.field) j
        WHERE json_type(r.data, '$.' || f.field) = 'array' AND j.type = 'text'""", ["owner"]),
    # the rows of a record's lists of tables (fits, contains, includes), one row per entry, the row as JSON
    ("list_rows", """SELECT r.id AS owner, f.field AS field, CAST(j.key AS INTEGER) AS idx, j.value AS row
        FROM records r, (SELECT 'fits' AS field UNION ALL SELECT 'contains' UNION ALL SELECT 'includes') f,
        json_each(r.data, '$.' || f.field) j
        WHERE json_type(r.data, '$.' || f.field) = 'array'""", ["owner"]),
]


def kind_of(rel):
    """The entity kind of a path under data/ (data/parts/... is part); None for the lists beside the records."""
    parts = rel.split("/")
    return KIND.get(parts[1]) if len(parts) >= 3 and parts[0] == "data" else None


@functools.lru_cache(maxsize=None)
def _pattern(p):
    return re.compile(p)


def regexp(pattern, value):
    """SQLite's REGEXP operator (`value REGEXP pattern`): Python's re.search; a value that is not text is no match."""
    return isinstance(value, str) and _pattern(pattern).search(value) is not None


def truthy(v):
    """Python's truth of a json_extract value: no field, false, 0, "" and an empty list or table are false."""
    return v not in (None, "", "[]", "{}") and v != 0


def connect(path=":memory:", readonly=False):
    db = sqlite3.connect(f"file:{path}?mode=ro" if readonly else path, uri=readonly, check_same_thread=False)
    db.create_function("norm_url", 1, norm_url, deterministic=True)
    db.create_function("video_id", 1, video_id, deterministic=True)
    db.create_function("regexp", 2, regexp, deterministic=True)
    db.create_function("truthy", 1, truthy, deterministic=True)
    return db


def parse(rel, raw):
    """One record file (its bytes) as a records row; a file that does not parse is validate.py's to report (None)."""
    try:
        d = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return None
    return (d.get("id") if isinstance(d.get("id"), str) else None, kind_of(rel), rel, json.dumps(d, default=str))


def _parse_chunk(args):
    root, rels = args
    out = []
    for rel in rels:
        with open(os.path.join(root, rel), "rb") as f:
            row = parse(rel, f.read())
        if row:
            out.append(row)
    return out


def record_files(root):
    rels = []
    for dirpath, dirs, files in os.walk(os.path.join(root, "data")):
        dirs.sort()
        for fn in sorted(files):
            if fn.endswith(".toml"):
                rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
                if kind_of(rel):
                    rels.append(rel)
    return rels


def build(path, rows_iter):
    """Write the snapshot: records from rows_iter (lists of rows), then the derived tables and their indexes."""
    db = connect(path)
    db.execute("PRAGMA journal_mode = OFF")
    db.execute("PRAGMA synchronous = OFF")
    db.execute("CREATE TABLE records (id TEXT, kind TEXT, path TEXT, data TEXT)")
    for rows in rows_iter:
        db.executemany("INSERT INTO records VALUES (?, ?, ?, ?)", rows)
    for col in ("id", "kind", "path"):
        db.execute(f"CREATE INDEX records_{col} ON records ({col})")
    for name, sql, cols in TABLES:
        db.execute(f"CREATE TABLE {name} AS {sql}")
        for col in cols:
            db.execute(f"CREATE INDEX {name}_{col} ON {name} ({col})")
    db.commit()
    db.close()


def build_tree(path, root=RC, workers=WORKERS):
    """The snapshot of every record file of the checkout at root; returns the number of files."""
    rels = record_files(root)
    chunks = [(root, rels[i:i + CHUNK]) for i in range(0, len(rels), CHUNK)]
    if workers > 1:
        with concurrent.futures.ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("fork")) as pool:
            build(path, pool.map(_parse_chunk, chunks))
    else:
        build(path, map(_parse_chunk, chunks))
    return len(rels)


def changed_files(base, root=RC):
    """The record files that differ between the git revision base and the working tree: {path: bytes at base or None}."""
    out = subprocess.run(["git", "-C", root, "diff", "--name-only", "--no-renames", base, "--", "data/"],
                         capture_output=True, text=True, check=True).stdout
    changed = {}
    for rel in out.splitlines():
        if rel.endswith(".toml") and kind_of(rel):
            r = subprocess.run(["git", "-C", root, "show", f"{base}:{rel}"], capture_output=True)
            changed[rel] = r.stdout if r.returncode == 0 else None
    return changed


def build_base(path, changed):
    """The snapshot of the changed files as they were at the base revision (the ratchets count their hits there)."""
    build(path, [[row for rel, raw in changed.items() if raw is not None for row in [parse(rel, raw)] if row]])
