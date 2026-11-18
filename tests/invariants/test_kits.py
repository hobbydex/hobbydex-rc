"""Kits (platforms): names and releases (the data-only checks of the daily audit, under their audit names)."""
import collections, json, re

from rules import NEAR_DUP_KEPT, YEAR, near_dup_key, norm_name


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


def test_platform_no_manual_or_page(ratchet):
    """Platforms with releases but no manual or maker product page: none on its releases, no manual or product page
    that lists the kit in kits, and no maker link on the kit. Reported, not blocking: importers add platforms before
    their pages are found."""
    ratchet("platform-no-manual-or-page", """WITH rk AS (SELECT id AS rid, json_extract(data, '$.kit') AS kit FROM records
          WHERE kind = 'release'),
        paged AS (SELECT DISTINCT rk.kit FROM rk JOIN list_values v ON v.owner = rk.rid AND v.field = 'documents'
          JOIN docs d ON d.id = v.value WHERE d.kind IN ('manual', 'product_page') AND rk.kit IS NOT NULL),
        dockits AS (SELECT DISTINCT v.value AS kit FROM list_values v JOIN docs d ON d.id = v.owner
          WHERE v.field = 'kits' AND d.kind IN ('manual', 'product_page'))
        SELECT k.id AS record, 'no manual or product page' AS problem FROM records k
        WHERE k.kind = 'kit' AND k.id IN (SELECT kit FROM rk WHERE kit IS NOT NULL)
          AND k.id NOT IN (SELECT kit FROM paged) AND k.id NOT IN (SELECT kit FROM dockits)
          AND NOT EXISTS (SELECT 1 FROM links l WHERE l.owner = k.id AND (l.kind IS NULL OR l.kind = 'maker')
            AND NOT truthy(l.gone))""", blocking=False)


def _releases_by_kit(db):
    out = collections.defaultdict(list)
    for rid, kit, name, number, scale, notes in db.execute("""SELECT id, json_extract(data, '$.kit'),
            json_extract(data, '$.name'), json_extract(data, '$.number'), json_extract(data, '$.scale'),
            json_extract(data, '$.notes') FROM records WHERE kind = 'release'"""):
        out[kit].append({"id": rid, "name": name, "number": number, "scale": scale, "notes": notes})
    return out


def test_kit_mixed_scale(hard, db):
    """A kit whose releases disagree on scale states the shared scale, and a release scale that differs from the kit
    has a note with its source (a catch-all group kit, notes "Group for ...", is skipped)."""
    rels = _releases_by_kit(db)
    rows = []
    for kid, scale, notes in db.execute("""SELECT id, json_extract(data, '$.scale'), json_extract(data, '$.notes')
            FROM records WHERE kind = 'kit'"""):
        if str(notes or "").startswith("Group for "):
            continue
        rs = rels.get(kid, [])
        eff = {r["scale"] or scale for r in rs} - {None}
        unsourced = [r for r in rs if r["scale"] and r["scale"] != scale and not r["notes"]]
        if len(eff) > 1 and (not scale or unsourced):
            rows.append((kid, "release scales " + ", ".join(sorted(map(str, eff)))))
    hard(rows, name="kit-mixed-scale")


def test_duplicate_name_in_kit(hard, db):
    """No two releases of a kit with the same name and item number: merge them (former_ids) if they are one item."""
    rows = []
    for kid, rs in _releases_by_kit(db).items():
        names = collections.Counter((str(r["name"]).strip().lower(), norm_name("" if r["number"] is None else str(r["number"])))
                                    for r in rs)
        rows += [(kid, f"{n[0]!r} twice") for n, c in names.items() if c > 1 and kid is not None]
    hard(rows, name="duplicate-name-in-kit")


def test_near_duplicate_model(ratchet, db):
    """One real vehicle under one depicts.model per make: two spellings that differ only in colour, body or kit words
    (Actros 3363 and Actros 3363 GigaSpace) are folded into one (the site's vehicle-moves table follows)."""
    items = []
    for rid, make, model in db.execute("""SELECT id, json_extract(data, '$.depicts.make'), json_extract(data, '$.depicts.model')
            FROM records WHERE (kind = 'release' OR (kind = 'part' AND json_extract(data, '$.category') = 'body'))
              AND truthy(json_extract(data, '$.depicts.make'))"""):
        items.append((rid, make, model))
    near = collections.defaultdict(lambda: collections.defaultdict(set))
    for _, make, model in items:
        if model:
            near[(make, near_dup_key(model))][re.sub(r"[^a-z0-9]", "", model.lower())].add(model)
    groups = {k: v for k, v in near.items() if k[1] and len(v) > 1 and k not in NEAR_DUP_KEPT}
    ratchet("near-duplicate-model", [(rid, f"{make}: " + " | ".join(sorted(s for sp in groups[(make, near_dup_key(model or ''))].values() for s in sp)))
                                     for rid, make, model in items if (make, near_dup_key(model or "")) in groups])
