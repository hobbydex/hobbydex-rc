"""Cases for audit.localised_title: a maker's file in its own language keeps its title; a localised page or video is listed.

    python3 -I tools/test_audit_title_language.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402


def test_french_manual_keeps_its_title():
    assert not audit.localised_title({"kind": "manual", "title": "Guide de référence BX8SL"})
    assert not audit.localised_title({"kind": "setup_sheet", "title": "Fiche de réglage CRX2 MADPERF"})
    assert not audit.localised_title({"kind": "supplement", "title": "SSX-823_Garantie en Gebruikvoorzorgen"})


def test_localised_video_is_listed():
    assert audit.localised_title({"kind": "video", "title": "Bekijk onze nieuwe buggy"})


def test_english_title():
    assert not audit.localised_title({"kind": "video", "title": "The new buggy"})


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
