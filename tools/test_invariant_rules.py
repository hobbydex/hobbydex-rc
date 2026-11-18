"""Cases for the word rules of the data invariants (tests/invariants/rules.py), which the suite runs on the real tree.

    python3 -I tools/test_invariant_rules.py
"""
import os, re, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "invariants"))
import rules  # noqa: E402


class PlaceholderTitle(unittest.TestCase):
    """doc-placeholder-title: a title of item numbers only, or one that repeats a token."""

    def test_repeated_item_number_is_flagged(self):
        self.assertTrue(rules.placeholder_title("Tamiya 43501 43501: instruction manual (tamiyausa.com, archived)"))
        self.assertTrue(rules.placeholder_title("Tamiya 58449 58449: supplement"))
        self.assertTrue(rules.placeholder_title("Kyosho KF01 KF01 Type 3: instructions"))
        self.assertTrue(rules.placeholder_title("PR Racing product page: 2023 2023 PR SB401-R"))

    def test_number_only_title_is_flagged(self):
        self.assertTrue(rules.placeholder_title("43501"))
        self.assertTrue(rules.placeholder_title("43501 43502"))

    def test_single_number_and_names_are_not_flagged(self):
        self.assertFalse(rules.placeholder_title("Tamiya 43501: instruction manual"))
        self.assertFalse(rules.placeholder_title("Tamiya 22007 Silicone Oil #5000: product page"))
        self.assertFalse(rules.placeholder_title("XRAY XB9 2026 spare parts list"))
        self.assertFalse(rules.placeholder_title("BD11"))   # a genuine video title: a model code, not a number
        self.assertFalse(rules.placeholder_title(""))
        self.assertFalse(rules.placeholder_title(None))


class ServicePack(unittest.TestCase):
    """service-pack-in-box: a service, rebuild or upgrade pack, not a part that names the kit it works with."""

    def test_service_pack(self):
        self.assertTrue(rules.is_service_pack("Rebuild kit, front differential"))
        self.assertTrue(rules.is_service_pack("Service pack, driveshafts"))
        self.assertTrue(rules.is_service_pack("Upgrade kit, extreme heavy duty"))

    def test_compat_clause_is_no_pack(self):
        self.assertFalse(rules.is_service_pack("Shock tower, front, extreme heavy duty, gray (for use with #9080 upgrade kit)"))
        self.assertFalse(rules.is_service_pack("Carriers, stub axle (for use with #9180, 9181, 9182 upgrade kit)"))

    def test_plain_part(self):
        self.assertFalse(rules.is_service_pack("Hinge pin set"))
        self.assertFalse(rules.is_service_pack(""))


class BodySet(unittest.TestCase):
    """body-manual-only: the manual of a body set sold apart, not a car's manual that names its body."""

    def test_body_set_manual(self):
        self.assertTrue(rules.is_body_set_doc("Tamiya 51578 body parts set: assembly manual", "doc/tamiya/spb-51578-manual"))

    def test_whole_car_manual_naming_its_body(self):
        self.assertFalse(rules.is_body_set_doc("Tamiya 47481 Super Avante (Painted Body) (TD4 Chassis): instruction manual", "doc/tamiya/47481-manual-de"))
        self.assertFalse(rules.is_body_set_doc("Carson 1:5 Chassis 100% RTR incl. Porsche Body: instruction manual", "doc/carson/x"))
        self.assertFalse(rules.is_body_set_doc("1/9 GP 4WD KIT DRX wo/Body: parts list", "doc/kyosho/31047-drx-parts-list-v01"))

    def test_missing_title(self):
        self.assertFalse(rules.is_body_set_doc(None, "doc/none"))


