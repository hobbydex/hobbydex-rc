"""python3 -I -m unittest discover -s tools -p test_export.py (from the repository root)"""
import os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export


class LastCommitDates(unittest.TestCase):
    def git(self, *args, when="2026-01-01T12:00:00+00:00"):
        env = dict(os.environ, GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True, env=env)

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def test_dates_follow_content_not_moves(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                self.git("init", "-q")
                body = "id = 'x'\n" + "name = 'a long enough body to be recognised as a rename'\n" * 5
                self.write("data/parts/b/AA/AA1.toml", body)
                self.write("data/parts/b/BB/BB1.toml", body + "n = 1\n")
                self.git("add", "-A"); self.git("commit", "-qm", "a", when="2026-01-01T12:00:00+00:00")
                self.write("data/parts/b/BB/BB1.toml", body + "n = 2\n")
                self.git("add", "-A"); self.git("commit", "-qm", "b", when="2026-02-01T12:00:00+00:00")
                os.makedirs("data/parts/b/AB")
                self.git("mv", "data/parts/b/AA/AA1.toml", "data/parts/b/AB/AA1.toml")
                self.git("commit", "-qm", "move", when="2026-03-01T23:30:00-05:00")
                got = export.last_commit_dates()
            finally:
                os.chdir(old)
        self.assertEqual(got["data/parts/b/AB/AA1.toml"], "2026-01-01")   # a pure move is no change
        self.assertEqual(got["data/parts/b/BB/BB1.toml"], "2026-02-01")

    def test_content_dates_skip_bookkeeping(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                self.git("init", "-q")
                self.write("data/parts/b/AA/AA1.toml", "id = 'x'\nname = 'Arm'\nfits = [{ kit = 'kit/b/k', type = 'direct' }]\n")
                self.write("data/parts/b/AA/AA2.toml", "id = 'y'\nname = 'Hub'\n")
                self.git("add", "-A"); self.git("commit", "-qm", "a", when="2026-01-01T12:00:00+00:00")
                # bookkeeping only: a seen_by bound, a name_source, a source on a fits row
                self.write("data/parts/b/AA/AA1.toml", "id = 'x'\nname = 'Arm'\nname_source = 'manual'\nseen_by = '2019-03'\n"
                           "seen_by_source = 'https://web.archive.org/web/2019/x'\nfits = [{ kit = 'kit/b/k', type = 'direct', source = 'doc/b/list' }]\n")
                # content: a new name
                self.write("data/parts/b/AA/AA2.toml", "id = 'y'\nname = 'Front hub'\nsources = { name = 'https://maker.example/y' }\n")
                self.git("add", "-A"); self.git("commit", "-qm", "b", when="2026-02-01T12:00:00+00:00")
                dates, changed = export.history()
            finally:
                os.chdir(old)
        self.assertEqual(dates["data/parts/b/AA/AA1.toml"], "2026-02-01")
        self.assertEqual(changed["data/parts/b/AA/AA1.toml"], "2026-01-01")   # nothing shown changed
        self.assertEqual(changed["data/parts/b/AA/AA2.toml"], "2026-02-01")

    def test_content_of_drops_bookkeeping_at_any_depth(self):
        got = export.content_of({"name": "Arm", "pack_qty": 2, "pack_qty_basis": "name", "former_ids": ["part/b/old"],
                                 "contains": [{"part": "part/b/1", "role": "kit", "source": "doc/b/m", "listed_in": ["doc/b/s"]}]})
        self.assertEqual(got, {"name": "Arm", "pack_qty": 2, "contains": [{"part": "part/b/1", "role": "kit"}]})


if __name__ == "__main__":
    unittest.main()
