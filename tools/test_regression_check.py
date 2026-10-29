"""python3 -I -m unittest discover -s tools -p test_regression_check.py (from the repository root)"""
import os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regression_check as rc


class Repointed(unittest.TestCase):
    old = {"part": "part/arrma/ARA330200", "role": "listed", "source": "doc/arrma/ara8406-manual"}

    def test_superseding_part_in_same_release_is_a_repoint(self):
        rows = [{"part": "part/arrma/ARAC9074", "role": "listed", "source": "doc/arrma/ara8406-manual"}]
        self.assertEqual(rc.repointed(self.old, rows, {"part/arrma/ARA330200": "part/arrma/ARAC9074"}), "part/arrma/ARAC9074")

    def test_no_supersedes_is_a_removal(self):
        rows = [{"part": "part/arrma/ARAC9074", "role": "listed", "source": "doc/arrma/ara8406-manual"}]
        self.assertIsNone(rc.repointed(self.old, rows, {}))

    def test_superseding_part_without_row_is_a_removal(self):
        self.assertIsNone(rc.repointed(self.old, [], {"part/arrma/ARA330200": "part/arrma/ARAC9074"}))

    def test_other_role_or_source_is_a_removal(self):
        rows = [{"part": "part/arrma/ARAC9074", "role": "kit", "source": "doc/arrma/ara8406-manual"}]
        self.assertIsNone(rc.repointed(self.old, rows, {"part/arrma/ARA330200": "part/arrma/ARAC9074"}))


class SeenBy(unittest.TestCase):
    """seen_by is the first day the maker had an item on its pages: an earlier capture lowers it (no loss), a later date does not."""

    def events(self, old, new):
        ck = rc.Check("a", "b")
        ck.compare("release", "release/x/1", {"id": "release/x/1", "seen_by": old, "seen_by_source": "https://x.test/p"},
                   {"id": "release/x/1", "seen_by": new, "seen_by_source": "https://web.archive.org/web/2020/https://x.test/p"})
        return [e for e in ck.events if e["field"] == "seen_by"]

    def test_earlier_first_sighting_is_not_a_regression(self):
        for old, new in (("2023-03", "2023-02"), ("2019-07-07", "2019-05"), ("2026-10", "2022-04-18")):
            ev = self.events(old, new)
            self.assertEqual([e["regression"] for e in ev], [False], (old, new))

    def test_later_date_is_a_regression(self):
        self.assertEqual([e["regression"] for e in self.events("2023-03", "2024-09")], [True])


def upgrade_fixture():
    parts = {
        "part/a/S1": {"id": "part/a/S1", "brand": "brand/a", "name": "Wheel Hex Adapter", "category": "suspension", "material": "plastic"},
        "part/a/X1": {"id": "part/a/X1", "brand": "brand/a", "name": "Wheel Hex Adapter - Alu.", "category": "suspension", "material": "aluminium"},
    }
    releases = [{"kit": "kit/a/k", "contains": [{"part": "part/a/S1", "role": "kit", "source": "doc/a/m"},
                                                {"part": "part/a/X1", "role": "option", "source": "doc/a/m"}]}]
    return parts, releases


class Derived(unittest.TestCase):
    def test_upgrade_of_a_stock_part_is_derived(self):
        parts, releases = upgrade_fixture()
        row = dict(kit="kit/a/k", type="replaces", replaces="part/a/S1", source="doc/a/m", notes=rc.LINK_NOTE)
        self.assertIn(rc.canon(row), rc.derive_upgrades(parts, releases)["part/a/X1"])

    def test_no_stock_part_in_the_kit_is_no_upgrade(self):
        parts, releases = upgrade_fixture()
        releases[0]["contains"] = [c for c in releases[0]["contains"] if c["role"] != "kit"]
        self.assertEqual(rc.derive_upgrades(parts, releases), {})

    def test_material_must_be_an_upgrade(self):
        parts, releases = upgrade_fixture()
        parts["part/a/S1"]["material"] = "aluminium"
        self.assertEqual(rc.derive_upgrades(parts, releases), {})

    def test_gained_only(self):
        self.assertTrue(rc.gained_only({"k": 1, "releases": ["a"]}, {"k": 1, "releases": ["a", "b"]}))
        self.assertFalse(rc.gained_only({"k": 1, "releases": ["a"]}, {"k": 2, "releases": ["a", "b"]}))
        self.assertFalse(rc.gained_only({"k": 1, "releases": ["a", "b"]}, {"k": 1, "releases": ["a"]}))


