"""Cases for archive_files in tools/audit.py: the cached PDF an archive document's listing page links counts as that
document's file in the manual-unlinked check.

An archive document (RC Documents, Valkyrie) links its listing page and carries no file or url. The resolver (in
hobbydex-tools, tools/archive_pdf.py resolve) gives the cached PDF of that page's file; here a fake resolver stands in
for it, so the test needs no tools checkout, cache or crawl database.

    python3 -I tools/test_audit_archive_files.py
"""
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ArchiveFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.tmp.name, "valkyrie-manual.pdf")
        with open(self.pdf, "wb") as fh:
            fh.write(b"%PDF-1.4")
        self.archive = {"id": "doc/team-associated/valkyrie-rc10-manual", "page": "https://www.valkyrierc.com/rc10.html",
                        "kind": "manual", "brand": "brand/team-associated"}
        self.docs = {
            self.archive["id"]: self.archive,
            "doc/x/with-file": {"id": "doc/x/with-file", "page": "https://www.valkyrierc.com/y.html", "file": "y.pdf"},
            "doc/x/with-url": {"id": "doc/x/with-url", "page": "https://www.valkyrierc.com/z.html", "url": "https://a/z.pdf"},
            "doc/x/no-pdf": {"id": "doc/x/no-pdf", "page": "https://www.valkyrierc.com/n.html"},
            "doc/x/maker": {"id": "doc/x/maker", "page": "https://www.acme.com/m.html"},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def resolver(self, did, d):
        # the archive's listing page links the PDF for the Valkyrie document only; every other document has none
        if did == self.archive["id"]:
            return self.pdf, "cached"
        return None, "listing page not cached"

    def test_archive_document_maps_to_its_cached_pdf(self):
        arch = audit.archive_files(self.docs, self.resolver)
        self.assertEqual(list(arch), [os.path.realpath(self.pdf)])
        self.assertEqual([d["id"] for d in arch[os.path.realpath(self.pdf)]], [self.archive["id"]])

    def test_documents_with_a_file_or_url_are_not_resolved(self):
        calls = []

        def spy(did, d):
            calls.append(did)
            return None, "x"
        audit.archive_files(self.docs, spy)
        self.assertNotIn("doc/x/with-file", calls)
        self.assertNotIn("doc/x/with-url", calls)
        self.assertIn(self.archive["id"], calls)

    def test_no_resolver_or_no_pdf_maps_nothing(self):
        self.assertEqual(dict(audit.archive_files(self.docs, None)), {})
        self.assertEqual(dict(audit.archive_files(self.docs, lambda did, d: (None, "not queued"))), {})


if __name__ == "__main__":
    unittest.main()
