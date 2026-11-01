"""audit.load_art_sources: the run-time copy in cache/art/sources wins per brand; the seed is the fallback.

    python3 -I -m pytest tools/test_audit_art_sources.py -q
"""
import os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit  # noqa: E402


def write(d, brand, ids):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, brand + ".toml"), "w") as f:
        for i in ids:
            f.write(f'[[item]]\nid = "{i}"\nphoto = "https://example.com/{i}.jpg"\n\n')


def test_runtime_copy_replaces_seed_per_brand():
    with tempfile.TemporaryDirectory() as root:
        write(os.path.join(root, "tools", "art", "sources"), "axial", ["release/axial/a", "release/axial/b"])
        write(os.path.join(root, "cache", "art", "sources"), "axial", ["release/axial/a"])
        ids = [i["id"] for i in audit.load_art_sources(root)]
        assert ids == ["release/axial/a"]


def test_seed_is_fallback_for_brand_without_runtime_copy():
    with tempfile.TemporaryDirectory() as root:
        write(os.path.join(root, "tools", "art", "sources"), "arrma", ["release/arrma/x"])
        write(os.path.join(root, "cache", "art", "sources"), "axial", ["release/axial/a"])
        ids = sorted(i["id"] for i in audit.load_art_sources(root))
        assert ids == ["release/arrma/x", "release/axial/a"]


def test_no_directories_is_none():
    with tempfile.TemporaryDirectory() as root:
        assert audit.load_art_sources(root) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
