"""Parts: names and categories (the data-only checks of the daily audit, under their audit names)."""
import collections, json, re

from rules import (is_aircraft_part, item_scales_contradict, kit_words, scaled_name_scales,
                   tamiya_maker_linked, twin_class, twin_pairs, unbalanced)


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
    """Parts with no category: the fallback (misc with category_source fallback) that no classifier rule or maker
    source places. Misc itself is a category and never counts (owner 2026-11-18). Blocking: a change that adds
    fallback parts fails; extend the classifier rules (hobbydex-tools tools/data/classify_parts.toml) for the names
    listed, never write a guessed category."""
    ratchet("part-category-fallback", """SELECT id AS record,
          'no category (fallback): ' || coalesce(json_extract(data, '$.name'), '(no name)') AS problem FROM records
        WHERE kind = 'part' AND json_extract(data, '$.category_source') = 'fallback'""")


def test_part_named_by_number(ratchet):
    """Parts whose name is their item number: the name comes from the maker's parts list. Reported, not blocking:
    importers add parts a manual names by number only (code as name)."""
    ratchet("part-named-by-number", """SELECT id AS record, 'named by its number' AS problem FROM records
        WHERE kind = 'part' AND json_extract(data, '$.name') = json_extract(data, '$.number')
          AND json_type(data, '$.name') = json_type(data, '$.number')""", blocking=False)


def test_part_ocr_number_only(ratchet):
    """Parts whose only evidence is an OCR read of their number: named by the number (name_source ocr, or the note
    "Named by its number only"), one document, and no link, barcode, web sighting or fits row of another source. Such a
    number may be lettering inside a drawing or a misread (Kyosho's "OT227 2900098" on a pictured belt became C0227);
    an importer takes a new number only from a printed list row (a name or a count beside it). Each one left was checked
    against a lossless crop of its page by the vision model (2026-11-18); a new one is a fault of the importer."""
    ratchet("part-ocr-number-only", """SELECT id AS record, 'number read by OCR only, from ' ||
            json_extract(data, '$.documents[0]') AS problem FROM records
        WHERE kind = 'part' AND json_extract(data, '$.name') = json_extract(data, '$.number')
          AND (json_extract(data, '$.name_source') = 'ocr'
               OR coalesce(json_extract(data, '$.notes'), '') LIKE 'Named by its number only%')
          AND json_array_length(json_extract(data, '$.documents')) = 1
          AND json_extract(data, '$.links') IS NULL AND json_extract(data, '$.gtin') IS NULL
          AND coalesce(json_extract(data, '$.seen_by_source'), '') NOT LIKE 'http%'
          AND NOT EXISTS (SELECT 1 FROM json_each(json_extract(data, '$.fits')) f
                          WHERE json_extract(f.value, '$.source') IS NOT json_extract(data, '$.documents[0]'))""")


def test_part_named_by_hardware_code(ratchet):
    """Parts whose only name is a bearing code with a seal suffix (MR106RS, R168-2RS) or a metric screw size (M3X8) in
    their number: the size the code stands for names them (name_source "spec", tools/name_hardware_codes.py in
    hobbydex-tools). The ones left are codes that read two ways or contradict their pack; the count may only fall."""
    ratchet("part-named-by-hardware-code", r"""SELECT id AS record, 'named by a hardware code only' AS problem FROM records
        WHERE kind = 'part' AND json_extract(data, '$.name') = json_extract(data, '$.number')
          AND json_type(data, '$.name') = 'text'
          AND json_extract(data, '$.number') REGEXP '(?i)^(?:[A-Z]{1,3}-?)?(?:F|MF|MR|R)?\d{2,4}-?(?:ZZ|2RS|RS|RZ)(?:-\w+)?$|M\d(?:[.-]\d)?X\d{1,2}$'""")


def test_spec_name_links_spec(hard):
    """A part named from a standard size (name_source "spec") links the generic spec of that size in equivalent_to."""
    hard("""SELECT id AS record, 'named from a spec but links no spec' AS problem FROM records
        WHERE kind = 'part' AND json_extract(data, '$.name_source') = 'spec'
          AND NOT EXISTS (SELECT 1 FROM json_each(data, '$.equivalent_to') e WHERE json_extract(e.value, '$.spec') IS NOT NULL)""")


