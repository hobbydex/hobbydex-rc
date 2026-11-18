"""Releases: names, dates and categories (the data-only checks of the daily audit, under their audit names)."""
import collections, json, os, re, tomllib

from rules import HW, complete_diff, is_body_set_doc, is_service_pack, norm_name, number_relation, same_product_record
from snapshot import RC


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


def test_release_no_product_page(ratchet):
    """Releases with no maker product page: no product_page document and no link other than a fan site. Reported,
    not blocking: importers add releases a manual or catalogue names before their page is found."""
    ratchet("release-no-product-page", """SELECT r.id AS record, 'no product page' AS problem FROM records r
        WHERE r.kind = 'release'
          AND NOT EXISTS (SELECT 1 FROM list_values v JOIN docs d ON d.id = v.value
            WHERE v.owner = r.id AND v.field = 'documents' AND d.kind = 'product_page')
          AND NOT EXISTS (SELECT 1 FROM links l WHERE l.owner = r.id AND coalesce(l.kind, '') != 'fan-site')""",
            blocking=False)


def test_release_typed_other_cars(ratchet):
    """Releases typed car, the catch-all (no category on the release or its kit): the kit's type comes from the maker's
    product page or manual. Reported, not blocking: a kit with no source stays car."""
    ratchet("release-typed-other-cars", """SELECT r.id AS record, 'typed car (no category)' AS problem FROM records r
        LEFT JOIN records k ON k.id = json_extract(r.data, '$.kit') AND +k.kind = 'kit'
        WHERE r.kind = 'release' AND CASE WHEN truthy(json_extract(r.data, '$.category')) THEN json_extract(r.data, '$.category')
          WHEN truthy(json_extract(k.data, '$.category')) THEN json_extract(k.data, '$.category') ELSE 'car' END = 'car'""",
            blocking=False)


def test_release_no_contents(ratchet):
    """Releases with no contents yet: the release's parts list goes into contains (or a note that there is none).
    Reported, not blocking: importers add releases before their parts list is read."""
    ratchet("release-no-contents", """SELECT id AS record, 'no contents' AS problem FROM records
        WHERE kind = 'release' AND NOT truthy(json_extract(data, '$.contains'))""", blocking=False)


def test_announced_video_is_linked(hard, db):
    """A release dated by a YouTube video (announced_source) is listed by that video's document (kind video), so the
    site can embed it; a Short or a video that names the model only in hashtags dates nothing."""
    def watch_id(url):
        m = re.search(r"[?&]v=([\w-]+)", str(url or ""))
        return m.group(1) if m and "youtube.com" in str(url) else None
    linked = collections.defaultdict(set)
    for url, rels in db.execute("""SELECT json_extract(data, '$.url'), json_extract(data, '$.releases') FROM records
            WHERE kind = 'doc' AND json_extract(data, '$.kind') = 'video' AND json_type(data, '$.releases') = 'array'"""):
        vid = watch_id(url)
        for rid in json.loads(rels) if vid else []:
            linked[rid].add(vid)
    rows = []
    for rid, src in db.execute("""SELECT id, json_extract(data, '$.announced_source') FROM records WHERE kind = 'release'
            AND truthy(json_extract(data, '$.announced'))"""):
        vid = watch_id(src)
        if vid and vid not in linked.get(rid, set()):
            rows.append((rid, f"announced by video {vid}, which no video document lists"))
    hard(rows, name="announced-video-not-linked")


def test_release_two_gear_pitches(hard):
    """A release's box (kit rows) holds no two pinions, or two spurs, of different pitches: the release's own parts
    list says which one is in the box; the other is option or listed."""
    hard("""SELECT l.owner AS record, json_extract(p.data, '$.category') || ' pitches ' ||
          group_concat(DISTINCT json_extract(p.data, '$.pitch_dp')) AS problem
        FROM list_rows l JOIN records p ON p.id = json_extract(l.row, '$.part')
        WHERE l.field = 'contains' AND json_extract(l.row, '$.role') = 'kit'
          AND json_extract(p.data, '$.category') IN ('pinion', 'spur') AND truthy(json_extract(p.data, '$.pitch_dp'))
        GROUP BY l.owner, json_extract(p.data, '$.category')
        HAVING count(DISTINCT json_extract(p.data, '$.pitch_dp')) > 1""", name="release-two-gear-pitches")


