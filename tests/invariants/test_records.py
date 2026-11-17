"""Fields a record may not leave empty (NOT NULL), and the known gaps that may only shrink."""


def test_part_has_category(hard):
    """Every part has a category."""
    hard("""SELECT id AS record, 'no category' AS problem FROM records
        WHERE kind = 'part' AND json_extract(data, '$.category') IS NULL""")


def test_part_misc(ratchet):
    """Parts in category misc: no source has stated what they are yet. The count is reported, not blocking: importers
    still add parts no source categorises (partial records are kept, docs/schema.md "part")."""
    ratchet("part-misc", """SELECT id AS record, 'category misc' AS problem FROM records
        WHERE kind = 'part' AND json_extract(data, '$.category') = 'misc'""", blocking=False)


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
        FROM records r LEFT JOIN records k ON k.id = json_extract(r.data, '$.kit') AND k.kind = 'kit'
        WHERE r.kind = 'release' AND (k.id IS NULL OR json_extract(k.data, '$.brand') != json_extract(r.data, '$.brand'))""")


def test_release_has_number(ratchet):
    """Releases of a brand that prints item numbers but with no number yet. The count may only shrink."""
    ratchet("release-no-number", """SELECT r.id AS record, 'no number' AS problem FROM records r
        LEFT JOIN records b ON b.id = json_extract(r.data, '$.brand')
        WHERE r.kind = 'release' AND json_extract(r.data, '$.number') IS NULL
          AND coalesce(json_extract(b.data, '$.item_numbers'), 1) != 0""")


def test_kit_has_category(hard):
    """Every kit (platform) has a category."""
    hard("""SELECT id AS record, 'no category' AS problem FROM records
        WHERE kind = 'kit' AND json_extract(data, '$.category') IS NULL""")


def test_kit_has_scale(ratchet):
    """Kits with no scale yet (a family kit takes none). The count may only shrink."""
    ratchet("kit-no-scale", """SELECT k.id AS record, 'no scale' AS problem FROM records k
        WHERE k.kind = 'kit' AND json_extract(k.data, '$.scale') IS NULL AND coalesce(json_extract(k.data, '$.family'), 0) = 0""")


def test_doc_has_kind(hard):
    """Every document has a kind."""
    hard("""SELECT id AS record, 'no kind' AS problem FROM records WHERE kind = 'doc' AND json_extract(data, '$.kind') IS NULL""")


def test_reference_lists_resolve(hard):
    """Every id in a record's documents, releases, kits and parts lists is a record of that kind."""
    hard("""SELECT v.owner AS record, v.field || ' -> ' || v.value || ' does not exist' AS problem
        FROM list_values v LEFT JOIN records t ON t.id = v.value
        WHERE v.field IN ('documents', 'releases', 'kits', 'parts') AND t.id IS NULL""")
