"""tools/check_commit_authors.py on a small repo built in a temp dir.

Commits are written as raw objects with fixed authors, so the test never
reads or changes the git identity of the machine it runs on.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("check_commit_authors.py")
WHEN = "1700000000 +0000"


def git(repo, *args, stdin=""):
    result = subprocess.run(
        ["git", *args], cwd=repo, input=stdin, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def commit(repo, parent, author, committer, message):
    tree = git(repo, "mktree", stdin="")
    lines = [f"tree {tree}"]
    if parent:
        lines.append(f"parent {parent}")
    lines += [f"author {author} {WHEN}", f"committer {committer} {WHEN}", "", message]
    return git(repo, "hash-object", "-t", "commit", "-w", "--stdin", stdin="\n".join(lines) + "\n")


def check(repo, base, head):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), base, head],
        cwd=repo,
        capture_output=True,
        text=True,
    )


FRANCIS = "Francis De Brabandere <francisdb@gmail.com>"
GITHUB = "GitHub <noreply@github.com>"


class CheckCommitAuthors(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        git(self.repo, "init", "-q")
        self.base = commit(self.repo, None, FRANCIS, FRANCIS, "root\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_allowed_identities_pass(self):
        head = commit(
            self.repo,
            self.base,
            "Francis <francisdb@users.noreply.github.com>",
            GITHUB,
            "web edit\n",
        )
        head = commit(
            self.repo,
            head,
            "dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>",
            "dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>",
            "bump\n\nCo-authored-by: Francis <FrancisDB@gmail.com>\n",
        )
        result = check(self.repo, self.base, head)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_author_outside_list_fails_naming_commit_and_email(self):
        bad = commit(self.repo, self.base, "Agent <x@x>", FRANCIS, "change\n")
        result = check(self.repo, self.base, bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn(bad[:12], result.stderr)
        self.assertIn("author email x@x is not allowed", result.stderr)

    def test_committer_outside_list_fails(self):
        bad = commit(self.repo, self.base, FRANCIS, "Someone <other@example.com>", "change\n")
        result = check(self.repo, self.base, bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn("committer email other@example.com is not allowed", result.stderr)

    def test_co_author_trailer_outside_list_fails(self):
        bad = commit(
            self.repo,
            self.base,
            FRANCIS,
            FRANCIS,
            "pair work\n\nCo-authored-by: Stranger <stranger@example.com>\n",
        )
        result = check(self.repo, self.base, bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Co-authored-by email stranger@example.com is not allowed", result.stderr)

    def test_lowercase_trailer_key_is_checked(self):
        bad = commit(
            self.repo,
            self.base,
            FRANCIS,
            FRANCIS,
            "pair work\n\nco-authored-by: Stranger <stranger@example.com>\n",
        )
        result = check(self.repo, self.base, bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn("stranger@example.com", result.stderr)

    def test_co_author_without_email_fails(self):
        bad = commit(
            self.repo, self.base, FRANCIS, FRANCIS, "pair work\n\nCo-authored-by: Nobody\n"
        )
        result = check(self.repo, self.base, bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Co-authored-by without an email", result.stderr)

    def test_commits_at_or_before_base_are_not_checked(self):
        old = commit(self.repo, None, "Agent <x@x>", "Agent <x@x>", "old\n")
        head = commit(self.repo, old, FRANCIS, FRANCIS, "new\n")
        result = check(self.repo, old, head)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_range_passes(self):
        result = check(self.repo, self.base, self.base)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_base_is_an_error(self):
        result = check(self.repo, "0" * 40, self.base)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