def test_part_no_car_link(ratchet, db):
    """Parts of a car-specific category with no fits row and no release that contains them: the linking queue (a fits
    row, or the release that contains it). Parts of any-car categories (any_car in data/categories), universal parts
    and aircraft parts are left out. Reported, not blocking: importers add parts before their cars are linked."""
    any_car = {i.split("/")[-1] for (i,) in db.execute("""SELECT id FROM records WHERE kind = 'category'
        AND truthy(json_extract(data, '$.any_car'))""")}
    in_box = {p for (p,) in db.execute("SELECT DISTINCT json_extract(row, '$.part') FROM list_rows WHERE field = 'contains'")}
    rows = []
    for pid, brand, number, cat, universal, applies in db.execute("""SELECT id, json_extract(data, '$.brand'),
            json_extract(data, '$.number'), json_extract(data, '$.category'), json_type(data, '$.universal'),
            truthy(json_extract(data, '$.applies_to')) FROM records WHERE kind = 'part'
            AND NOT truthy(json_extract(data, '$.fits')) AND truthy(json_extract(data, '$.category'))"""):
        if pid in in_box or universal == "true" or (cat in any_car and not applies) or is_aircraft_part(brand, number):
            continue
        rows.append((pid, f"{cat}: no fits row, in no release"))
    ratchet("part-no-car-link", rows, blocking=False)


def test_fits_kit_no_release(ratchet):
    """A fits row names a kit that has releases (a family kit, family = true, owes none): add the kit's release, or
    remove the row. Reported, not blocking: parts importers name parts-only kits before their releases are added."""
    ratchet("fits-kit-no-release", """SELECT l.owner AS record, 'fits ' || k.id || ', which has no release' AS problem
        FROM list_rows l JOIN records k ON k.id = json_extract(l.row, '$.kit') AND k.kind = 'kit'
        WHERE l.field = 'fits' AND NOT truthy(json_extract(k.data, '$.family'))
          AND k.id NOT IN (SELECT json_extract(data, '$.kit') FROM records WHERE kind = 'release'
            AND json_extract(data, '$.kit') IS NOT NULL)""", blocking=False)


def test_fits_scale_contradicts_kit(ratchet, db):
    """A fits row whose listing names the car at another scale than the kit's: the part's applies_to or the row's
    notes state a scale for every car they list and none is the kit's ("1/18 Ruckus 4WD" fitted to the 1/10 Ruckus
    4WD); or the part's name, applies_to or notes put a scale right before the name of a kit that states none, while
    the brand holds a kit of that scale and that name ("1/16 Mini Slash" fitted to the Mini Slash 4X4, not the 1/16
    Slash). Move the row to the kit of the listed scale (the importer's car alias), or remove it."""
    kits = {kid: (json.loads(d) if d else {}) for kid, d in db.execute("SELECT id, data FROM records WHERE kind = 'kit'")}
    brand_names = {bid: (json.loads(d) or {}).get("name", "") for bid, d in db.execute(
        "SELECT id, data FROM records WHERE kind = 'brand'")}
    scaled = collections.defaultdict(list)   # brand -> [(kit id, scale, name words)]
    for kid, k in kits.items():
        if k.get("scale") and kit_words(k.get("name")):
            scaled[k.get("brand")].append((kid, k["scale"], kit_words(k.get("name"))))
    rows = []
    for pid, name, applies, row in db.execute("""SELECT r.id, json_extract(r.data, '$.name'),
            json_extract(r.data, '$.applies_to'), l.row FROM list_rows l JOIN records r ON r.id = l.owner
            WHERE l.field = 'fits' AND r.kind = 'part'"""):
        row = json.loads(row)
        k = kits.get(row.get("kit"))
        if not k:
            continue
        notes = row.get("notes") or ""
        listed = " ; ".join(x for x in (applies if isinstance(applies, str) else "", notes) if x)
        if k.get("scale"):
            if item_scales_contradict(applies if isinstance(applies, str) else "", k["scale"]) or (
                    item_scales_contradict(notes, k["scale"])):
                rows.append((pid, f"fits {row['kit']} ({k['scale']}), listed as {listed!r}"))
            continue
        text = (name or "") + " ; " + listed
        at = scaled_name_scales(text, k.get("name"), brand_names.get(k.get("brand"), ""))
        other = [kid for kid, sc, words in scaled.get(k.get("brand"), [])
                 if sc in at and words <= kit_words(k.get("name")) and kid != row["kit"]]
        if other:
            rows.append((pid, f"fits {row['kit']} (no scale), listed at {'/'.join(sorted(at))}: {other[0]}"))
    ratchet("fits-scale-contradicts-kit", rows)