class TitleLanguage(unittest.TestCase):
    """title-language: Dutch, French, Spanish or German words in a title."""

    def test_localised_title_is_listed(self):
        self.assertTrue(re.search(rules.NON_ENGLISH, "Bekijk onze nieuwe buggy"))
        self.assertTrue(re.search(rules.NON_ENGLISH, "Guide de référence BX8SL"))

    def test_english_title(self):
        self.assertFalse(re.search(rules.NON_ENGLISH, "The new buggy"))
        self.assertFalse(re.search(rules.NON_ENGLISH, "Monster Van"))

    def test_own_language_files_keep_their_title(self):
        self.assertIn("manual", rules.OWN_LANGUAGE_FILES)
        self.assertIn("setup_sheet", rules.OWN_LANGUAGE_FILES)
        self.assertNotIn("video", rules.OWN_LANGUAGE_FILES)


class Brackets(unittest.TestCase):
    """name-unbalanced-bracket."""

    def test_unbalanced(self):
        self.assertTrue(rules.unbalanced("Shock Oil (500"))
        self.assertTrue(rules.unbalanced("Shock Oil 500)"))
        self.assertTrue(rules.unbalanced("Shock Oil （500"))
        self.assertFalse(rules.unbalanced("Shock Oil (500)"))
        self.assertFalse(rules.unbalanced("Shock Oil"))


def part(pid, brand, name, number=None, category="differential", **extra):
    return {"id": pid, "brand": brand, "name": name, "number": number or pid.split("/")[-1], "category": category, **extra}


class CompleteDiff(unittest.TestCase):
    """too-many-diffs: a whole differential assembly by its name."""

    def test_whole_assemblies_count(self):
        for name in ("Differential Assembly", "Diff Set Complete", "Complete Differential", "Assembled Differential",
                     "Front Complete Diff", "Differential complete", "Zorro Brushless Complete Centre Differential Unit",
                     "Center Differential Assembly", "Assembled Front/Rear Differential Set", "Diff. Assembly"):
            with self.subTest(name=name):
                self.assertTrue(rules.complete_diff("differential", name))

    def test_cases_gears_cups_and_other_components_do_not(self):
        for name in ("Gear Differential Unit Cup Joint Set", "Differential Case Set", "Differential Gear Set",
                     "Diff Gear Set", "Complete Differential (Steel Gears/Diff. Cups)", "Diff Cup Joint Complete",
                     "Complete Diff Gasket Set", "Complete Diff Shim Pack", "Complete Diff O-Ring Set",
                     "Differential Set", "Diff. Unit", "Differential Housing For F113",
                     "TA06 Gear Differential Unit Cup Joint Set"):
            with self.subTest(name=name):
                self.assertFalse(rules.complete_diff("differential", name))

    def test_category_must_be_differential(self):
        self.assertFalse(rules.complete_diff("screw", "Complete Differential"))


class SuffixTwins(unittest.TestCase):
    """release-suffix-twin: one item number the other plus a suffix, and one product."""

    def test_number_relation_suffix_either_way_only(self):
        self.assertTrue(rules.number_relation("34902", "34902D"))
        self.assertTrue(rules.number_relation("34902D", "34902"))
        self.assertTrue(rules.number_relation("10428", "10428-2"))
        self.assertFalse(rules.number_relation("34902", "34902"))
        self.assertFalse(rules.number_relation("34902", "34903D"))
        self.assertFalse(rules.number_relation("1234", "1234D"))

    def test_same_product(self):
        self.assertTrue(rules.same_product_record({"gtin": "4950344"}, {"gtin": "4950344"}))
        self.assertFalse(rules.same_product_record({"gtin": "4950344", "released_source": "https://x/p"},
                                                   {"gtin": "4950345", "released_source": "https://x/p"}))
        self.assertTrue(rules.same_product_record({"released_source": "https://x/p/"}, {"released_source": "https://X/p"}))
        self.assertFalse(rules.same_product_record({}, {}))


