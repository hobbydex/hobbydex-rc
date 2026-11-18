"""Kits (platforms): names and releases (the data-only checks of the daily audit, under their audit names)."""
import json

from rules import YEAR


def test_platform_year_name(ratchet, db):
    """A platform is not named after a year later than its oldest release: rename it after the oldest release (the
    year lives on the release), the old id in former_ids."""
    oldest = dict(db.execute("""SELECT kit, min(y) FROM (SELECT json_extract(data, '$.kit') AS kit,
          CASE WHEN truthy(json_extract(data, '$.year')) THEN json_extract(data, '$.year')
               ELSE CAST(substr(coalesce(json_extract(data, '$.released'), '0'), 1, 4) AS INTEGER) END AS y
          FROM records WHERE kind = 'release') WHERE y GROUP BY kit"""))
    rows = []
    for kid, name, former in db.execute("""SELECT id, json_extract(data, '$.name'), json_extract(data, '$.former_ids')
            FROM records WHERE kind = 'kit'"""):
        old = oldest.get(kid)
        names = [name or "", kid] + (json.loads(former) if former else [])
        later = sorted({y for n in names for y in YEAR.findall(str(n)) if int(y) > int(old)}) if old else []
        if later:
            rows.append((kid, f"named {', '.join(later)}, oldest release {old}"))
    ratchet("platform-year-name", rows)


def test_platform_no_release(ratchet):
    """Platforms with no release: add the platform's releases, or retire the platform if it is not a product.
    Reported, not blocking: parts importers add the kits their fits rows name before any release is known."""
    ratchet("platform-no-release", """SELECT id AS record, 'no release' AS problem FROM records
        WHERE kind = 'kit' AND id NOT IN (SELECT json_extract(data, '$.kit') FROM records
          WHERE kind = 'release' AND json_extract(data, '$.kit') IS NOT NULL)""", blocking=False)
