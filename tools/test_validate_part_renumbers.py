"""python3 -I -m unittest discover -s tools -p test_validate_part_renumbers.py (from the repository root)

A part's former_numbers is a renumber: the same part under a number the maker no longer uses, with the maker's page
cited; a number another part is sold under, a retired id or the part's own number is refused. A part's supersedes is a
revision: a part of the same brand, cited in sources.supersedes, no cycles (legacy ids are grandfathered).
"""
import contextlib, io, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

BRAND = 'id = "brand/himoto"\nname = "Himoto"\nlegal_name = "Himoto GmbH"\ncountry = "CN"\nwebsite = "https://himoto.example/"\nkind = "designer"\nstatus = "active"\n'
KIT = 'id = "kit/himoto/edc-16"\nname = "EDC 16"\nbrand = "brand/himoto"\ncategory = "crawler"\n'
SRC = "https://himoto.example/manual/hi4192.pdf"


def part(number, extra="", slug=None):
    slug = slug or number
    return (f'id = "part/himoto/{slug}"\nbrand = "brand/himoto"\nnumber = "{number}"\nname = "Part {number}"\n'
            f'category = "suspension"\n{extra}')


class PartRenumbers(unittest.TestCase):
    def errors_for(self, files, legacy=()):
        tmp = tempfile.mkdtemp(prefix="part-renumbers-")
        self.addCleanup(shutil.rmtree, tmp)
        files = {"brands/himoto.toml": BRAND, "kits/himoto/edc-16.toml": KIT, **files}
        for rel, text in files.items():
            path = os.path.join(tmp, "data", rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        if legacy:
            with open(os.path.join(tmp, "data", "legacy-part-supersedes.toml"), "w", encoding="utf-8") as fh:
                fh.write("ids = [" + ", ".join(f'"{x}"' for x in legacy) + "]\n")
        cwd, old_root = os.getcwd(), validate.ROOT
        os.chdir(tmp)
        validate.ROOT = "data"
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                try:
                    validate.main()
                except SystemExit:
                    pass
        finally:
            os.chdir(cwd)
            validate.ROOT = old_root
        self.assertIn("entities:", out.getvalue())
        return [l for l in out.getvalue().splitlines() if "former number" in l or "supersedes" in l or "former_numbers" in l]

    def test_renumber_with_maker_page_is_accepted(self):
        self.assertEqual(self.errors_for({"parts/himoto/282018.toml": part("282018",
            f'former_numbers = ["82909"]\nsources = {{ former_numbers = "{SRC}" }}\n')}), [])

    def test_former_number_without_source_is_refused(self):
        self.assertTrue(self.errors_for({"parts/himoto/282018.toml": part("282018", 'former_numbers = ["82909"]\n')}))

    def test_former_number_equal_to_own_number_is_refused(self):
        self.assertTrue(self.errors_for({"parts/himoto/282018.toml": part("282018",
            f'former_numbers = ["282018"]\nsources = {{ former_numbers = "{SRC}" }}\n')}))

    def test_former_number_in_own_numbers_is_refused(self):
        self.assertTrue(self.errors_for({"parts/himoto/282018.toml": part("282018",
            f'numbers = ["82909"]\nformer_numbers = ["82909"]\nsources = {{ former_numbers = "{SRC}" }}\n')}))

    def test_former_number_that_is_a_live_part_is_refused(self):
        errs = self.errors_for({
            "parts/himoto/282018.toml": part("282018", f'former_numbers = ["82909"]\nsources = {{ former_numbers = "{SRC}" }}\n'),
            "parts/himoto/82909.toml": part("82909")})
        self.assertTrue(any("live number of part/himoto/82909" in e for e in errs))

    def test_former_number_that_is_another_parts_numbers_is_refused(self):
        errs = self.errors_for({
            "parts/himoto/282018.toml": part("282018", f'former_numbers = ["82909"]\nsources = {{ former_numbers = "{SRC}" }}\n'),
            "parts/himoto/820001.toml": part("820001", 'numbers = ["82909"]\n')})
        self.assertTrue(any("live number" in e for e in errs))

    def test_former_number_that_is_retired_is_refused(self):
        tmp_retired = 'retired = [{ id = "part/himoto/82909", reason = "misread" }]\n'
        errs = self.errors_for({
            "parts/himoto/282018.toml": part("282018", f'former_numbers = ["82909"]\nsources = {{ former_numbers = "{SRC}" }}\n'),
            "retired.toml": tmp_retired})
        self.assertTrue(any("retired" in e for e in errs))

    def test_former_number_listed_by_two_parts_is_refused(self):
        src = f'former_numbers = ["82909"]\nsources = {{ former_numbers = "{SRC}" }}\n'
        errs = self.errors_for({"parts/himoto/282018.toml": part("282018", src),
                                "parts/himoto/820001.toml": part("820001", src)})
        self.assertTrue(any("also a former number" in e for e in errs))

    def test_repeated_former_number_is_refused(self):
        self.assertTrue(self.errors_for({"parts/himoto/282018.toml": part("282018",
            f'former_numbers = ["82909", "82909"]\nsources = {{ former_numbers = "{SRC}" }}\n')}))

    def test_revision_with_maker_source_is_accepted(self):
        self.assertEqual(self.errors_for({
            "parts/himoto/820001.toml": part("820001"),
            "parts/himoto/820001V2.toml": part("820001V2", f'supersedes = "part/himoto/820001"\nsources = {{ supersedes = "{SRC}" }}\n')}), [])

    def test_revision_without_source_is_refused(self):
        self.assertTrue(self.errors_for({
            "parts/himoto/820001.toml": part("820001"),
            "parts/himoto/820001V2.toml": part("820001V2", 'supersedes = "part/himoto/820001"\n')}))

    def test_http_source_of_an_http_only_brand_is_accepted(self):
        http_brand = BRAND.replace('website = "https://himoto.example/"', 'website = "http://himoto.example/"')
        self.assertEqual(self.errors_for({"brands/himoto.toml": http_brand,
            "parts/himoto/282018.toml": part("282018", 'former_numbers = ["82909"]\nsources = { former_numbers = "http://himoto.example/manual/hi4192.pdf" }\n')}), [])

    def test_http_source_of_another_host_is_refused(self):
        self.assertTrue(self.errors_for({"parts/himoto/282018.toml": part("282018",
            'former_numbers = ["82909"]\nsources = { former_numbers = "http://elsewhere.example/manual.pdf" }\n')}))

    def test_legacy_supersedes_is_grandfathered(self):
        self.assertEqual(self.errors_for({
            "parts/himoto/820001.toml": part("820001"),
            "parts/himoto/820001V2.toml": part("820001V2", 'supersedes = "part/himoto/820001"\n')},
            legacy=["part/himoto/820001V2"]), [])

    def test_supersedes_to_missing_part_is_refused(self):
        self.assertTrue(self.errors_for({"parts/himoto/820001.toml": part("820001",
            f'supersedes = "part/himoto/999999"\nsources = {{ supersedes = "{SRC}" }}\n')}))

    def test_supersedes_another_brand_is_refused(self):
        other = 'id = "brand/other"\nname = "Other"\nlegal_name = "Other"\ncountry = "DE"\nwebsite = "https://other.example/"\nkind = "designer"\nstatus = "active"\n'
        self.assertTrue(self.errors_for({
            "brands/other.toml": other,
            "parts/other/1.toml": 'id = "part/other/1"\nbrand = "brand/other"\nnumber = "1"\nname = "Other 1"\ncategory = "suspension"\n',
            "parts/himoto/820001.toml": part("820001", f'supersedes = "part/other/1"\nsources = {{ supersedes = "{SRC}" }}\n')}))

    def test_supersedes_itself_is_refused(self):
        self.assertTrue(self.errors_for({"parts/himoto/820001.toml": part("820001",
            f'supersedes = "part/himoto/820001"\nsources = {{ supersedes = "{SRC}" }}\n')}))

    def test_supersedes_cycle_is_refused(self):
        a = part("820001", f'supersedes = "part/himoto/820002"\nsources = {{ supersedes = "{SRC}" }}\n')
        b = part("820002", f'supersedes = "part/himoto/820001"\nsources = {{ supersedes = "{SRC}" }}\n')
        self.assertTrue(any("cycle" in e for e in self.errors_for({"parts/himoto/820001.toml": a, "parts/himoto/820002.toml": b})))


if __name__ == "__main__":
    unittest.main()
