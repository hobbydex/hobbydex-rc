"""audit.check_spans: each check is a span "check <name>" under the TRACEPARENT the audit job passes, sent through
the tools' otel.py (a stand-in here: no network, no hobbydex-tools checkout). No TRACEPARENT: nothing is recorded.

    python3 -I tools/test_audit_check_spans.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

FAKE_OTEL = '''
SENT = []
def span(trace, span_id, parent, name, start, end, attrs=None, error=None, service=None):
    SENT.append(dict(trace=trace, parent=parent, name=name, start=start, end=end, attrs=attrs, service=service))
'''
TP = "00-0123456789abcdef0123456789abcdef-00000000000000aa-01"


def test_each_check_is_a_span_under_the_job_part():
    with tempfile.TemporaryDirectory() as tools:
        os.makedirs(os.path.join(tools, "tools"))
        with open(os.path.join(tools, "tools", "otel.py"), "w") as f:
            f.write(FAKE_OTEL)
        record = audit.check_spans(tools, {"TRACEPARENT": TP})
        record("a", 3)
        record("b", 0)
        sent = record.otel.SENT
        assert [s["name"] for s in sent] == ["check a", "check b"]
        assert sent[0]["parent"] == "00000000000000aa" and sent[0]["trace"] == "0123456789abcdef0123456789abcdef"
        assert sent[0]["attrs"] == {"check": "a", "count": 3}
        assert sent[1]["start"] == sent[0]["end"]   # the work between two checks is the next check's


def test_without_a_traceparent_nothing_is_recorded():
    with tempfile.TemporaryDirectory() as tools:
        assert audit.check_spans(tools, {}) is None
        assert audit.check_spans(tools, {"TRACEPARENT": TP}) is None   # no otel.py in the tools


if __name__ == "__main__":
    test_each_check_is_a_span_under_the_job_part()
    test_without_a_traceparent_nothing_is_recorded()
    print("ok")
