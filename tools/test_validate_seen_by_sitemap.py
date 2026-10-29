"""python3 -I -m unittest discover -s tools -p test_validate_seen_by_sitemap.py (from the repository root)

A release's seen_by may cite the maker's product sitemap that lists its page (seen_by_source = the sitemap URL on
the brand's site or on one of the release's own links); a sitemap on another host is refused.
"""
import contextlib, io, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

BRAND = 'id = "brand/acme"\nname = "Acme"\nlegal_name = "Acme GmbH"\ncountry = "DE"\nwebsite = "https://acme.example"\nkind = "designer"\nstatus = "active"\n'
KIT = 'id = "kit/acme/k1"\nname = "K1"\nbrand = "brand/acme"\nkind = "kit"\n'


def release(seen_source):
    return ('id = "release/acme/k1"\nkit = "kit/acme/k1"\nbrand = "brand/acme"\nname = "Kit 1"\nkind = "kit"\n'
            'status = "released"\nseen_by = "2023-09-19"\n'
            f'seen_by_source = "{seen_source}"\n'
            'links = [{ site = "Acme", url = "https://acme.example/product/k1/" }]\n')


class SitemapSource(unittest.TestCase):
    def errors_for(self, seen_source):
        tmp = tempfile.mkdtemp(prefix="seen-by-sitemap-")
        self.addCleanup(shutil.rmtree, tmp)
        for rel, text in {"brands/acme.toml": BRAND, "kits/acme/k1.toml": KIT,
                          "releases/acme/k1.toml": release(seen_source)}.items():
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

    def test_brand_sitemap_accepted(self):
        self.assertEqual(self.errors_for("https://acme.example/product-sitemap.xml"), [])

    def test_other_host_sitemap_refused(self):
        self.assertTrue(self.errors_for("https://elsewhere.example/product-sitemap.xml"))

    def test_sitemap_must_be_xml(self):
        self.assertTrue(self.errors_for("https://acme.example/products/"))


if __name__ == "__main__":
    unittest.main()
