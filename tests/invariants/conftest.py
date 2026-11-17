"""The data invariants as a test suite: `pytest tests/invariants -n auto` on a hobbydex-rc checkout.

The data tree is parsed once per run, before the workers start, into one SQLite snapshot (snapshot.py); every
pytest-xdist worker opens that file read-only. Each test is one invariant: a query whose rows are the offending
records. A hard invariant fails on any row; a ratchet compares its count with baseline.toml and fails only when the
count grew (docs/invariants.md).

Options: --limit N (offending records shown per failure, default 20; 0 shows all), --update-baselines (write the
lower counts of this run into baseline.toml; never raises one). Budget: the whole run is meant to take about a minute;
over WARN_S it says so, over FAIL_S the run fails (a slow new invariant must not creep in).
"""
import fcntl, os, sys, tempfile, time, tomllib, warnings

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snapshot  # noqa: E402

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baseline.toml")
WARN_S, FAIL_S = 120, 300
_state = {"t0": time.monotonic(), "lowered": {}}


def pytest_addoption(parser):
    g = parser.getgroup("invariants")
    g.addoption("--limit", type=int, default=20, help="offending records shown per failing invariant (0: all)")
    g.addoption("--update-baselines", action="store_true", help="lower baseline.toml to this run's ratchet counts")
    g.addoption("--snapshot", help="reuse this snapshot file instead of building one (it must match the checkout)")


def pytest_configure(config):
    if hasattr(config, "workerinput"):   # an xdist worker: the controller built the snapshot
        config.invariants_db = config.workerinput["invariants_db"]
        return
    if config.getoption("--snapshot"):
        config.invariants_db = config.getoption("--snapshot")
        return
    t0 = time.monotonic()
    d = tempfile.mkdtemp(prefix="hobbydex-invariants-")
    config.invariants_db = os.path.join(d, "snapshot.sqlite")
    n = snapshot.build_tree(config.invariants_db)
    config.invariants_load = (n, time.monotonic() - t0)


def pytest_configure_node(node):   # xdist hook: hand the snapshot path to each worker
    node.workerinput["invariants_db"] = node.config.invariants_db


def pytest_report_header(config):
    if hasattr(config, "invariants_load"):
        n, s = config.invariants_load
        return f"invariants: {n} record files loaded in {s:.1f} s ({snapshot.WORKERS} processes)"


def pytest_unconfigure(config):
    if hasattr(config, "workerinput") or config.getoption("--snapshot") or not hasattr(config, "invariants_db"):
        return
    path = config.invariants_db
    for p in (path, os.path.dirname(path)):
        try:
            os.remove(p) if p == path else os.rmdir(p)
        except OSError:
            pass


def pytest_sessionfinish(session, exitstatus):
    if hasattr(session.config, "workerinput"):
        return
    took = time.monotonic() - _state["t0"]
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    if tr:
        tr.write_line(f"invariants: the run took {took:.0f} s (budget: warn over {WARN_S} s, fail over {FAIL_S} s)")
    if took > FAIL_S:
        if tr:
            tr.write_line(f"invariants: FAILED: over the {FAIL_S} s budget; find the slow invariant with --durations=5")
        session.exitstatus = 1
    elif took > WARN_S and tr:
        tr.write_line(f"invariants: WARNING: over {WARN_S} s; find the slow invariant with --durations=5")


@pytest.fixture(scope="session")
def db(request):
    con = snapshot.connect(request.config.invariants_db, readonly=True)
    yield con
    con.close()


@pytest.fixture(scope="session")
def limit(request):
    return request.config.getoption("--limit")


def baselines():
    with open(BASELINE, "rb") as f:
        return tomllib.load(f)


def _rows(db, sql):
    cur = db.execute(sql)
    cols = [c[0] for c in cur.description]
    i, j = cols.index("record"), cols.index("problem")
    return sorted({(r[i], r[j]) for r in cur}, key=lambda r: (str(r[0]), str(r[1])))


def _listing(rows, limit):
    shown = rows[: limit or None]
    lines = [f"  {rec}: {problem}" for rec, problem in shown]
    if len(rows) > len(shown):
        lines.append(f"  ... {len(rows) - len(shown)} more (--limit 0 shows all)")
    return "\n".join(lines)


@pytest.fixture
def hard(db, limit, request):
    """hard(sql): fail with the offending records when the query returns any row."""
    def run(sql):
        rows = _rows(db, sql)
        if rows:
            doc = " ".join((request.function.__doc__ or "").split())
            pytest.fail(f"{len(rows)} offending: {doc}\n{_listing(rows, limit)}", pytrace=False)
    return run


@pytest.fixture
def ratchet(db, limit, request):
    """ratchet(name, sql): fail when the query returns more rows than baseline.toml allows for name. With
    blocking=False a grown count is a warning in the summary, not a failure (a gap the importers still add to)."""
    def run(name, sql, blocking=True):
        rows = _rows(db, sql)
        base = baselines().get(name)
        doc = " ".join((request.function.__doc__ or "").split())
        if base is None:
            pytest.fail(f"{name}: no baseline in tests/invariants/baseline.toml; add {name} = {len(rows)}", pytrace=False)
        if len(rows) > base and not blocking:
            warnings.warn(f"{name}: {len(rows)} offending, over the baseline {base} (reported, not blocking)")
        elif len(rows) > base:
            pytest.fail(f"{name}: {len(rows)} offending, the baseline allows {base} (a change may only lower it): "
                        f"{doc}\n{_listing(rows, limit)}", pytrace=False)
        if len(rows) < base:
            print(f"{name}: {len(rows)} now, baseline {base}: lower the baseline (--update-baselines)")
            if request.config.getoption("--update-baselines"):
                _lower(name, len(rows))
    return run


def _lower(name, count):
    """Rewrite the line `name = N` of baseline.toml to the lower count (the file's comments and order stay)."""
    with open(BASELINE + ".lock", "w") as lock:   # xdist workers lower their own lines one at a time
        fcntl.flock(lock, fcntl.LOCK_EX)
        _lower_locked(name, count)
    try:
        os.remove(BASELINE + ".lock")
    except OSError:
        pass


def _lower_locked(name, count):
    with open(BASELINE) as f:
        lines = f.read().splitlines(keepends=True)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key == name:
            old = int(line.split("=", 1)[1].split("#", 1)[0])
            if count < old:
                lines[i] = f"{name} = {count}\n"
    with open(BASELINE, "w") as f:
        f.writelines(lines)
