"""No entry twice in one record's lists: what a UNIQUE index on (record, entry) would refuse."""


def test_list_entry_unique(hard):
    """No entry twice in a record's documents, aliases, numbers, former_ids, former_numbers, listed_as, releases,
    kits, parts or requires (aliases ignore case)."""
    hard("""SELECT owner AS record, field || ' lists ' || min(value) || ' ' || count(*) || ' times' AS problem
        FROM list_values GROUP BY owner, field, CASE WHEN field = 'aliases' THEN lower(value) ELSE value END
        HAVING count(*) > 1""")


def test_link_url_unique(hard):
    """No page twice in a record's links (scheme, www., trailing slash and fragment ignored): keep one row, with the
    fields of both."""
    hard("""SELECT owner AS record, 'links lists ' || min(url) || ' ' || count(*) || ' times' AS problem
        FROM links WHERE nurl IS NOT NULL GROUP BY owner, nurl HAVING count(*) > 1""")


def test_fits_row_unique(hard):
    """No two fits rows of a part that make the same claim (the same kit, type, releases, car and replaced part):
    one row, the other sources in notes."""
    hard("""SELECT owner AS record, 'fits names ' || json_extract(row, '$.kit') || ' (' ||
        coalesce(json_extract(row, '$.type'), '-') || ') ' || count(*) || ' times' AS problem
        FROM list_rows WHERE field = 'fits'
        GROUP BY owner, json_extract(row, '$.kit'), json_extract(row, '$.type'), json_extract(row, '$.releases'),
          json_extract(row, '$.car'), json_extract(row, '$.replaces') HAVING count(*) > 1""")


def test_includes_item_unique(ratchet):
    """No part or spec twice in a part's includes with the same notes: one row, its qty the total."""
    ratchet("includes-item-unique", """SELECT owner AS record, 'includes lists ' || coalesce(json_extract(row, '$.part'), json_extract(row, '$.spec'))
        || ' ' || count(*) || ' times' AS problem
        FROM list_rows WHERE field = 'includes' AND coalesce(json_extract(row, '$.part'), json_extract(row, '$.spec')) IS NOT NULL
        GROUP BY owner, json_extract(row, '$.part'), json_extract(row, '$.spec'), json_extract(row, '$.notes')
        HAVING count(*) > 1""")


def test_contains_row_unique(ratchet):
    """No part twice in a release's contains with the same role, source and step: one row per part and source, its
    qty summed over the steps (docs/schema.md "release")."""
    ratchet("contains-row-unique", """SELECT owner AS record, 'contains lists ' || json_extract(row, '$.part') || ' (' ||
        json_extract(row, '$.role') || ', ' || coalesce(json_extract(row, '$.source'), '-') || ') ' || count(*) || ' times' AS problem
        FROM list_rows WHERE field = 'contains'
        GROUP BY owner, json_extract(row, '$.part'), json_extract(row, '$.role'), json_extract(row, '$.source'),
          json_extract(row, '$.step') HAVING count(*) > 1""")
