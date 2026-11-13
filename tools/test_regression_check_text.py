"""tools/regression_check.py on free-text values: a changed stated note, name or fit/link note is a regression.

Each case builds a base and a head commit in a temp repo (raw commit objects with a fixed author, so the test never
reads or changes the git identity of the machine) and runs the check on them. Self-contained: no cache, no checkout.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "regression_check.py"
WHEN = "1700000000 +0000"
PART = "data/parts/jconcepts/24/2457.toml"
NOTE_BASE = "Shown by number only in the manual; Named on the maker's own product page (archived copy)"
READ_FAILED = ("Named by its number only: the name on the scanned acme manual page was not clear enough to take")


def git(repo, *args, stdin="", env=None):
    full_env = dict(os.environ, **(env or {}))
    result = subprocess.run(["git", *args], cwd=repo, input=stdin, capture_output=True, text=True, check=True,
                            env=full_env)
    return result.stdout.strip()


def commit(repo, files, parent=None):
    """A commit whose tree holds exactly files (path -> text); built in a private index file."""
    index = os.path.join(repo, ".test-index")
    env = {"GIT_INDEX_FILE": index}
    if os.path.exists(index):
        os.remove(index)
    for path, text in files.items():
        blob = git(repo, "hash-object", "-w", "--stdin", stdin=text)
        git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=env)
    tree = git(repo, "write-tree", env=env)
    os.remove(index)
    lines = [f"tree {tree}"] + ([f"parent {parent}"] if parent else [])
    who = "Fixture <fixture@example.com>"
    lines += [f"author {who} {WHEN}", f"committer {who} {WHEN}", "", "change"]
    return git(repo, "hash-object", "-t", "commit", "-w", "--stdin", stdin="\n".join(lines) + "\n")


def part(notes=NOTE_BASE, name="Hex Driver Wrench Set w/ Storage Base - 7pc", extra="", name_source="manufacturer"):
    text = (
        'id = "part/jconcepts/2457"\n'
        'brand = "brand/jconcepts"\n'
        'number = "2457"\n'
        f'name = "{name}"\n'
        + (f'name_source = "{name_source}"\n' if name_source else "") +
        'category = "tool"\n'
        'seen_by = "2022-06-25"\n'
        'documents = ["doc/jconcepts/REACTOR_Instruction_Manual-V4_2"]\n'
        'links = [ { site = "JConcepts", url = "https://jconcepts.net/hex-driver-wrench-set" } ]\n'
    )
    if notes is not None:
        text += f'notes = "{notes}"\n'
    return text + extra


def run_check(repo, base_text, head_text):
    """The regressions the check reports for a change of PART from base_text to head_text."""
    root = commit(repo, {PART: base_text})
    head = commit(repo, {PART: head_text}, parent=root)
    git(repo, "update-ref", "refs/heads/base", root)
    git(repo, "update-ref", "refs/heads/head", head)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "result.json")
        subprocess.run([sys.executable, "-I", str(SCRIPT), "--base", "base", "--head", "head", "--json", out],
                       cwd=repo, capture_output=True, text=True)
        with open(out, encoding="utf-8") as f:
            return json.load(f)["regressions"]


class FreeTextRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = cls.tmp.name
        git(cls.repo, "init", "-q")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def assertRegression(self, base_text, head_text):
        regs = run_check(self.repo, base_text, head_text)
        self.assertTrue(regs, "the change loses or changes a stated value: it must be a regression")

    def assertNoRegression(self, base_text, head_text):
        regs = run_check(self.repo, base_text, head_text)
        self.assertEqual(regs, [], f"expected no regression, got {regs}")

    # notes on the part record
    def test_notes_prefix_dropped_is_a_regression(self):
        # the jconcepts/2457 case: the placeholder prefix went, the stated text after it stayed
        self.assertRegression(part(NOTE_BASE), part("Named on the maker's own product page (archived copy)"))

    def test_notes_shortened_is_a_regression(self):
        self.assertRegression(part(NOTE_BASE), part("Shown by number only in the manual"))

    def test_notes_text_changed_in_the_middle_is_a_regression(self):
        self.assertRegression(part("Source A says 7pc; checked"), part("Source A says 8pc; checked"))

    def test_notes_removed_is_a_regression(self):
        self.assertRegression(part(NOTE_BASE), part(None))

    def test_notes_text_added_is_allowed(self):
        self.assertNoRegression(part("Shown by number only in the manual"),
                                part("Shown by number only in the manual; Named on the maker's page"))

    def test_notes_text_added_in_front_is_allowed(self):
        # the restore of a dropped clause: the whole stored note stays, the clause comes before it
        self.assertNoRegression(part("name from the distributor. Colour read from the maker's product photo."),
                                part("Shown by number only in the manual's parts drawings; name from the distributor. "
                                     "Colour read from the maker's product photo."))

    def test_shown_by_number_clause_removed_is_a_regression(self):
        # "Shown by number only in the manual" is what the manual states, not an importer placeholder
        self.assertRegression(part("Shown by number only in the manual"), part(None))
        self.assertRegression(part("Shown by number only in the manual"), part("Named on the maker's page"))

    def test_name_source_claim_after_shown_by_number_is_protected(self):
        self.assertRegression(part("Shown by number only in the manual's parts drawings; name from the maker's manual."),
                              part(None))

    def test_read_failed_note_replaced_is_allowed(self):
        self.assertNoRegression(part(READ_FAILED), part("Named on the maker's page"))

    def test_read_failed_note_removed_is_allowed(self):
        self.assertNoRegression(part(READ_FAILED), part(None))

    def test_read_failed_clause_removed_keeps_other_clauses(self):
        self.assertNoRegression(part(READ_FAILED + "; Discontinued (the store's tag)"),
                                part("Discontinued (the store's tag)"))

    def test_read_failed_clause_removed_with_a_stated_clause_lost_is_a_regression(self):
        self.assertRegression(part(READ_FAILED + "; Discontinued (the store's tag)"),
                              part("Named on the maker's page"))

    # name on the part record
    def test_name_pack_count_dropped_is_a_regression(self):
        self.assertRegression(part(name="Hex Driver Wrench Set - 7pc"), part(name="Hex Driver Wrench Set"))

    def test_name_changed_text_is_a_regression(self):
        self.assertRegression(part(name="Hex Driver Wrench Set"), part(name="Hex Driver Wrench Kit"))

    def test_name_qualifier_added_is_a_regression(self):
        # a name is what the record is matched by: "(FZD2)" added is another name, unlike a note with text added
        self.assertRegression(part(name="Spool Cup"), part(name="Spool Cup (FZD2)"))

    def test_name_moved_to_former_names_with_pack_qty_is_allowed(self):
        self.assertNoRegression(part(name="Servo Mount 2P"),
                                part(name="Servo Mount", extra='pack_qty = 2\nformer_names = ["Servo Mount 2P"]\n'))

    def test_name_same_in_canonical_form_is_allowed(self):
        self.assertNoRegression(part(name="JConcepts Hex Driver Set"), part(name="Hex Driver Set"))

    def test_name_pack_count_kept_as_pack_qty_is_allowed(self):
        self.assertNoRegression(part(name="Hex Driver Set (7)"), part(name="Hex Driver Set", extra="pack_qty = 7\n"))

    def test_name_number_replaced_is_allowed(self):
        self.assertNoRegression(part(name="2457", name_source=None), part(name="Hex Driver Wrench Set"))

    # notes inside fits and links rows
    def test_fit_row_note_changed_is_a_regression(self):
        base = part(extra='fits = [ { kit = "kit/jconcepts/reactor", type = "direct", notes = "Fits per manual p3" } ]\n')
        head = part(extra='fits = [ { kit = "kit/jconcepts/reactor", type = "direct", notes = "Fits" } ]\n')
        self.assertRegression(base, head)

    def test_fit_row_note_text_added_is_allowed(self):
        base = part(extra='fits = [ { kit = "kit/jconcepts/reactor", type = "direct", notes = "Fits per manual p3" } ]\n')
        head = part(extra='fits = [ { kit = "kit/jconcepts/reactor", type = "direct", '
                          'notes = "Fits per manual p3; also the 2nd edition" } ]\n')
        self.assertNoRegression(base, head)

    def test_link_row_note_changed_is_a_regression(self):
        base = part().replace('url = "https://jconcepts.net/hex-driver-wrench-set" }',
                              'url = "https://jconcepts.net/hex-driver-wrench-set", notes = "Shown on the product page" }')
        head = part().replace('url = "https://jconcepts.net/hex-driver-wrench-set" }',
                              'url = "https://jconcepts.net/hex-driver-wrench-set", notes = "Shown" }')
        self.assertRegression(base, head)


if __name__ == "__main__":
    unittest.main()