def test_spec_unlinked(ratchet):
    """Every spec is used by a part (equivalent_to, includes or protocols): link a part to it, or retire it."""
    ratchet("spec-unlinked", """WITH used AS (
          SELECT json_extract(j.value, '$.spec') AS spec FROM records r, json_each(r.data, '$.equivalent_to') j
            WHERE r.kind = 'part' AND json_type(r.data, '$.equivalent_to') = 'array' AND j.type = 'object'
          UNION SELECT json_extract(row, '$.spec') FROM list_rows WHERE field = 'includes' AND json_type(row) = 'object'
          UNION SELECT j.value FROM records r, json_each(r.data, '$.protocols') j
            WHERE r.kind = 'part' AND json_type(r.data, '$.protocols') = 'array' AND j.type = 'text')
        SELECT id AS record, 'no part uses it' AS problem FROM records
        WHERE kind = 'spec' AND id NOT IN (SELECT spec FROM used WHERE spec IS NOT NULL)""")


def _tamiya_parts(db):
    for pid, number, name_source, links in db.execute("""SELECT id, json_extract(data, '$.number'),
            json_extract(data, '$.name_source'), json_extract(data, '$.links') FROM records
            WHERE kind = 'part' AND json_extract(data, '$.brand') = 'brand/tamiya'"""):
        yield pid, "" if number is None else str(number), name_source, json.loads(links) if links else []


def test_tamiya_spare_no_link(ratchet, db):
    """Tamiya 8-digit spares with no maker link (Tamiya USA's spare page, tamiya.de, or a capture of a gone tamiya.com
    page); a spare named by OCR of a manual is counted in tamiya-spare-label-only. Reported, not blocking."""
    ratchet("tamiya-spare-no-link", [(pid, "no maker link" + (" (dealer link only)" if any(l.get("kind") == "dealer" for l in links) else ""))
                                     for pid, num, src, links in _tamiya_parts(db)
                                     if re.fullmatch(r"\d{8}", num) and not tamiya_maker_linked(links) and src != "ocr"],
            blocking=False)


def test_tamiya_spare_label_only(ratchet, db):
    """Tamiya 8-digit spares named by OCR of a manual (a bag or parts-tree label) with no maker page: the maker sells
    no spare page for such a number (informational, not blocking)."""
    ratchet("tamiya-spare-label-only", [(pid, "named by OCR, no maker page") for pid, num, src, links in _tamiya_parts(db)
                                        if re.fullmatch(r"\d{8}", num) and not tamiya_maker_linked(links) and src == "ocr"],
            blocking=False)


def test_tamiya_item_no_link(ratchet, db):
    """Tamiya 5-digit item numbers with no maker product page and no dealer link: a maker link (tamiya.com page), a
    manual or a fan-site source. Reported, not blocking."""
    ratchet("tamiya-item-no-link", [(pid, "no maker link") for pid, num, src, links in _tamiya_parts(db)
                                    if re.fullmatch(r"\d{5}", num) and not tamiya_maker_linked(links)
                                    and not any(l.get("kind") == "dealer" for l in links)], blocking=False)


def test_twin_parts(ratchet, db):
    """The same part number and name under two brands is shared only when the brands are related and each record
    cites its own brand's source (or one names the other in rebrand_of, or they state different measures). A copy
    (a record cites the other brand's site or document) moves to the brand that makes it; an unclear pair needs both
    brands' sources checked."""
    pairs = twin_pairs([{"id": i, "brand": b, "name": n, "number": num} for i, b, n, num in db.execute("""SELECT id,
        json_extract(data, '$.brand'), json_extract(data, '$.name'), json_extract(data, '$.number') FROM records
        WHERE kind = 'part' AND truthy(json_extract(data, '$.number')) AND json_type(data, '$.name') = 'text'""")])
    ids = sorted({x["id"] for pair in pairs for x in pair})
    full = {}
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        for rid, data in db.execute(f"SELECT id, data FROM records WHERE kind = 'part' AND id IN ({','.join('?' * len(chunk))})", chunk):
            full[rid] = json.loads(data)
    brands = {i: json.loads(d) for i, d in db.execute("SELECT id, data FROM records WHERE kind = 'brand'")}
    companies = {i: json.loads(d) for i, d in db.execute("SELECT id, data FROM records WHERE kind = 'company'")}
    docs = {i: {"brand": b} for i, b in db.execute("SELECT id, json_extract(data, '$.brand') FROM records WHERE kind = 'doc'")}
    rows = []
    for a, b in pairs:
        cls = twin_class(full[a["id"]], full[b["id"]], brands, companies, docs)
        if cls != "shared":
            rows += [(a["id"], f"{cls} twin of {b['id']}"), (b["id"], f"{cls} twin of {a['id']}")]
    ratchet("twin-parts", rows)


