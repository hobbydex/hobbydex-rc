"""Cases for audit.tamiya_static_non_rc: a cached Tamiya manual of a static kit, paint or tool is not an RC gap.

    python3 -I tools/test_audit_tamiya_static.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

NO_DATA = set()


def test_military_kit_with_no_release_is_not_rc():
    assert audit.tamiya_static_non_rc("manuals/tamiya-de/300035009/300035009_Panzerkampfwagen_II_F-G.pdf", NO_DATA)


def test_aircraft_kit_with_no_release_is_not_rc():
    assert audit.tamiya_static_non_rc("manuals/tamiya-de/300060301/300060301_F-14A_Grumman_Tomcat.pdf", NO_DATA)


def test_plastic_model_series_is_not_rc():
    assert audit.tamiya_static_non_rc("manuals/tamiya-de/300010001/300010001_Porsche_910.pdf", NO_DATA)


def test_airbrush_and_paint_are_not_rc():
    assert audit.tamiya_static_non_rc("manuals/tamiya-de/300074514/300074514_Anleitung-Instruction.pdf", NO_DATA)
    assert audit.tamiya_static_non_rc("manuals/tamiya-de/300087051/300087051_Anleitung-Instruction_TamiyaEpoxyPutty.pdf", NO_DATA)


def test_tank_kit_56xxx_stays_in():
    # 56045 is the Centurion Mk.III RC tank: RC, so its manual stays in the gap check
    assert not audit.tamiya_static_non_rc("manuals/tamiya-de/300056045/300056045_Centurion_Mk.III_Bedienung.pdf", NO_DATA)


def test_option_part_and_rc_car_stay_in():
    assert not audit.tamiya_static_non_rc("manuals/tamiya-de/300054005/300054005_Option.pdf", NO_DATA)
    assert not audit.tamiya_static_non_rc("manuals/tamiya-de/300058571/300058571_Anleitung-Instruction_TT-02.pdf", NO_DATA)


def test_crawler_70xxx_stays_in():
    assert not audit.tamiya_static_non_rc("manuals/tamiya-de/300070247/300070247_4-Track_Crawler.pdf", NO_DATA)


def test_number_with_a_release_or_part_stays_in():
    assert not audit.tamiya_static_non_rc("manuals/tamiya-de/300035009/300035009_Panzerkampfwagen_II_F-G.pdf", {"35009"})


def test_other_brands_and_folders_stay_in():
    assert not audit.tamiya_static_non_rc("manuals/tamiya/56040-56040.pdf", NO_DATA)
    assert not audit.tamiya_static_non_rc("manuals/tamiya-usa/84026-manual.pdf", NO_DATA)
    assert not audit.tamiya_static_non_rc("manuals/tamiya-de/35009/35009_x.pdf", NO_DATA)
    assert not audit.tamiya_static_non_rc("manuals/tamiya-de/300035009.pdf", NO_DATA)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
