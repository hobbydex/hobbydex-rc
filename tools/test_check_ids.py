"""check_ids: an id gone from the tree fails unless a record's former_ids or data/retired.toml names it (the files
without the text former_ids are not parsed), and its stages are spans under the caller's TRACEPARENT, sent through the
tools' otel.py (a stand-in here: no network, no hobbydex-tools checkout).

    python3 -I tools/test_check_ids.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_ids  # noqa: E402

FAKE_OTEL = '''
SENT = []
def span(trace, span_id, parent, name, start, end, attrs=None, error=None, service=None, links=None, ok=False):
    SENT.append(dict(trace=trace, parent=parent, name=name, start=start, end=end, attrs=attrs, ok=ok))
'''
TP = "00-0123456789abcdef0123456789abcdef-00000000000000aa-01"


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def run(root, base):
    """check_ids.py on the tree at root against the tree-ish base: (exit code, output)."""
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "check_ids.py"), base], cwd=root,
                       capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "TRACEPARENT"})
    return p.returncode, p.stdout


def test_a_gone_id_needs_a_trace():
    with tempfile.TemporaryDirectory() as root:
        git(root, "init", "-q")
        write(root, "data/kits/acme/a1.toml", 'name = "A1"\n')
        write(root, "data/kits/acme/a2.toml", 'name = "A2"\n')
        write(root, "data/kits/acme/a3.toml", 'name = "A3"\n')
        git(root, "add", "-A")
        base = git(root, "write-tree")   # a tree as the base: no commit (and so no author) needed
        os.remove(os.path.join(root, "data/kits/acme/a1.toml"))
        os.remove(os.path.join(root, "data/kits/acme/a2.toml"))
        code, out = run(root, base)
        assert code == 1 and "kit/acme/a1: removed" in out and "kit/acme/a2: removed" in out, out
        write(root, "data/kits/acme/a3.toml", 'name = "A3"\nformer_ids = ["kit/acme/a1"]\n')
        write(root, "data/retired.toml", '[[retired]]\nid = "kit/acme/a2"\nreason = "misread"\n')
        code, out = run(root, base)
        assert code == 0 and "0 gone without a trace" in out, out


def test_the_stages_are_spans_under_the_callers_step():
    with tempfile.TemporaryDirectory() as tools:
        os.makedirs(os.path.join(tools, "tools"))
        with open(os.path.join(tools, "tools", "otel.py"), "w") as f:
            f.write(FAKE_OTEL)
        record = check_ids.stage_spans({"TRACEPARENT": TP, "HOBBYDEX_TOOLS": tools})
        record("read git tree", rows=3)
        record("read data", files=2, parsed=1)
        record("compute gone ids", items=0)
        sent = record.otel.SENT
        assert [s["name"] for s in sent] == ["read git tree", "read data", "compute gone ids"]
        assert all(s["parent"] == "00000000000000aa" and s["trace"] == "0123456789abcdef0123456789abcdef" for s in sent)
        assert all(s["ok"] for s in sent)
        assert sent[1]["attrs"] == {"files": 2, "parsed": 1, "io": "read"}
        assert sent[1]["start"] == sent[0]["end"]   # one stage after the other


def test_without_a_traceparent_or_tools_nothing_is_recorded():
    with tempfile.TemporaryDirectory() as tools:
        assert check_ids.stage_spans({"HOBBYDEX_TOOLS": tools}).otel is None
        assert check_ids.stage_spans({"TRACEPARENT": TP, "HOBBYDEX_TOOLS": tools}).otel is None   # no otel.py
        assert check_ids.stage_spans({"TRACEPARENT": TP}).otel is None


if __name__ == "__main__":
    test_a_gone_id_needs_a_trace()
    test_the_stages_are_spans_under_the_callers_step()
    test_without_a_traceparent_or_tools_nothing_is_recorded()
    print("ok")