# a part of category servo that is a servo itself (not a horn, saver, case, gear set or mount): the name says servo and
# no accessory word, or it states a figure (torque, speed or performance)
SERVO_ACCESSORY = re.compile(r"(?i)horn|saver|\barm\b|case|gear|mount|tape|holder|plate|bracket|cover|screw|extension|lead|"
                             r"cable|wire|protector|guard|stay|link|spacer|grommet|post|tester|programm|card|box|set\b|parts?\b|"
                             r"heat ?sink|cap\b|seal")


def _servos(db):
    rows = db.execute("""SELECT id, json_extract(data, '$.name'), json_extract(data, '$.torque_kgcm'),
          json_extract(data, '$.speed_s'), json_extract(data, '$.performance'), json_extract(data, '$.equivalent_to')
        FROM records WHERE kind = 'part' AND json_extract(data, '$.category') = 'servo'""")
    out = []
    for pid, name, tq, sp, pf, eq in rows:
        pf = json.loads(pf) if pf else []
        figures = tq is not None or sp is not None or pf
        if figures or (re.search(r"(?i)\bservo\b", name or "") and not SERVO_ACCESSORY.search(name or "")):
            out.append((pid, name, tq is not None or any("torque_kgcm" in r for r in pf),
                        sp is not None or any("speed_s" in r for r in pf),
                        any(str(e.get("spec", "")).startswith("spec/servo/") for e in json.loads(eq or "[]"))))
    return out


def test_servo_no_speed(ratchet, db):
    """A servo with no speed (s/60 degrees) stated, top-level or in performance: read it from the maker's page
    (hobbydex-tools tools/link_servo_pages.py, tools/servo_performance.py for a new page layout). Reported, not
    blocking: importers add servos from sources that state no figures."""
    ratchet("servo-no-speed", [(pid, f"no speed: {name}") for pid, name, _, sp, _ in _servos(db) if not sp], blocking=False)


def test_servo_no_torque(ratchet, db):
    """A servo with no torque (kg-cm) stated, top-level or in performance: as servo-no-speed."""
    ratchet("servo-no-torque", [(pid, f"no torque: {name}") for pid, name, tq, _, _ in _servos(db) if not tq], blocking=False)


def test_servo_no_size_spec(ratchet, db):
    """A servo linked to no spec/servo size spec: the maker states no size class, and its dimensions fit no size range
    or no spline is stated (hobbydex-tools tools/link_servo_pages.py counts each reason)."""
    ratchet("servo-no-size-spec", [(pid, f"no size spec: {name}") for pid, name, _, _, spec in _servos(db) if not spec],
            blocking=False)


def test_servo_figure_out_of_range(hard):
    """A servo whose headline speed_s is not seconds per 60 degrees (0.005 to 2) or whose torque_kgcm is not kg-cm (0.1 to
    500): a misread figure (".10 sec" read as 0, ".062 sec" as 2, ".07sec" as 7). Fix the reader (hobbydex-tools
    tools/horizon_specs.py, tools/servo_performance.py) and the value from the maker's page, as performance rows are
    checked by tools/validate.py."""
    hard("""SELECT id AS record, 'speed_s ' || coalesce(json_extract(data, '$.speed_s'), '-')
            || ', torque_kgcm ' || coalesce(json_extract(data, '$.torque_kgcm'), '-') AS problem FROM records
        WHERE kind = 'part' AND json_extract(data, '$.category') = 'servo'
          AND (json_extract(data, '$.speed_s') NOT BETWEEN 0.005 AND 2
               OR json_extract(data, '$.torque_kgcm') NOT BETWEEN 0.1 AND 500)""", "servo-figure-out-of-range")


def test_servo_case_oversize(hard):
    """A servo whose dimensions_mm has a side of 90 mm or more: no car servo case is that large (a 1/5-scale one is about
    66 x 30 x 58 mm), so it is the package size a shop lists as the product size (Horizon's 102 x 51 x 14 mm for a mini
    servo). The importer refuses such a size for a servo (hobbydex-tools tools/sources/rules/horizon-specs.tsv)."""
    hard("""SELECT id AS record, 'dimensions_mm ' || json_extract(data, '$.dimensions_mm') AS problem
        FROM records WHERE kind = 'part' AND json_extract(data, '$.category') = 'servo'
          AND EXISTS (SELECT 1 FROM json_each(json_extract(records.data, '$.dimensions_mm')) d WHERE d.value >= 90)""",
         "servo-case-oversize")