class Aircraft(unittest.TestCase):
    """part-no-car-link leaves aircraft, helicopter and drone parts out."""

    def test_aircraft(self):
        self.assertTrue(rules.is_aircraft_part("brand/t2m", "T5190-01"))
        self.assertTrue(rules.is_aircraft_part("brand/t2m", "T620-01"))
        self.assertFalse(rules.is_aircraft_part("brand/t2m", "T4919-01"))
        self.assertFalse(rules.is_aircraft_part("brand/t2m", "T4900-6"))
        self.assertFalse(rules.is_aircraft_part("brand/t2m", "T62"))
        self.assertFalse(rules.is_aircraft_part("brand/t2m", "T6200-1"))
        self.assertFalse(rules.is_aircraft_part("brand/xray", "T5190-01"))


class TamiyaMakerLink(unittest.TestCase):
    """tamiya-*-no-link: what counts as the maker's page."""

    def test_maker_links(self):
        capture = "https://web.archive.org/web/20150101000000/http://www.tamiyausa.com/items/radio-control-kits-30/x"
        self.assertTrue(rules.tamiya_maker_linked([{"site": "Tamiya USA (Internet Archive)", "url": capture, "kind": "archive"}]))
        self.assertTrue(rules.tamiya_maker_linked([{"site": "Tamiya", "url": "https://www.tamiya.com/japan/products/51331/index.html"}]))
        self.assertTrue(rules.tamiya_maker_linked([{"site": "Tamiya USA", "url": "https://www.tamiyausa.com/shop/x", "kind": "maker"}]))

    def test_other_links_do_not_count(self):
        self.assertFalse(rules.tamiya_maker_linked([{"site": "TamiyaBase", "url": "https://www.tamiyabase.com/parts/7619-51331", "kind": "fan-site"}]))
        self.assertFalse(rules.tamiya_maker_linked([{"site": "tamico.de", "url": "https://tamico.de/x", "kind": "dealer"}]))
        self.assertFalse(rules.tamiya_maker_linked([{"site": "RC", "url": "https://web.archive.org/web/20100101000000/https://www.example.com/x", "kind": "archive"}]))
        self.assertFalse(rules.tamiya_maker_linked([]))


