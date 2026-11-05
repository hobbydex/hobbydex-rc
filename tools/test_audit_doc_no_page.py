"""Cases for audit.doc_no_page_or_url: a document with neither its listing page nor a url is a gap; a video never is.

    python3 -I tools/test_audit_doc_no_page.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402


def test_manual_without_page_or_url_is_a_gap():
    assert audit.doc_no_page_or_url({"id": "doc/x/a-manual", "kind": "manual", "file": "a.pdf"})


def test_document_with_a_page_or_a_url_is_not_a_gap():
    assert not audit.doc_no_page_or_url({"kind": "manual", "page": "https://example.test/p"})
    assert not audit.doc_no_page_or_url({"kind": "manual", "url": "https://example.test/a.pdf"})


def test_video_without_page_or_url_is_not_a_gap():
    assert not audit.doc_no_page_or_url({"id": "doc/x/youtube-abc", "kind": "video"})
    assert not audit.doc_no_page_or_url({"id": "doc/x/youtube-abc", "kind": "video", "file": "abc"})


def test_video_with_a_url_is_not_a_gap():
    assert not audit.doc_no_page_or_url({"kind": "video", "url": "https://www.youtube.com/watch?v=abc"})


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
