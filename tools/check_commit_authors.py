#!/usr/bin/env python3
"""Fail when a commit in BASE..HEAD names an email outside ALLOWED.

Each commit's author email, committer email and every Co-authored-by
trailer email are checked. Usage:

    python3 -I tools/check_commit_authors.py BASE [HEAD]

HEAD defaults to HEAD. Exit status: 0 when every commit passes, 1 when
a commit names another email, 2 when git cannot list the range.
"""
import argparse
import re
import subprocess
import sys

ALLOWED = {
    "francisdb@gmail.com",
    "francisdb@users.noreply.github.com",
    "noreply@github.com",  # GitHub as committer of web-flow and squash merges
    "49699333+dependabot[bot]@users.noreply.github.com",
}

# fields: sha, author email, committer email, subject, trailer values; records end with 0x1e
FORMAT = (
    "%H%x1f%ae%x1f%ce%x1f%s%x1f"
    "%(trailers:key=Co-authored-by,valueonly,unfold,separator=%x0a)%x1e"
)
EMAIL = re.compile(r"<([^<>]*)>")


def commits(base, head):
    result = subprocess.run(
        ["git", "log", f"--format={FORMAT}", f"{base}..{head}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(2)
    for record in result.stdout.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, author, committer, subject, trailers = record.split("\x1f", 4)
        values = [line.strip() for line in trailers.split("\n") if line.strip()]
        yield sha, author, committer, subject, values


def problems(author, committer, values):
    """Return (label, email) for every address outside ALLOWED."""
    found = []
    for label, email in (("author", author), ("committer", committer)):
        if email.strip().lower() not in ALLOWED:
            found.append((label + " email", email.strip()))
    for value in values:
        match = EMAIL.search(value)
        if match is None:
            found.append(("Co-authored-by without an email", value))
        elif match.group(1).strip().lower() not in ALLOWED:
            found.append(("Co-authored-by email", match.group(1).strip()))
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("base", help="the base revision; commits in base..head are checked")
    parser.add_argument("head", nargs="?", default="HEAD")
    args = parser.parse_args()

    total = 0
    failures = []
    for sha, author, committer, subject, values in commits(args.base, args.head):
        total += 1
        for label, email in problems(author, committer, values):
            failures.append(f"commit {sha[:12]} ({subject}): {label} {email} is not allowed")

    if failures:
        print("commits name an email outside the allowed list:", file=sys.stderr)
        for line in failures:
            print("  " + line, file=sys.stderr)
        print(
            "allowed: " + ", ".join(sorted(ALLOWED))
            + "; rewrite those commits with an allowed identity",
            file=sys.stderr,
        )
        return 1
    print(f"{total} commit(s) in {args.base}..{args.head} name only allowed emails")
    return 0


if __name__ == "__main__":
    sys.exit(main())
