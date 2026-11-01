"""python3 -I -m unittest discover -s tools -p test_validate_seen_by_news.py (from the repository root)

A release's seen_by may cite the brand's own news post (news_info.php?sn=N) as its seen_by_source, at month or day
precision. Another host, another path, or a release with an announced date is refused.
"""
import contextlib, io, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

BRAND = 'id = "brand/acme"\nname = "Acme"\nlegal_name = "Acme GmbH"\ncountry = "DE"\nwebsite = "https://www.acme.example/"\nkind = "designer"\nstatus = "active"\n'
KIT = 'id = "kit/acme/k1"\nname = "K1"\nbrand = "brand/acme"\nkind = "kit"\n'
POST = "https://www.acme.example/news_info.php?sn=296"


def release(seen_source, seen_by="2023-09", extra=""):
    return ('id = "release/acme/k1"\nkit = "kit/acme/k1"\nbrand = "brand/acme"\nnumber = "K1"\nname = "Kit 1"\nkind = "arr"\n'
            f'status = "released"\nseen_by = "{seen_by}"\nseen_by_source = "{seen_source}"\n{extra}'
            'links = [{ site = "Acme", url = "https://www.acme.example/product/k1/" }]\n')


class NewsSeenBy(unittest.TestCase):
    def errors_for(self, seen_source, **kw):
        tmp = tempfile.mkdtemp(prefix="seen-by-news-")
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
        self.assertIn("entities:", out.getvalue())
        return [l for l in out.getvalue().splitlines() if "seen_by" in l]

    def test_brand_news_post_accepted_at_month(self):
        self.assertEqual(self.errors_for(POST), [])

    def test_brand_news_post_accepted_at_day(self):
        self.assertEqual(self.errors_for(POST, seen_by="2023-09-06"), [])

    def test_other_host_refused(self):
        self.assertTrue(self.errors_for("https://www.elsewhere.example/news_info.php?sn=296"))

    def test_other_path_refused(self):
        self.assertTrue(self.errors_for("https://www.acme.example/news.php?sn=296"))

    def test_news_with_announced_refused(self):
        self.assertTrue(self.errors_for(POST, extra='announced = "2023-09-06"\n'))


if __name__ == "__main__":
    unittest.main()