class TwinParts(unittest.TestCase):
    """twin-parts: shared, copy or unclear."""
    brands = {
        "brand/hpi": {"id": "brand/hpi", "website": "https://www.hpiracing.com", "owner": None},
        "brand/maverick": {"id": "brand/maverick", "website": "https://www.maverick-rc.com", "owner": "company/hpi-racing"},
        "brand/other": {"id": "brand/other", "website": "https://www.other-rc.com", "owner": None},
        "brand/blackzon": {"id": "brand/blackzon", "website": "https://www.blackzon.de", "owner": "company/hpi-racing"},
    }
    companies = {"company/hpi-racing": {"id": "company/hpi-racing", "brand": "brand/hpi"}}
    docs = {"doc/hpi/list": {"brand": "brand/hpi"}, "doc/maverick/list": {"brand": "brand/maverick"},
            "doc/other/list": {"brand": "brand/other"}}

    def cls(self, a, b):
        return rules.twin_class(a, b, self.brands, self.companies, self.docs)

    def test_related_brands_each_citing_own_source_are_shared(self):
        self.assertEqual(self.cls(part("part/hpi/1", "brand/hpi", "LOCK NUT M2.5", documents=["doc/hpi/list"]),
                                  part("part/maverick/1", "brand/maverick", "LOCK NUT M2.5", documents=["doc/maverick/list"])), "shared")
        self.assertEqual(self.cls(part("part/hpi/1", "brand/hpi", "LOCK NUT", links=[{"url": "https://hpiracing.com/x"}]),
                                  part("part/maverick/1", "brand/maverick", "LOCK NUT", links=[{"url": "https://www.maverick-rc.com/p"}])), "shared")

    def test_unrelated_brands_are_unclear(self):
        self.assertEqual(self.cls(part("part/other/1", "brand/other", "25605", documents=["doc/other/list"]),
                                  part("part/hpi/1", "brand/hpi", "25605", documents=["doc/hpi/list"])), "unclear")

    def test_other_brands_source_is_a_copy(self):
        self.assertEqual(self.cls(part("part/blackzon/1", "brand/blackzon", "Diff Shaft", links=[{"url": "https://www.maverick-rc.com/x"}]),
                                  part("part/maverick/1", "brand/maverick", "Diff Shaft", documents=["doc/maverick/list"])), "copy")
        self.assertEqual(self.cls(part("part/other/1", "brand/other", "25605", documents=["doc/hpi/list"]),
                                  part("part/hpi/1", "brand/hpi", "25605", documents=["doc/hpi/list"])), "copy")

    def test_same_site_pair_is_shared(self):
        site = "https://www.team-titan.com.tw/"
        brands = {"brand/blitz": {"website": site, "owner": "company/team-titan"}, "brand/team-titan": {"website": site}}
        companies = {"company/team-titan": {"id": "company/team-titan", "brand": "brand/team-titan"}}
        link = [{"site": "Team Titan", "url": site + "products_class101.php?cid=28", "kind": "maker"}]
        a = part("part/blitz/60419-1", "brand/blitz", "TS050 Body Stiffener 0.5mm", links=link)
        b = part("part/team-titan/60419-1", "brand/team-titan", "TS050 Body Stiffener 0.5mm", links=link)
        self.assertEqual(rules.twin_class(a, b, brands, companies, {}), "shared")

    def test_rebrand_of_and_measures(self):
        a = part("part/other/3", "brand/other", "Motor")
        b = part("part/hpi/3", "brand/hpi", "Motor")
        self.assertEqual(self.cls(a, b), "unclear")
        a["power_w"], b["power_w"] = 650, 1000
        self.assertEqual(self.cls(a, b), "shared")   # two products
        b["power_w"] = 650
        a["rebrand_of"] = [{"part": "part/hpi/3", "certainty": "likely"}]
        self.assertEqual(self.cls(a, b), "shared")
        self.assertEqual(self.cls(b, a), "shared")

    def test_number_only_names_never_pair(self):
        self.assertEqual(rules.twin_pairs([part("part/a/11202", "brand/a", "11202"), part("part/b/11202", "brand/b", "11202")]), [])

    def test_pairs_need_one_number_and_one_name(self):
        same = [part("part/hpi/1", "brand/hpi", "Lock Nut"), part("part/maverick/1", "brand/maverick", "lock-nut")]
        other_name = [part("part/hpi/2", "brand/hpi", "Lock Nut"), part("part/maverick/2", "brand/maverick", "Nut")]
        other_number = [part("part/hpi/3", "brand/hpi", "Lock Nut"), part("part/maverick/4", "brand/maverick", "Lock Nut", number="4")]
        self.assertEqual(len(rules.twin_pairs(same + other_name + other_number)), 1)


def rel(rid, number, name, **dates):
    return dict(id=f"release/{rid}", number=number, name=name, **dates)


