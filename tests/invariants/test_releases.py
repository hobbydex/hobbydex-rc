"""Releases: names, dates and categories (the data-only checks of the daily audit, under their audit names)."""
import collections

from rules import is_body_set_doc, is_service_pack, norm_name


def test_date_marker_question(hard):
    """No *_doubt field on a release: the ? sits in the date column of a narrow table; shorten the reason into the
    release notes and confirm the date."""
    hard("""SELECT id AS record, 'has a *_doubt field' AS problem FROM records WHERE kind = 'release'
        AND (json_type(data, '$.year_doubt') IS NOT NULL OR json_type(data, '$.released_doubt') IS NOT NULL
          OR json_type(data, '$.announced_doubt') IS NOT NULL)""", name="date-marker-question")


def test_duplicate_release_name(hard, db):
    """No two releases of one brand with the same name and the same item number: a duplicate (releases with distinct
    item numbers are distinct releases)."""
    groups = collections.defaultdict(list)
    for rid, brand, name, number in db.execute("""SELECT id, json_extract(data, '$.brand'), json_extract(data, '$.name'),
            json_extract(data, '$.number') FROM records WHERE kind = 'release'"""):
        if name and brand and isinstance(name, str):
            groups[(brand, " ".join(name.split()).casefold(), norm_name("" if number is None else str(number)))].append(rid)
    hard([(rid, "same name and number as " + ", ".join(i for i in g if i != rid))
          for g in groups.values() if len(g) > 1 for rid in g], name="duplicate-release-name")


def test_service_pack_in_box(ratchet, db):
    """No Traxxas service, rebuild or upgrade pack as a kit row of a release's contains: such a pack is not in the box
    (role option or listed)."""
    rows = db.execute("""SELECT l.owner, json_extract(l.row, '$.part'), json_extract(p.data, '$.name')
        FROM list_rows l JOIN records r ON r.id = l.owner AND r.kind = 'release'
        LEFT JOIN records p ON p.id = json_extract(l.row, '$.part')
        WHERE l.field = 'contains' AND json_extract(l.row, '$.role') = 'kit'
          AND json_extract(r.data, '$.brand') = 'brand/traxxas'""")
    ratchet("service-pack-in-box", [(rid, f"kit row {pid} is a service pack") for rid, pid, name in rows
                                    if is_service_pack(name if isinstance(name, str) else "")])


def test_body_manual_only(ratchet, db):
    """A release whose contents come only from a body-set manual while its kit has a kit manual: source the contents
    from the kit manual (or mark the body manual's parts as listed only)."""
    docs = {i: (k, t if isinstance(t, str) else "") for i, k, t in db.execute("""SELECT id, json_extract(data, '$.kind'),
        json_extract(data, '$.title') FROM records WHERE kind = 'doc'""")}

    def body(d):
        return is_body_set_doc(docs.get(d, (None, ""))[1], d)

    srcs = collections.defaultdict(set)
    for owner, src in db.execute("""SELECT owner, json_extract(row, '$.source') FROM list_rows WHERE field = 'contains'
            AND truthy(json_extract(row, '$.source'))"""):
        srcs[owner].add(src)
    kit_of, rel_docs = {}, collections.defaultdict(list)
    for rid, kit in db.execute("SELECT id, json_extract(data, '$.kit') FROM records WHERE kind = 'release'"):
        kit_of[rid] = kit
    for owner, d in db.execute("""SELECT v.owner, v.value FROM list_values v JOIN records r ON r.id = v.owner
            AND r.kind = 'release' WHERE v.field = 'documents'"""):
        rel_docs[kit_of[owner]].append(d)
    rows = []
    for rid, ss in srcs.items():
        if rid not in kit_of or not all(body(s) for s in ss):
            continue
        if any(docs.get(d, (None,))[0] == "manual" and not body(d) for d in rel_docs.get(kit_of[rid], [])):
            rows.append((rid, "contents only from a body-set manual"))
    ratchet("body-manual-only", rows)


