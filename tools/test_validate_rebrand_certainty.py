"""python3 -I -m unittest discover -s tools -p test_validate_rebrand_certainty.py (from the repository root)

A rebrand_of row may carry certainty = "likely" (absent = confirmed); any other value is refused. A release may carry a rebrand_of row naming a release.
"""
import contextlib, io, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

BRAND = 'id = "brand/acme"\nname = "Acme"\nlegal_name = "Acme GmbH"\ncountry = "DE"\nwebsite = "https://acme.example"\nkind = "designer"\nstatus = "active"\n'


def kit(slug, extra=""):
    return f'id = "kit/acme/{slug}"\nname = "{slug}"\nbrand = "brand/acme"\ncategory = "crawler"\n{extra}'


def release(slug, extra=""):
    return f'id = "release/acme/{slug}"\nkit = "kit/acme/k1"\nbrand = "brand/acme"\nname = "{slug}"\nstatus = "released"\n{extra}'


class RebrandCertainty(unittest.TestCase):
    def errors_for(self, files):
        tmp = tempfile.mkdtemp(prefix="rebrand-certainty-")
        self.addCleanup(shutil.rmtree, tmp)
        files = {"brands/acme.toml": BRAND, "kits/acme/k1.toml": kit("k1"), **files}
        for rel, text in files.items():
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
        return out.getvalue()

    def kit_row(self, certainty):
        return {"kits/acme/k2.toml": kit("k2", f'rebrand_of = [{{ kit = "kit/acme/k1", {certainty}notes = "spec match" }}]\n')}

    def test_likely_accepted(self):
        self.assertNotIn("certainty", self.errors_for(self.kit_row('certainty = "likely", ')))

    def test_absent_accepted(self):
        self.assertNotIn("certainty", self.errors_for(self.kit_row("")))

    def test_other_value_refused(self):
        self.assertIn("rebrand_of.certainty", self.errors_for(self.kit_row('certainty = "maybe", ')))

    def test_release_row_needs_existing_release(self):
        files = {"releases/acme/r1.toml": release("r1"),
                 "releases/acme/r2.toml": release("r2", 'rebrand_of = [{ release = "release/acme/nope", certainty = "likely", notes = "x" }]\n')}
        self.assertIn("release/acme/nope does not exist", self.errors_for(files))
        files["releases/acme/r2.toml"] = release("r2", 'rebrand_of = [{ release = "release/acme/r1", certainty = "likely", notes = "x" }]\n')
        self.assertNotIn("rebrand_of", self.errors_for(files))


if __name__ == "__main__":
    unittest.main()
