"""python3 -I -m unittest discover -s tools -p test_validate_contains_listed_in.py (from the repository root)

A contains row may carry listed_in (the earlier listing a maker manual upgraded to kit): a document of the release, other than the row's source, role kit only.
"""
import contextlib, io, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

BRAND = 'id = "brand/acme"\nname = "Acme"\nlegal_name = "Acme GmbH"\ncountry = "DE"\nwebsite = "https://acme.example"\nkind = "designer"\nstatus = "active"\n'
KIT = 'id = "kit/acme/k1"\nname = "k1"\nbrand = "brand/acme"\ncategory = "crawler"\n'
PART = 'id = "part/acme/p1"\nbrand = "brand/acme"\nnumber = "p1"\nname = "p1"\ndocuments = ["doc/acme/store"]\n'
DOC = lambda n: f'id = "doc/acme/{n}"\nbrand = "brand/acme"\ntitle = "{n}"\nkind = "manual"\nurl = "https://acme.example/{n}"\n'


def release(row, docs='["doc/acme/store", "doc/acme/manual"]'):
    return ('id = "release/acme/r1"\nkit = "kit/acme/k1"\nbrand = "brand/acme"\nname = "r1"\nstatus = "released"\n'
            f'documents = {docs}\ncontains = [\n  {row},\n]\n')


class ListedIn(unittest.TestCase):
    def errors_for(self, row, docs='["doc/acme/store", "doc/acme/manual"]'):
        tmp = tempfile.mkdtemp(prefix="listed-in-")
        self.addCleanup(shutil.rmtree, tmp)
        files = {"brands/acme.toml": BRAND, "kits/acme/k1.toml": KIT, "parts/acme/p1.toml": PART,
                 "documents/acme/store.toml": DOC("store"), "documents/acme/manual.toml": DOC("manual"),
                 "releases/acme/r1.toml": release(row, docs)}
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
        return [l for l in out.getvalue().splitlines() if "listed_in" in l]

    def test_upgraded_row_is_valid(self):
        self.assertEqual(self.errors_for('{ part = "part/acme/p1", role = "kit", source = "doc/acme/manual", listed_in = "doc/acme/store" }'), [])

    def test_only_with_kit(self):
        self.assertTrue(self.errors_for('{ part = "part/acme/p1", role = "listed", source = "doc/acme/manual", listed_in = "doc/acme/store" }'))

    def test_not_the_source(self):
        self.assertTrue(self.errors_for('{ part = "part/acme/p1", role = "kit", source = "doc/acme/manual", listed_in = "doc/acme/manual" }'))

    def test_must_be_a_release_document(self):
        self.assertTrue(self.errors_for('{ part = "part/acme/p1", role = "kit", source = "doc/acme/manual", listed_in = "doc/acme/store" }', '["doc/acme/manual"]'))

    def test_must_exist(self):
        self.assertTrue(self.errors_for('{ part = "part/acme/p1", role = "kit", source = "doc/acme/manual", listed_in = "doc/acme/nope" }'))


if __name__ == "__main__":
    unittest.main()