def test_too_many_diffs(ratchet, db):
    """A release's box holds at most three complete differential assemblies (each kit row counted with its qty): the
    extra ones are spares or options, or the part is a case, gear or cup set."""
    n = collections.Counter()
    for owner, qty, cat, name in db.execute("""SELECT l.owner, json_extract(l.row, '$.qty'), json_extract(p.data, '$.category'),
            json_extract(p.data, '$.name') FROM list_rows l JOIN records p ON p.id = json_extract(l.row, '$.part')
            WHERE l.field = 'contains' AND json_extract(l.row, '$.role') = 'kit'
              AND json_extract(p.data, '$.category') = 'differential'"""):
        if complete_diff(cat, name):
            n[owner] += int(1 if qty is None else qty)
    ratchet("too-many-diffs", [(rid, f"{c} complete differentials in the box") for rid, c in n.items() if c > 3])


def test_kit_box_few_hardware(ratchet):
    """A kit release with a manual or exploded view holds at least 10 hardware rows (role kit or listed) in its
    contains: read the box's hardware from the manual. Reported, not blocking: contents are read over time."""
    hw = ", ".join(f"'{c}'" for c in HW)
    ratchet("kit-box-few-hardware", f"""WITH cand AS (SELECT DISTINCT r.id FROM records r
          JOIN list_values v ON v.owner = r.id AND v.field = 'documents' JOIN docs d ON d.id = v.value
          WHERE r.kind = 'release' AND json_extract(r.data, '$.kind') = 'kit' AND d.kind IN ('manual', 'exploded_view')),
        n AS (SELECT c.id, (SELECT count(*) FROM list_rows l JOIN records p ON p.id = json_extract(l.row, '$.part')
          WHERE l.owner = c.id AND l.field = 'contains' AND json_extract(l.row, '$.role') IN ('kit', 'listed')
            AND json_extract(p.data, '$.category') IN ({hw})) AS hw FROM cand c)
        SELECT id AS record, hw || ' hardware rows' AS problem FROM n WHERE hw < 10""", blocking=False)


def test_release_suffix_twin(hard, db):
    """No two releases of one brand whose item numbers differ only by a suffix (34902 / 34902D) and that name one
    product (the same barcode, or the same maker page and no other barcode): fold one into the other, or list the
    pair in data/confirmed-distinct.toml [[release_pair]] when the maker sells them apart."""
    with open(os.path.join(RC, "data", "confirmed-distinct.toml"), "rb") as f:
        reviewed = {frozenset(p["releases"]) for p in tomllib.load(f).get("release_pair", [])}
    groups = collections.defaultdict(list)
    for rid, brand, number, gtin, src in db.execute("""SELECT id, json_extract(data, '$.brand'), json_extract(data, '$.number'),
            json_extract(data, '$.gtin'), json_extract(data, '$.released_source') FROM records WHERE kind = 'release'
            AND truthy(json_extract(data, '$.brand')) AND truthy(json_extract(data, '$.number'))"""):
        groups[(brand, str(number)[:5])].append({"id": rid, "number": number, "gtin": gtin, "released_source": src})
    rows = []
    for g in groups.values():
        for i, a in enumerate(g):
            for b in g[i + 1:]:
                if (number_relation(a["number"], b["number"]) and same_product_record(a, b)
                        and frozenset((a["id"], b["id"])) not in reviewed):
                    rows += [(a["id"], f"one product with {b['id']}"), (b["id"], f"one product with {a['id']}")]
    hard(rows, name="release-suffix-twin")
