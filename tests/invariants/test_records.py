"""Fields a record may not leave empty (NOT NULL), and the known gaps that may only shrink."""
import json

from rules import BANNED_HOSTS, LOCAL_PATH, SCRAP_IMG, TAMICO_OWNER_DOCS, walk_strings



def test_part_has_category(hard):
    """Every part has a category (misc is one; a part no rule places has the fallback, counted by
    part-category-fallback)."""
    hard("""SELECT id AS record, 'no category' AS problem FROM records
        WHERE kind = 'part' AND coalesce(trim(json_extract(data, '$.category')), '') = ''""")


def test_part_has_number(hard):
    """Every part of a brand that prints item numbers has its number."""
    hard("""SELECT p.id AS record, 'no number' AS problem FROM records p
        LEFT JOIN records b ON b.id = json_extract(p.data, '$.brand')
        WHERE p.kind = 'part' AND json_extract(p.data, '$.number') IS NULL
          AND coalesce(json_extract(b.data, '$.item_numbers'), 1) != 0""")


def test_part_number_unique(hard):
    """No two parts of one brand under one number (a number, or one of numbers)."""
    hard("""WITH n AS (
          SELECT id, json_extract(data, '$.brand') AS brand, json_extract(data, '$.number') AS num FROM records
            WHERE kind = 'part' AND json_extract(data, '$.number') IS NOT NULL
          UNION ALL SELECT r.id, json_extract(r.data, '$.brand'), j.value FROM records r, json_each(r.data, '$.numbers') j
            WHERE r.kind = 'part' AND json_type(r.data, '$.numbers') = 'array')
        SELECT min(id) AS record, brand || ' number ' || num || ' is on ' || group_concat(DISTINCT id) AS problem
        FROM n GROUP BY brand, num HAVING count(DISTINCT id) > 1""")


def test_release_has_kit(hard):
    """Every release names its kit, and the kit exists and is of the same brand."""
    hard("""SELECT r.id AS record, CASE WHEN k.id IS NULL THEN 'kit ' || coalesce(json_extract(r.data, '$.kit'), '(none)') || ' does not exist'
          ELSE 'kit ' || k.id || ' is of ' || json_extract(k.data, '$.brand') END AS problem
        FROM records r LEFT JOIN records k ON k.id = json_extract(r.data, '$.kit') AND +k.kind = 'kit'
        WHERE r.kind = 'release' AND (k.id IS NULL OR json_extract(k.data, '$.brand') != json_extract(r.data, '$.brand'))""")


def test_release_has_number(ratchet):
    """Releases of a brand that prints item numbers but with no number yet. Reported, not blocking: importers still add
    releases a source names without a number (partial records are kept)."""
    ratchet("release-no-number", """SELECT r.id AS record, 'no number' AS problem FROM records r
        LEFT JOIN records b ON b.id = json_extract(r.data, '$.brand')
        WHERE r.kind = 'release' AND json_extract(r.data, '$.number') IS NULL
          AND coalesce(json_extract(b.data, '$.item_numbers'), 1) != 0""", blocking=False)


def test_kit_has_category(hard):
    """Every kit (platform) has a category."""
    hard("""SELECT id AS record, 'no category' AS problem FROM records
        WHERE kind = 'kit' AND json_extract(data, '$.category') IS NULL""")


def test_kit_has_scale(ratchet):
    """Kits with no scale yet (a family kit takes none). Reported, not blocking: a scale is set only when a source
    states it, and new kits often come without one."""
    ratchet("kit-no-scale", """SELECT k.id AS record, 'no scale' AS problem FROM records k
        WHERE k.kind = 'kit' AND json_extract(k.data, '$.scale') IS NULL AND coalesce(json_extract(k.data, '$.family'), 0) = 0""", blocking=False)


def test_doc_has_kind(hard):
    """Every document has a kind."""
    hard("""SELECT id AS record, 'no kind' AS problem FROM records WHERE kind = 'doc' AND json_extract(data, '$.kind') IS NULL""")


def test_reference_lists_resolve(hard):
    """Every id in a record's documents, releases, kits and parts lists is a record of that kind."""
    hard("""SELECT v.owner AS record, v.field || ' -> ' || v.value || ' does not exist' AS problem
        FROM list_values v LEFT JOIN records t ON t.id = v.value
        WHERE v.field IN ('documents', 'releases', 'kits', 'parts') AND t.id IS NULL""")


