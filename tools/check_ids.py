"""Fail when an id that existed at a base revision is gone without a trace.

Ids are permanent: people and search engines link to the pages built from
them. An id that disappears must be listed in `former_ids` of the record that
took it over (a renamed kit, a corrected part number, a merge), or in
data/retired.toml with a reason (an OCR misread that was never a real part).

    python3 -I tools/check_ids.py origin/main

Its stages (`read git tree`, `read data`, `compute gone ids`) are spans under
the caller's TRACEPARENT when HOBBYDEX_TOOLS names a hobbydex-tools checkout
(its tools/otel.py sends them); otherwise nothing is recorded.
"""
import importlib.util, os, re, secrets, subprocess, sys, time, tomllib
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

def stage_spans(environ=None):
    """A recorder of the stages as spans: each call record(name, **attrs) ends the span `name` that began where the
    previous one ended, under the span TRACEPARENT names (the caller's step), sent through the tools' otel.py found in
    HOBBYDEX_TOOLS. A no-op without TRACEPARENT or tools/otel.py there."""
    e = os.environ if environ is None else environ
    m = re.fullmatch(r"[0-9a-f]{2}-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}", (e.get("TRACEPARENT") or "").strip())
    tools = os.path.join(e.get("HOBBYDEX_TOOLS") or "", "tools")
    path = os.path.join(tools, "otel.py")
    last = [time.time()]
    if not m or not e.get("HOBBYDEX_TOOLS") or not os.path.isfile(path):
        def nothing(name, **attrs):
            last[0] = time.time()
        nothing.otel = None
        return nothing
    if tools not in sys.path:
        sys.path.append(tools)   # otel imports joblog from its own folder; appended: our modules come first
    spec = importlib.util.spec_from_file_location("otel", path)
    otel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(otel)
    trace, parent = m.group(1), m.group(2)

    def record(name, **attrs):
        now = time.time()
        io = name.split(" ", 1)[0]
        otel.span(trace, secrets.token_hex(8), parent, name, last[0], now, dict(attrs, io=io), ok=True)
        last[0] = now
    record.otel = otel   # the module that sends them (tests read what it was given)
    return record

def main(base):
    stage = stage_spans()
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", base, "--", "data/"], capture_output=True, text=True, check=True).stdout
    before = {i for i in map(id_of, out.splitlines()) if i}
    stage("read git tree", rev=base, rows=len(before))
    now, traced = set(), set()
    files = parsed = 0
    for dirpath, _, names in os.walk("data"):
        for fn in names:
            path = os.path.join(dirpath, fn)
            if path == "data/retired.toml":
                with open(path, "rb") as f:
                    traced |= {r["id"] for r in tomllib.load(f).get("retired", [])}
                continue
            i = id_of(path)
            if not i: continue
            now.add(i)
            files += 1
            with open(path, "rb") as f:
                raw = f.read()
            # only a file that names former_ids can have them: the others need no TOML parse (validate.py checks
            # every file's syntax)
            if b"former_ids" in raw:
                parsed += 1
                traced |= set(tomllib.loads(raw.decode("utf-8")).get("former_ids", []))
    stage("read data", path="data", files=files, parsed=parsed)
    gone = sorted(before - now - traced)
    stage("compute gone ids", items=len(gone))
    for i in gone:
        print(f"{i}: removed since {base}; add it to former_ids of its successor or to data/retired.toml")
    print(f"{len(before)} ids at {base}, {len(now)} now, {len(gone)} gone without a trace")
    sys.exit(1 if gone else 0)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "origin/main")
