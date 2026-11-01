"""python3 -I -m unittest discover -s tools -p test_validate_pack_qty_basis.py (from the repository root)

A part's pack_qty_basis may be "distributor" (a dealer's listing states the count); an unknown basis is refused.
"""
import contextlib, io, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

BRAND = 'id = "brand/acme"\nname = "Acme"\nlegal_name = "Acme GmbH"\ncountry = "DE"\nwebsite = "https://acme.example"\nkind = "designer"\nstatus = "active"\n'
KIT = 'id = "kit/acme/k1"\nname = "K1"\nbrand = "brand/acme"\nkind = "kit"\n'


def part(basis):
    return ('id = "part/acme/A1"\nname = "Ball Stud"\nbrand = "brand/acme"\nnumber = "A1"\nkind = "part"\n'
            'category = "misc"\nlinks = [{ site = "RC Race Shop", url = "https://shop.example/a1", kind = "dealer" }]\n'
            f'pack_qty = 4\npack_qty_basis = "{basis}"\n')


class PackQtyBasis(unittest.TestCase):
    def errors_for(self, basis):
        tmp = tempfile.mkdtemp(prefix="pack-qty-basis-")
        self.addCleanup(shutil.rmtree, tmp)
        for rel, text in {"brands/acme.toml": BRAND, "kits/acme/k1.toml": KIT, "parts/acme/A1.toml": part(basis)}.items():
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
        return [l for l in out.getvalue().splitlines() if "pack_qty_basis" in l]

    def test_distributor_accepted(self):
        self.assertEqual(self.errors_for("distributor"), [])

    def test_unknown_basis_refused(self):
        errs = self.errors_for("reseller")
        self.assertTrue(errs, "an unknown pack_qty_basis must be refused")


if __name__ == "__main__":
    unittest.main()
