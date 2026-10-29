"""Runs tools/audit.py on the data and fails when it does not finish or its peak memory passes 2 GB.

CI has no hobbydex-tools checkout (it is private), so the checks that read it are skipped here; the
data checks load every record and run, which is where the memory goes. The full run with the tools is
the daily audit, which passes the same check by hand (docs in hobbydex-tools).

    python3 -I tools/test_audit_memory.py
"""
import json, os, resource, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RC = os.path.dirname(HERE)
LIMIT_KB = 2 * 1024 * 1024   # the audit's peak resident memory, in KiB


def main():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "audit.json")
        run = subprocess.run(
            [sys.executable, "-I", os.path.join(HERE, "audit.py"), "--tools", os.path.join(tmp, "no-tools"),
             "--site", os.path.join(tmp, "no-site"), "--json", out],
            cwd=RC, capture_output=True, text=True)
        peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss   # largest child, KiB (Linux)
        if run.returncode != 0:
            print(run.stderr[-2000:], file=sys.stderr)
            sys.exit(f"audit.py exited {run.returncode}")
        with open(out, encoding="utf-8") as f:
            result = json.load(f)
    if "part-category-fallback" not in result:
        sys.exit("audit.py wrote no part-category-fallback check (the data checks did not run)")
    print(f"audit.py on the data: peak {peak // 1024} MB (limit {LIMIT_KB // 1024} MB), {len(result)} checks")
    if peak > LIMIT_KB:
        sys.exit(f"peak memory {peak // 1024} MB is over the {LIMIT_KB // 1024} MB limit")


if __name__ == "__main__":
    main()
