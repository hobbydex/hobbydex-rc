"""python3 -I -m unittest discover -s tools -p test_validate_hardness.py (from the repository root)

A tyre's hardness is a whole Shore A figure with hardness_source (an https page); other values and other categories are refused.
"""
import contextlib, io, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

BRAND = 'id = "brand/acme"\nname = "Acme"\nlegal_name = "Acme GmbH"\ncountry = "DE"\nwebsite = "https://acme.example"\nkind = "designer"\nstatus = "active"\n'
KIT = 'id = "kit/acme/k1"\nname = "K1"\nbrand = "brand/acme"\nkind = "kit"\n'


def part(extra, category="tire"):
    return ('id = "part/acme/A1"\nname = "Foam Tyre 32Sh"\nbrand = "brand/acme"\nnumber = "A1"\nkind = "part"\n'
            f'category = "{category}"\nlinks = [{{ site = "Acme", url = "https://acme.example/a1" }}]\n' + extra)


class Hardness(unittest.TestCase):
    def errors_for(self, extra, category="tire"):
        tmp = tempfile.mkdtemp(prefix="hardness-")
        self.addCleanup(shutil.rmtree, tmp)
        for rel, text in {"brands/acme.toml": BRAND, "kits/acme/k1.toml": KIT, "parts/acme/A1.toml": part(extra, category)}.items():
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
        return [l for l in out.getvalue().splitlines() if "hardness" in l]

    def test_stated_hardness_accepted(self):
        self.assertEqual(self.errors_for('hardness = 32\nhardness_source = "https://acme.example/a1"\n'), [])

    def test_refused(self):
        self.assertTrue(self.errors_for('hardness = 32\n'))                                              # no source
        self.assertTrue(self.errors_for('hardness = "soft"\nhardness_source = "https://acme.example/a1"\n'))
        self.assertTrue(self.errors_for('hardness = 250\nhardness_source = "https://acme.example/a1"\n'))
        self.assertTrue(self.errors_for('hardness = 32\nhardness_source = "https://acme.example/a1"\n', "misc"))


if __name__ == "__main__":
    unittest.main()
