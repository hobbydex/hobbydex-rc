"""Parts: names and categories (the data-only checks of the daily audit, under their audit names)."""
from rules import unbalanced


def test_name_unbalanced_bracket(ratchet, db):
    """A part name whose brackets do not pair up was cut inside a bracket: restore the full name from the maker's
    source (its count goes to pack_qty). A name the maker prints unbalanced is kept (name_source manufacturer or
    manual, and notes saying "kept as printed by the maker")."""
    rows = db.execute("""SELECT id, json_extract(data, '$.name') FROM records WHERE kind = 'part'
        AND json_extract(data, '$.name') REGEXP '[()（）]'
        AND NOT (json_extract(data, '$.name_source') IN ('manufacturer', 'manual')
          AND instr(coalesce(json_extract(data, '$.notes'), ''), 'kept as printed by the maker') > 0)""")
    ratchet("name-unbalanced-bracket", [(pid, f"name {name!r}") for pid, name in rows if unbalanced(name)])


def test_bearing_rebuild_kit(ratchet):
    """A part in category bearing is a bearing, not a rebuild or service kit (a set of parts)."""
    ratchet("bearing-rebuild-kit", """SELECT id AS record, 'bearing named ' || json_extract(data, '$.name') AS problem
        FROM records WHERE kind = 'part' AND json_extract(data, '$.category') = 'bearing'
          AND json_extract(data, '$.name') REGEXP '(?i)\\b(rebuild|service|overhaul|repair)\\b'""")


def test_part_category_fallback(ratchet):
    """Parts with the fallback category (misc, category_source fallback): no classifier rule or maker source places
    them yet. Reported, not blocking: importers still add parts no rule places (partial records are kept)."""
    ratchet("part-category-fallback", """SELECT id AS record, 'category_source fallback' AS problem FROM records
        WHERE kind = 'part' AND json_extract(data, '$.category_source') = 'fallback'""", blocking=False)


def test_part_named_by_number(ratchet):
    """Parts whose name is their item number: the name comes from the maker's parts list. Reported, not blocking:
    importers add parts a manual names by number only (code as name)."""
    ratchet("part-named-by-number", """SELECT id AS record, 'named by its number' AS problem FROM records
        WHERE kind = 'part' AND json_extract(data, '$.name') = json_extract(data, '$.number')
          AND json_type(data, '$.name') = json_type(data, '$.number')""", blocking=False)