class EditionsNotGrouped(unittest.TestCase):
    """release-editions-not-grouped: editions of one kit launched together share a range; re-releases never pair."""

    def test_furitek_named_editions(self):
        a = rel("furitek/fur-2878", "FUR-2878", "TITAN U4 ULTIMATE 24 Nebula Edition ARTR w/ MicroFlex PRO 4WS TX/RX, "
                "TRI-UNITY PRO Sensored & Micro Tesla DigiBoard", seen_by="2026-11-12")
        b = rel("furitek/fur-2879", "FUR-2879", "TITAN U4 ULTIMATE 24 Supernova Edition ARTR w/ MicroFlex PRO 4WS TX/RX, "
                "TRI-UNITY PRO Sensored & Micro Tesla DigiBoard", seen_by="2026-11-12")
        self.assertEqual(rules.edition_pair(a, b), ("edition", "nebula edition", "supernova edition"))
        self.assertEqual(rules.market_bucket(a, b), "together")

    def test_furitek_colour_editions(self):
        tail = "ARTR with TRI-UNITY30 Next-Gen FOC Drivetrain - {} Edition"
        a = rel("furitek/fur-2863", "FUR-2863", "KRAWL 30 FULLRANGE TRAIL PRO PICKUP " + tail.format("White"), seen_by="2026-10-26")
        b = rel("furitek/fur-2864", "FUR-2864", "KRAWL 30 FULLRANGE TRAIL PRO PICKUP " + tail.format("Yellow"), seen_by="2026-10-26")
        self.assertEqual(rules.edition_pair(a, b)[0], "edition")
        self.assertEqual(rules.market_bucket(a, b), "together")

    def test_race_liveries_launch_over_a_year(self):
        base = "MINI-Z RWD MR-04 readyset JAGUAR XJR-14 "
        a = rel("kyosho/32369le", "32369LE", base + "No.4 LM 1991", released="2026-02")
        b = rel("kyosho/32369s17", "32369S17", base + "No.17 SUGO 1991", released="2026-12")
        self.assertEqual(rules.edition_pair(a, b)[0], "livery")
        self.assertEqual(rules.market_bucket(a, b), "review")
        self.assertEqual(rules.market_bucket(a, b, rules.LIVERY_MARKET_DAYS), "together")

    def test_other_products_are_no_edition(self):
        for word in ("Limited", "Founder's", "Graphite", "Carpet", "Dirt", "Alu"):
            a = rel("x/1", "X-100", f"Titan U4 {word} Edition ARTR")
            b = rel("x/2", "X-101", "Titan U4 Nebula Edition ARTR")
            self.assertIsNone(rules.edition_pair(a, b), word)

    def test_colour_clause(self):
        a = rel("maverick/150870", "150870", "Microbe Flux 1/24th Buggy - Blue", seen_by="2026-10")
        b = rel("maverick/150871", "150871", "Microbe Flux 1/24th Buggy - Yellow", seen_by="2026-10")
        self.assertEqual(rules.edition_pair(a, b), ("colour", "blue", "yellow"))
        self.assertEqual(rules.market_bucket(a, b), "together")
        # a colour code the site reads from the item number (30615C / 30615R) pairs there without a range
        self.assertIsNone(rules.edition_pair(rel("k/1", "30615C", "Inferno Red"), rel("k/2", "30615R", "Inferno Blue")))
        # not a colour: another product
        self.assertIsNone(rules.edition_pair(rel("x/1", "100", "Buggy RTR Brushless"), rel("x/2", "101", "Buggy RTR")))

    def test_race_number_livery(self):
        a = rel("kyosho/32369s17", "32369S17", "MINI-Z RWD MR-04 readyset Jaguar XJR-14 No.17 SUGO 1991")
        b = rel("kyosho/32369s18", "32369S18", "MINI-Z RWD MR-04 readyset Jaguar XJR-14 No.18 SUGO 1991")
        self.assertEqual(rules.edition_pair(a, b)[0], "livery")

    def test_tamiya_reissue_editions_stay_apart(self):
        black = rel("tamiya/47432", "47432", "Super Clod Buster Black Edition", released="2020-05")
        chrome = rel("tamiya/58423", "58423", "Super Clod Buster Chrome Edition", released="2008-12-20")
        gray = rel("tamiya/92437", "92437", "Super Clod Buster Gray Edition", seen_by="2022-03")
        for a, b in ((black, chrome), (black, gray), (chrome, gray)):
            self.assertIsNone(rules.edition_pair(a, b))   # item numbers far apart
            self.assertNotEqual(rules.market_bucket(a, b), "together")   # years apart
        red = rel("tamiya/47402", "47402", 'Customized Monster Van for Racing & Show Lunch Box "Red Edition" (CW-01)',
                  released="2019-06-15")
        gold = rel("tamiya/49459", "49459", 'Customized Monster Van for Racing & Show Lunch Box "Gold Edition" (CW-01)',
                   released="2011-09-17")
        self.assertIsNone(rules.edition_pair(red, gold))
        self.assertNotEqual(rules.market_bucket(red, gold), "together")

    def test_reissue_markers_keep_apart(self):
        javelin = rel("kyosho/30618", "30618", "Javelin re-release kit", announced="2017-08-28")
        legendary = rel("kyosho/30618c", "30618C", "Legendary Series Javelin", released="2024-05")
        self.assertEqual(rules.market_bucket(javelin, legendary), "apart")
        clod = rel("tamiya/58065", "58065", "Clod Buster", released="1987-09-21")
        self.assertEqual(rules.market_bucket(clod, rel("tamiya/58762", "58762", "Clod Buster (2026)", released="2026-09-19")),
                         "apart")
        original = rel("tamiya/58410", "58410", "Golf GTI", released="2009-03")
        again = rel("tamiya/84060", "84060", "Golf GTI, red", released="2009-03",
                    related=[{"release": "release/tamiya/58410", "relation": "rerelease-of"}])
        self.assertEqual(rules.market_bucket(original, again), "apart")

    def test_far_apart_or_undated_is_a_review(self):
        a = rel("blackzon/1", "540230", "Slyder ST - Red", seen_by="2023-12")
        self.assertEqual(rules.market_bucket(a, rel("blackzon/2", "540231", "Slyder ST - Blue", seen_by="2024-05")), "review")
        self.assertEqual(rules.market_bucket(rel("x/1", "1", "A B red"), rel("x/2", "2", "A B blue")), "review")
        # a year alone does not show a launch together
        self.assertEqual(rules.market_bucket(rel("x/1", "1", "A B red", year=2024), rel("x/2", "2", "A B blue", year=2024)),
                         "review")