def test_banned_host(hard, db):
    """No record links House of RC or Tamico, or an rcscrapyard image address. A tamico.de dealer link is allowed for
    a Tamiya spare with no maker page, and Xtra Speed's Tamico listing documents keep their address (no maker page)."""
    rows = []
    for rid, path, data in db.execute("""SELECT id, path, data FROM records
            WHERE data LIKE '%houseofrc%' OR data LIKE '%tamico%' OR data LIKE '%rcscrapyard%'"""):
        d = json.loads(data)
        links = [l for l in d.get("links", []) if not (isinstance(l, dict) and set(l) == {"site", "url", "kind"}
                                                        and l["site"] == "tamico.de" and l["kind"] == "dealer")]
        text = "\n".join(walk_strings({**d, "links": links} if isinstance(d.get("links"), list) else d))
        if BANNED_HOSTS.search(text) and not path.startswith(TAMICO_OWNER_DOCS):
            rows.append((rid or path, "links " + BANNED_HOSTS.search(text).group(0)))
        if SCRAP_IMG.search(text):
            rows.append((rid or path, "links the image " + SCRAP_IMG.search(text).group(0)))
    hard(rows, name="banned-host")


def test_tamico_doc_reference(ratchet):
    """A record cites the maker's own listing, not the Tamico dealer catalogue (doc/tamiya/tamico-dealer-parts)."""
    ratchet("tamico-doc-reference", """SELECT coalesce(id, path) AS record, 'cites the Tamico dealer catalogue' AS problem
        FROM records WHERE instr(data, 'doc/tamiya/tamico-dealer-parts') > 0
          AND path != 'data/documents/tamiya/tamico-dealer-parts.toml'""")


def test_local_path(ratchet, db):
    """No local path (/home/, /tmp/, file://, C:\\, work/manuals/, cache/) in a record: the source's URL instead."""
    rows = []
    for rid, path, data in db.execute(r"""SELECT id, path, data FROM records WHERE data LIKE '%/home/%' OR data LIKE '%/Users/%'
            OR data LIKE '%/tmp/%' OR data LIKE '%file://%' OR data LIKE '%:\%' OR data LIKE '%work/manuals/%'
            OR data LIKE '%cache/%'"""):
        hit = next((s for s in walk_strings(json.loads(data)) if LOCAL_PATH.search(s)), None)
        if hit:
            rows.append((rid or path, "local path in " + repr(hit[:80])))
    ratchet("local-path", rows)


def test_dimension_plausible(hard, db):
    """A car's dimensions fit its scale (a 1/10 car has no 2,000 mm wheelbase): every figure times the scale divisor
    is a plausible full-size figure, the wheelbase is not longer than the car and the track not more than 5 % wider. A body's stated
    wheelbase and track are checked the same way. Fix the figure or the unit from the maker page in dimensions.source."""
    from rules import dimension_problems
    kit_scale = dict(db.execute("SELECT id, json_extract(data, '$.scale') FROM records WHERE kind = 'kit'"))
    rows = []
    for rid, kind, data in db.execute("""SELECT id, kind, data FROM records WHERE
            (kind IN ('kit', 'release') AND json_extract(data, '$.dimensions') IS NOT NULL)
            OR (kind = 'part' AND json_extract(data, '$.category') IN ('body', 'body-accessory')
                AND (json_extract(data, '$.wheelbase_mm') IS NOT NULL OR json_extract(data, '$.track_mm') IS NOT NULL
                     OR json_extract(data, '$.track_front_mm') IS NOT NULL OR json_extract(data, '$.track_rear_mm') IS NOT NULL))"""):
        d = json.loads(data)
        if kind == "part":
            dims = {k: d[k] for k in ("wheelbase_mm", "track_mm", "track_front_mm", "track_rear_mm") if k in d}
            scale = d.get("scale")
        else:
            dims = d.get("dimensions") if isinstance(d.get("dimensions"), dict) else {}
            scale = d.get("scale") or kit_scale.get(d.get("kit") if kind == "release" else rid)
        rows += [(rid, p) for p in dimension_problems(dims, scale)]
    hard(rows, name="dimension-plausible")
