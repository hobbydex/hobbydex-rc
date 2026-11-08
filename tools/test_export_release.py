"""python3 -I tools/test_export_release.py (from the repository root)

Builds a tiny data tree in a temporary git repository (no file of the real data is read)
and runs tools/export_release.py on it.
"""
import csv, hashlib, json, os, sqlite3, subprocess, sys, tempfile, unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(TOOLS, "export_release.py")
DATE = "2026-01-01T12:00:00+00:00"

BRAND = 'id = "brand/x"\nname = "X Racing"\nstatus = "active"\n'
KIT = 'id = "kit/x/k1"\nbrand = "brand/x"\nname = "K1"\ncategory = "car"\nsurface = ["asphalt", "dirt"]\n'
PART_X1 = 'id = "part/x/X1"\nbrand = "brand/x"\nname = "Shock"\n'
PART_X2 = ('id = "part/x/X2"\nbrand = "brand/x"\nname = "Spring"\n'
           'fits = [{ kit = "kit/x/k1", releases = ["release/x/r1", "release/x/r2"], type = "direct", source = "doc/x/store" }]\n')
RETIRED = '[[retired]]\nid = "part/x/OLD"\nreason = "not a part"\n'


class ExportRelease(unittest.TestCase):
    def git(self, *args, when=DATE):
        env = dict(os.environ, GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       check=True, capture_output=True, env=env)

    def write(self, path, text):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def read(self, out, name):
        with open(os.path.join(out, name), encoding="utf-8") as f:
            return f.read()

    def csv_rows(self, out, name):
        with open(os.path.join(out, name), encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def run_export(self, version, out):
        subprocess.run([sys.executable, "-I", SCRIPT, out, "--version", version],
                       check=True, capture_output=True, cwd=self.repo)

    def make_repo(self, tag):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", self.repo]))
        os.chdir(self.repo)
        self.git("init", "-q")
        self.write("data/brands/x.toml", BRAND)
        self.write("data/kits/x/k1.toml", KIT)
        self.write("data/parts/x/X1.toml", PART_X1)
        self.write("data/parts/x/old/OLD.toml", 'id = "part/x/old"\nbrand = "brand/x"\nname = "Gone"\n')
        self.write("data/retired.toml", RETIRED)
        self.git("add", "-A"); self.git("commit", "-qm", "first")
        if tag:
            self.git("tag", tag)
        return self

    def test_release_files_and_changes(self):
        old = os.getcwd()
        self.addCleanup(os.chdir, old)
        self.make_repo("v2026.10.0")
        # second commit: a changed brand, a changed part, an added part, a removed kit, a moved part
        self.write("data/brands/x.toml", BRAND + 'notes = "changed"\n')
        self.write("data/parts/x/X1.toml", PART_X1.replace("Shock", "Shock absorber"))
        self.write("data/parts/x/X2.toml", PART_X2)
        os.remove("data/kits/x/k1.toml")
        os.makedirs("data/parts/x/moved")
        os.rename("data/parts/x/old/OLD.toml", "data/parts/x/moved/OLD.toml")
        self.git("add", "-A"); self.git("commit", "-qm", "second", when="2026-02-01T12:00:00+00:00")
        out = os.path.join(self.repo, "release")
        self.run_export("2026.11.0", out)

        changes = self.read(out, "CHANGES.md")
        self.assertIn("Changes since v2026.10.0", changes)
        self.assertIn("| brands | 0 | 0 | 1 |", changes)
        self.assertIn("| kits | 0 | 1 | 0 |", changes)
        self.assertIn("| parts | 1 | 0 | 1 |", changes)   # X2 added, X1 changed; the moved part keeps its id and counts 0
        manifest = json.loads(self.read(out, "manifest.json"))
        self.assertEqual(manifest["version"], "2026.11.0")
        self.assertEqual(manifest["previous"], "v2026.10.0")
        self.assertEqual(manifest["licence"], "CC-BY-4.0")
        self.assertEqual(manifest["counts"]["parts"], 3)
        self.assertEqual(manifest["counts"]["retired"], 1)
        self.assertEqual(manifest["per_brand"]["brand/x"]["parts"], 3)
        self.assertEqual(manifest["fits"], 2)
        for name, meta in manifest["files"].items():
            with open(os.path.join(out, name), "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), meta["sha256"], name)
        self.assertNotIn("manifest.json", manifest["files"])

        doc = json.loads(self.read(out, "hobbydex.json"))
        min_doc = json.loads(self.read(out, "hobbydex.min.json"))
        self.assertEqual(doc["parts"], min_doc["parts"])
        self.assertEqual([p["id"] for p in doc["parts"]], ["part/x/X1", "part/x/X2", "part/x/old"])

        self.assertEqual(self.csv_rows(out, "kits.csv"), [])   # the kit was removed
        self.assertEqual(self.csv_rows(out, "brands.csv")[0]["notes"], "changed")
        x2 = [r for r in self.csv_rows(out, "parts.csv") if r["id"] == "part/x/X2"][0]
        self.assertTrue(x2["fits"].startswith('[{"kit"'))   # nested table as JSON text

        con = sqlite3.connect(os.path.join(out, "hobbydex.sqlite"))
        try:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM "parts"').fetchone()[0], 3)
            self.assertEqual(con.execute("SELECT kit_or_release FROM fits ORDER BY kit_or_release").fetchall(),
                             [("release/x/r1",), ("release/x/r2",)])
            self.assertEqual(con.execute('SELECT COUNT(*) FROM "kits"').fetchone()[0], 0)   # kit removed
        finally:
            con.close()

        self.assertIn("Creative Commons Attribution 4.0", self.read(out, "ATTRIBUTION.md"))
        att = self.read(out, "ATTRIBUTION.md")
        self.assertIn("Somatik BV", att)
        self.assertIn("modified", att)
        self.assertNotIn("CC0", att)

    def test_first_release_without_a_tag(self):
        old = os.getcwd()
        self.addCleanup(os.chdir, old)
        self.make_repo(None)
        out = os.path.join(self.repo, "release")
        self.run_export("2026.11.0", out)
        self.assertEqual(self.read(out, "CHANGES.md"), "first release\n")
        manifest = json.loads(self.read(out, "manifest.json"))
        self.assertIsNone(manifest["previous"])
        self.assertEqual(self.csv_rows(out, "kits.csv")[0]["surface"], "asphalt|dirt")   # list of plain values joined with |


if __name__ == "__main__":
    unittest.main()