class FormerNames(unittest.TestCase):
    def test_former_name_equal_to_the_current_name_is_dropped(self):
        o = {"name": "C-Hubs: 4x4 BLX 4S", "brand": "brand/arrma", "former_names": ["C-Hubs"]}
        n = {"name": "C-Hubs", "brand": "brand/arrma"}
        self.assertEqual(rc.canonical_removal(o, n, "former_names", "C-Hubs"), "former name is the current name")

    def test_listing_line_is_dropped(self):
        o = {"name": "Shock Shaft 4x59.5mm", "brand": "brand/arrma", "former_names": ["Shock Shaft 4x59.5mm (2)"]}
        n = {"name": "Shock Shaft 4x61mm", "brand": "brand/arrma"}
        self.assertEqual(rc.canonical_removal(o, n, "former_names", "Shock Shaft 4x59.5mm (2)"), "listing line, never a former name")

    def test_former_name_that_is_not_the_current_name_is_a_loss(self):
        o = {"name": "Gear 48P 36T", "brand": "brand/a", "former_names": ["Gear 32P 40T"]}
        n = {"name": "Gear 48P 36T 3mm", "brand": "brand/a"}
        self.assertIsNone(rc.canonical_removal(o, n, "former_names", "Gear 32P 40T"))


class Repository(unittest.TestCase):
    """Check() on two commits of a small data tree: a derived fits row is explained only when the head no longer
    derives it."""

    NOTE = rc.LINK_NOTE

    def commit(self, root, files, message):
        subprocess.run(["git", "-C", root, "rm", "-rq", "--ignore-unmatch", "data"], check=True)
        for path, text in files.items():
            full = os.path.join(root, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(text)
        subprocess.run(["git", "-C", root, "add", "-A", "data"], check=True)
        subprocess.run(["git", "-C", root, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", message], check=True)
        return subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    def files(self, stock_name, derived_row):
        fits = f"fits = [ {derived_row} ]\n" if derived_row else ""
        return {
            "data/parts/a/S1.toml": 'id = "part/a/S1"\nbrand = "brand/a"\nname = "%s"\ncategory = "suspension"\nmaterial = "plastic"\n' % stock_name,
            "data/parts/a/X1.toml": 'id = "part/a/X1"\nbrand = "brand/a"\nname = "Wheel Hex Adapter - Alu."\ncategory = "suspension"\nmaterial = "aluminium"\n' + fits,
            "data/releases/a/k.toml": 'kit = "kit/a/k"\nname = "Kit"\ncontains = [\n'
                                      '  { part = "part/a/S1", role = "kit", source = "doc/a/m" },\n'
                                      '  { part = "part/a/X1", role = "option", source = "doc/a/m" },\n]\n',
        }

    def check(self, base_files, head_files):
        root = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            subprocess.run(["git", "-C", root, "init", "-q"], check=True)
            os.chdir(root)
            base = self.commit(root, base_files, "base")
            head = self.commit(root, head_files, "head")
            return rc.Check(base, head).run()
        finally:
            os.chdir(cwd)
            shutil.rmtree(root, ignore_errors=True)

    def test_derived_row_the_head_still_derives_is_a_regression(self):
        row = f'{{ kit = "kit/a/k", type = "replaces", replaces = "part/a/S1", source = "doc/a/m", notes = "{self.NOTE}" }}'
        ck = self.check(self.files("Wheel Hex Adapter", row), self.files("Wheel Hex Adapter", None))
        regs = [e for e in ck.events if e["regression"]]
        self.assertEqual([e["field"] for e in regs], ["fits"])

    def test_derived_row_the_head_does_not_derive_is_explained(self):
        row = f'{{ kit = "kit/a/k", type = "replaces", replaces = "part/a/S1", source = "doc/a/m", notes = "{self.NOTE}" }}'
        ck = self.check(self.files("Wheel Hex Adapter", row), self.files("Wheel Hex Adapter Set", None))
        self.assertEqual([e for e in ck.events if e["regression"]], [])
        self.assertTrue(any(e["field"] == "fits" and "not derived" in e["reason"] for e in ck.events))



class Removals(unittest.TestCase):
    """A removed or changed list row or string field of a part counts when the source stated it."""

    commit, check = Repository.commit, Repository.check

    MAKER = 'https://maker.example/p/1'
    DEALER = 'https://shop.example/cat/1'

    def part(self, extra):
        return {"data/parts/a/P1.toml": 'id = "part/a/P1"\nbrand = "brand/a"\nname = "Wing Mount"\n'
                                        'category = "suspension"\nmaterial = "plastic"\n' + extra,
                "data/releases/a/k.toml": 'kit = "kit/a/k"\nname = "Kit"\ncontains = [\n'
                                          '  { part = "part/a/P1", role = "kit", source = "doc/a/m" },\n]\n'}

    def regs(self, ck):
        return [(e["field"], e["reason"]) for e in ck.events if e["regression"]]

    def test_note_with_text_added_is_not_a_regression(self):
        base = self.part('notes = "The shop lists it as P-1"\n')
        head = self.part('notes = "The shop lists it as P-1. Colour read from the maker\'s product photo."\n')
        self.assertEqual(self.regs(self.check(base, head)), [])

    def test_rewritten_note_is_a_regression(self):
        base = self.part('notes = "The shop lists it as P-1"\n')
        head = self.part('notes = "Colour read from the maker\'s product photo."\n')
        self.assertEqual([f for f, _ in self.regs(self.check(base, head))], ["notes"])

    def test_removed_maker_link_is_a_regression(self):
        base = self.part('links = [ { url = "%s" } ]\n' % self.MAKER)
        head = self.part('links = []\n')
        self.assertEqual(self.regs(self.check(base, head)), [("links", "stated link removed")])

    def test_dealer_link_dropped_beside_a_maker_link_is_a_regression(self):
        base = self.part('links = [ { url = "%s", kind = "dealer", site = "shop" } ]\n' % self.DEALER)
        head = self.part('links = [ { url = "%s" } ]\n' % self.MAKER)
        self.assertEqual([f for f, _ in self.regs(self.check(base, head))], ["links"])

    def test_link_whose_page_is_gone_is_not_a_regression(self):
        base = self.part('links = [ { url = "%s" }, { url = "%s" } ]\n' % (self.MAKER, self.DEALER))
        head = self.part('links = [ { url = "%s" } ]\n' % self.MAKER)
        head["data/documents/shop/gone.toml"] = 'id = "doc/shop/gone"\npage = "%s"\ngone = "2026-10-20"\n' % self.DEALER
        self.assertEqual(self.regs(self.check(base, head)), [])

    def test_link_whose_page_is_a_document_of_the_record_is_not_a_regression(self):
        base = self.part('links = [ { url = "%s" } ]\n' % self.MAKER)
        head = self.part('links = []\ndocuments = [ "doc/a/m" ]\n')
        head["data/documents/a/m.toml"] = 'id = "doc/a/m"\npage = "%s"\n' % self.MAKER
        self.assertEqual(self.regs(self.check(base, head)), [])

    def test_removed_applies_to_is_a_regression(self):
        base = self.part('applies_to = "ARRMA Granite"\n')
        head = self.part('')
        self.assertEqual([f for f, _ in self.regs(self.check(base, head))], ["applies_to"])

    def test_changed_applies_to_is_a_regression(self):
        base = self.part('applies_to = "ARRMA Granite"\n')
        head = self.part('applies_to = "ARRMA Senton"\n')
        self.assertEqual([f for f, _ in self.regs(self.check(base, head))], ["applies_to"])

    def test_removed_sourced_equivalent_to_row_is_a_regression(self):
        row = '{ spec = "spec/screw/m3", match = "functional", source = "doc/a/m" }'
        base = self.part('equivalent_to = [ %s ]\n' % row)
        head = self.part('')
        self.assertEqual([f for f, _ in self.regs(self.check(base, head))], ["equivalent_to"])

    def test_removed_fits_row_is_a_regression(self):
        row = '{ kit = "kit/a/k", type = "fits", source = "doc/a/m" }'
        base = self.part('fits = [ %s ]\n' % row)
        head = self.part('')
        self.assertEqual([f for f, _ in self.regs(self.check(base, head))], ["fits"])


if __name__ == "__main__":
    unittest.main()