class FitsScale(unittest.TestCase):
    """fits-scale-contradicts-kit: the scale a listing states for the car of a fits row."""

    def test_listed_scales(self):
        self.assertEqual(rules.listed_scales("RPM Front A-arm Set For 1:16 Slash"), {"1/16"})
        self.assertEqual(rules.listed_scales("Rockslide 1/8th"), {"1/8"})
        self.assertEqual(rules.listed_scales('1/8" bearing, 1/8 in shaft, 5/16 nut'), set())

    def test_every_item_must_state_another_scale(self):
        self.assertTrue(rules.item_scales_contradict("1/18 Ruckus 4WD", "1/10"))
        self.assertFalse(rules.item_scales_contradict("1/10 Ruckus 4WD", "1/10"))
        self.assertFalse(rules.item_scales_contradict("1/18 4WD Temper, 1.9 Barrage Kit/RTR", "1/12"))   # Barrage: no scale
        self.assertFalse(rules.item_scales_contradict("Ruckus 4WD", "1/10"))
        self.assertFalse(rules.item_scales_contradict("1/18 Ruckus 4WD", ""))

    def test_a_scale_before_the_name_of_a_kit_with_none(self):
        self.assertEqual(rules.scaled_name_scales("1/16 Mini Slash", "Mini Slash", "Traxxas"), {"1/16"})
        self.assertEqual(rules.scaled_name_scales("For 1:16 scale Traxxas Mini Slash", "Mini Slash", "Traxxas"), {"1/16"})
        self.assertEqual(rules.scaled_name_scales("Mini Slash 4X4", "Mini Slash", "Traxxas"), set())
        self.assertEqual(rules.scaled_name_scales("1/16 Mini Slash", "Slash", "Traxxas"), set())   # "Mini" is not the brand
        self.assertEqual(rules.kit_words("1/16 Slash 4X4"), {"slash"})
        self.assertLessEqual(rules.kit_words("1/16 Slash 4X4"), rules.kit_words("Mini Slash"))

if __name__ == "__main__":
    unittest.main()
