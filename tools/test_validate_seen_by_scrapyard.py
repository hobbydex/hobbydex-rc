"""python3 -I -m unittest discover -s tools -p test_validate_seen_by_scrapyard.py (from the repository root)

A release's year seen_by may cite the RC Scrapyard model page it lists as a fan-site link; month precision or an unlinked page is refused.
"""
import contextlib, io, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

BRAND = 'id = "brand/acme"\nname = "Acme"\nlegal_name = "Acme GmbH"\ncountry = "DE"\nwebsite = "https://acme.example"\nkind = "designer"\nstatus = "active"\n'
KIT = 'id = "kit/acme/k1"\nname = "K1"\nbrand = "brand/acme"\nkind = "kit"\n'


PAGE = "https://www.rcscrapyard.net/acme-k1.htm"


def release(seen_source, seen_by="2007", link=True):
    extra = f', {{ site = "RC Scrapyard", url = "{PAGE}", kind = "fan-site" }}' if link else ""
    return ('id = "release/acme/k1"\nkit = "kit/acme/k1"\nbrand = "brand/acme"\nname = "Kit 1"\nkind = "kit"\n'
            f'status = "released"\nseen_by = "{seen_by}"\n'
            f'seen_by_source = "{seen_source}"\n'
            f'links = [{{ site = "Acme", url = "https://acme.example/product/k1/" }}{extra}]\n')


class ScrapyardYear(unittest.TestCase):
    def errors_for(self, seen_source, **kw):
        tmp = tempfile.mkdtemp(prefix="seen-by-sitemap-")
        self.addCleanup(shutil.rmtree, tmp)
        for rel, text in {"brands/acme.toml": BRAND, "kits/acme/k1.toml": KIT,
                          "releases/acme/k1.toml": release(seen_source, **kw)}.items():
            path = os.path.join(tmp, "data", rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
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
        self.assertIn("entities:", out.getvalue())   # the validator ran over the temporary data
        return [l for l in out.getvalue().splitlines() if "seen_by_source" in l]

    def test_year_from_the_linked_page_accepted(self):
        self.assertEqual(self.errors_for(PAGE), [])

    def test_page_must_be_linked(self):
        self.assertTrue(self.errors_for(PAGE, link=False))

    def test_month_precision_refused(self):
        self.assertTrue(self.errors_for(PAGE, seen_by="2007-05"))


if __name__ == "__main__":
    unittest.main()
