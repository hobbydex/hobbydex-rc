"""A wrong, half-present or unreadable data checkout fails audit.load and audit.walk; it is never read as "no holes".

    python3 -I tools/test_audit_walk_errors.py
"""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def tree(tmp, folders):
    for f in folders:
        os.makedirs(os.path.join(tmp, "data", f, "x"))
        with open(os.path.join(tmp, "data", f, "x", "a.toml"), "w", encoding="utf-8") as fh:
            fh.write(f'id = "{f}/x/a"\n')


def raises(fn, kind, text=""):
    try:
        fn()
    except kind as ex:
        assert text in str(ex), (text, str(ex))
        return
    raise AssertionError(f"{fn} did not raise {kind.__name__}")


def test_a_full_tree_loads():
    with tempfile.TemporaryDirectory() as tmp:
        tree(tmp, audit.REQUIRED_FOLDERS)
        db = audit.load(tmp)
        assert all(len(db[f]) == 1 for f in audit.REQUIRED_FOLDERS)


def test_no_data_folder_fails():
    with tempfile.TemporaryDirectory() as tmp:
        raises(lambda: audit.load(tmp), SystemExit, "is not a folder")


def test_an_empty_required_folder_fails():
    with tempfile.TemporaryDirectory() as tmp:
        tree(tmp, [f for f in audit.REQUIRED_FOLDERS if f != "parts"])
        raises(lambda: audit.load(tmp), SystemExit, "data/parts")


def test_a_missing_top_folder_is_empty_and_a_file_there_is_an_error():
    with tempfile.TemporaryDirectory() as tmp:
        assert list(audit.walk(os.path.join(tmp, "no-such"))) == []
        path = os.path.join(tmp, "art")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not a folder")
        raises(lambda: list(audit.walk(path)), NotADirectoryError)


def test_an_unlistable_subfolder_fails():
    if os.geteuid() == 0:   # root lists any folder; the case cannot be made there
        print("skip test_an_unlistable_subfolder_fails (root)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        locked = os.path.join(tmp, "top", "locked")
        os.makedirs(locked)
        os.chmod(locked, 0)
        try:
            raises(lambda: list(audit.walk(os.path.join(tmp, "top"))), PermissionError)
        finally:
            os.chmod(locked, 0o755)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