def test_copyright_year(hard):
    """No release year from a copyright line: a copyright line is an on-sale bound (seen_by, year precision), not a
    release year."""
    hard("""SELECT id AS record, 'year ' || json_extract(data, '$.year') || ' from a copyright line' AS problem
        FROM records WHERE kind = 'release' AND truthy(json_extract(data, '$.year'))
          AND NOT truthy(json_extract(data, '$.released'))
          AND json_extract(data, '$.notes') REGEXP '(?i)copyright|\\(c\\)|©'""", name="copyright-year")


def test_release_named_by_number(ratchet):
    """A release named only by its item number: give it the product name from the maker's page (a model code the
    maker's own page uses as the title is fine when sources.name holds that page)."""
    ratchet("release-named-by-number", """SELECT id AS record, 'named ' || json_extract(data, '$.name') AS problem
        FROM records WHERE kind = 'release' AND json_extract(data, '$.name') REGEXP '\\A[\\w-]*\\d[\\w-]*\\Z'
          AND (json_type(data, '$.number') IS NULL OR json_extract(data, '$.number') = json_extract(data, '$.name'))
          AND NOT truthy(json_extract(data, '$.sources.name'))""", blocking=False)


def test_release_no_date(ratchet):
    """Releases with no date at all (released, year, announced or a seen_by bound). Reported, not blocking: importers
    add releases a source names without a date."""
    ratchet("release-no-date", """SELECT id AS record, 'no date' AS problem FROM records WHERE kind = 'release'
        AND NOT truthy(json_extract(data, '$.released')) AND NOT truthy(json_extract(data, '$.year'))
        AND NOT truthy(json_extract(data, '$.announced')) AND NOT truthy(json_extract(data, '$.seen_by'))""",
            blocking=False)


def test_date_without_source(ratchet):
    """A release year or release date names its source (released_source: the page URL or its doc/ id); with none,
    the date goes (a printed manual date stays as seen_by)."""
    ratchet("date-without-source", """SELECT id AS record, 'year or released with no released_source' AS problem
        FROM records WHERE kind = 'release' AND (json_type(data, '$.year') IS NOT NULL
          OR truthy(json_extract(data, '$.released'))) AND NOT truthy(json_extract(data, '$.released_source'))""")


def test_announced_after_seen_by(hard):
    """No announced day later than the seen_by bound (on a release or a part): its source is wrong; remove announced
    and announced_source (the bound stays)."""
    hard("""SELECT id AS record, 'announced ' || a || ' after seen_by ' || b AS problem FROM (
          SELECT id, CAST(json_extract(data, '$.announced') AS TEXT) AS a, CAST(json_extract(data, '$.seen_by') AS TEXT) AS b
          FROM records WHERE kind IN ('release', 'part') AND truthy(json_extract(data, '$.announced'))
            AND truthy(json_extract(data, '$.seen_by')))
        WHERE substr(a, 1, length(b)) > b""", name="announced-after-seen-by")


def test_release_category_redundant(hard):
    """A release's category differs from its kit's: the same category is the kit's to state (remove it)."""
    hard("""SELECT r.id AS record, 'category ' || json_extract(r.data, '$.category') || ' is the kit''s' AS problem
        FROM records r JOIN records k ON k.id = json_extract(r.data, '$.kit') AND k.kind = 'kit'
        WHERE r.kind = 'release' AND truthy(json_extract(r.data, '$.category'))
          AND json_extract(r.data, '$.category') = json_extract(k.data, '$.category')""",
         name="release-category-redundant")


def test_depicts_no_model(hard):
    """A release that depicts a real vehicle names its model (depicts.model; make is optional)."""
    hard("""SELECT id AS record, 'depicts with no model' AS problem FROM records WHERE kind = 'release'
        AND truthy(json_extract(data, '$.depicts')) AND NOT truthy(json_extract(data, '$.depicts.model'))""",
         name="depicts-no-model")
