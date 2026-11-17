"""python3 -I tools/test_validate_website_archive.py (from the repository root)

A brand whose website's domain is no longer the maker's keeps `website` and adds `website_archive`, a Wayback capture
of a page on that host, with `website_note` (docs/schema.md "brand").
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate  # noqa: E402

BRAND = {"id": "brand/x", "name": "X", "status": "gone", "website": "https://www.ofna.com",
         "website_archive": "https://web.archive.org/web/20190216185048/http://www.ofna.com:80/index.php",
         "website_note": "domain now parked, archived copy"}


def errors_for(**changes):
    d = {k: v for k, v in dict(BRAND, **changes).items() if v is not None}
    errors = []
    validate.check_website_archive([("data/brands/x.toml", "brand", d)], errors)
    return errors


class WebsiteArchive(unittest.TestCase):
    def test_capture_of_the_website_host_is_valid(self):
        self.assertEqual(errors_for(), [])
        self.assertEqual(errors_for(website_archive="https://web.archive.org/web/20190216185048/http://ofna.com/"), [])

    def test_brand_without_archive_is_valid(self):
        self.assertEqual(errors_for(website_archive=None, website_note=None), [])

    def test_every_state_is_accepted(self):
        for state in ("parked", "for sale", "reused", "gone"):
            self.assertEqual(errors_for(website_note=f"domain now {state}, archived copy"), [], state)

    def test_capture_must_be_a_dated_wayback_url(self):
        for bad in ("https://www.ofna.com/", "https://web.archive.org/web/2019/http://www.ofna.com/",
                    "http://web.archive.org/web/20190216185048/http://www.ofna.com/",
                    "https://web.archive.org/web/20190216185048id_/http://www.ofna.com/"):
            self.assertEqual(len(errors_for(website_archive=bad)), 1, bad)

    def test_capture_must_be_of_the_website_host(self):
        self.assertEqual(len(errors_for(website_archive="https://web.archive.org/web/20190216185048/http://ofna.example/")), 1)

    def test_note_is_required_and_fixed(self):
        self.assertEqual(len(errors_for(website_note=None)), 1)
        self.assertEqual(len(errors_for(website_note="domain now gone")), 1)
        self.assertEqual(len(errors_for(website_note="domain now sold, archived copy")), 1)

    def test_archive_needs_a_website(self):
        self.assertEqual(len(errors_for(website=None)), 1)


if __name__ == "__main__":
    unittest.main()
