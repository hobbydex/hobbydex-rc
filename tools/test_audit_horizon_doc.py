"""audit.horizon_doc_no_page: a Horizon document with no page is flagged, except a catalog (a site-level record whose
url is a home page or sitemap), a product page, an owner report and a video.

    python3 -I tools/test_audit_horizon_doc.py
"""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

HORIZON = {"brand/axial"}
URL = "https://www.horizonhobby.com/on/demandware.static/-/Sites-horizon-master/default/dw0bdca6a1/Manuals/AXI-2260-MANUAL-DE.pdf"


def doc(kind, **extra):
    return dict({"brand": "brand/axial", "kind": kind, "url": URL}, **extra)


class HorizonDocNoPageTest(unittest.TestCase):
    def test_manual_without_page_is_flagged(self):
        self.assertTrue(audit.horizon_doc_no_page(doc("manual"), HORIZON))

    def test_manual_with_page_is_not_flagged(self):
        self.assertFalse(audit.horizon_doc_no_page(doc("manual", page="https://www.horizonhobby.com/product/x.html"), HORIZON))

    def test_catalog_is_not_flagged(self):
        self.assertFalse(audit.horizon_doc_no_page(doc("catalog", url="https://www.horizonhobby.com/sitemap_index.xml"), HORIZON))

    def test_product_page_owner_report_and_video_are_not_flagged(self):
        for kind in ("product_page", "owner_report", "video"):
            self.assertFalse(audit.horizon_doc_no_page(doc(kind), HORIZON), kind)

    def test_other_brand_is_not_flagged(self):
        self.assertFalse(audit.horizon_doc_no_page(dict(doc("manual"), brand="brand/tamiya"), HORIZON))


if __name__ == "__main__":
    unittest.main()
