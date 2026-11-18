"""Hardware and electronics parts: pack counts, spec links and plugs (the data-only checks of the daily audit, under
their audit names)."""
import collections, json, re

from rules import (BALANCE_NAME, BATTERY_ACCESSORY, BATTERY_ITSELF, ELEC_FIELDS, HW, MAT_WORDS, PLUG, count_unstated,
                   gear_pitch_as_count, kit_sum, servo_named, servo_plugs, sold_in_packs, spec_mismatches)


def _parts(db, where, params=()):
    """The parts that match a WHERE clause on records (as p), as dicts."""
    return [json.loads(d) for (d,) in db.execute(f"SELECT p.data FROM records p WHERE p.kind = 'part' AND ({where})", params)]


def _pack_counts(db):
    """{brand id: {"pack_counts": False}} for the brands that state pack_counts = false (count_unstated reads it)."""
    return {i: {"pack_counts": False} for (i,) in db.execute("""SELECT id FROM records WHERE kind = 'brand'
        AND json_type(data, '$.pack_counts') = 'false'""")}


def _in(values):
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def test_hw_pack_counts(ratchet, db):
    """Hardware sold in packs (a bag of small items or a set: sold_in_packs) states its count (pack_qty) or lists the
    bag's specs (includes). Reported, not blocking: importers add parts before their count is read."""
    brands = _pack_counts(db)
    no_pack = [p for p in _parts(db, f"""json_extract(p.data, '$.category') IN {_in(HW)}
        AND json_type(p.data, '$.pack_qty') IS NULL AND NOT truthy(json_extract(p.data, '$.includes'))""")
               if sold_in_packs(p)]
    ratchet("hw-no-pack-count", [(p["id"], "no pack_qty") for p in no_pack if not count_unstated(p, brands)],
            blocking=False)


def test_hw_pack_count_unstated(ratchet, db):
    """Hardware sold in packs whose maker states only a minimum count ("180+ pieces.") or none (the brand's
    pack_counts = false): nothing to fill (informational, not blocking)."""
    brands = _pack_counts(db)
    no_pack = [p for p in _parts(db, f"""json_extract(p.data, '$.category') IN {_in(HW)}
        AND json_type(p.data, '$.pack_qty') IS NULL AND NOT truthy(json_extract(p.data, '$.includes'))""")
               if sold_in_packs(p)]
    ratchet("hw-pack-count-unstated", [(p["id"], "count unstated") for p in no_pack if count_unstated(p, brands)],
            blocking=False)


def test_tamiya_hex_head_socket(hard, db):
    """A Tamiya "Hex Head" screw is a hexagon head with a JIS cross recess (spec/screw/*-hex-jis*), never a socket cap."""
    hard([(p["id"], "hex head linked to a socket cap") for p in _parts(db, """json_extract(p.data, '$.brand') = 'brand/tamiya'
            AND json_extract(p.data, '$.category') = 'screw' AND json_extract(p.data, '$.name') REGEXP '(?i)\\bhex head\\b'""")
          if any("socket-cap" in e.get("spec", "") for e in p.get("equivalent_to", []))], name="tamiya-hex-head-socket")


def _hw_kits(db):
    return _parts(db, f"""json_extract(p.data, '$.category') IN {_in(HW)} AND truthy(json_extract(p.data, '$.includes'))""")


def test_kit_includes_no_qty(ratchet, db):
    """Every includes row of a hardware kit has its qty (the pieces in the bag), unless the source lists the items
    without counts (includes_qty = "unstated")."""
    ratchet("kit-includes-no-qty", [(p["id"], "an includes row with no qty") for p in _hw_kits(db)
                                    if kit_sum(p) is None and p.get("includes_qty") != "unstated"])


def test_kit_pack_not_sum(ratchet, db):
    """A hardware kit's pack_qty is the sum of its includes qty, or the rows are whole sets of it (4 sets of 5)."""
    ratchet("kit-pack-not-sum", [(p["id"], f"pack_qty {p['pack_qty']}, includes sum {kit_sum(p)}") for p in _hw_kits(db)
                                 if "pack_qty" in p and kit_sum(p) is not None and p["pack_qty"] != kit_sum(p)
                                 and not all(r["qty"] % p["pack_qty"] == 0 for r in p["includes"])])


def test_pack_qty_has_basis(ratchet):
    """A pack_qty records its basis (pack_qty_basis: name, page, includes, manual, distributor, photo ...)."""
    ratchet("pack-qty-no-basis", """SELECT id AS record, 'pack_qty with no pack_qty_basis' AS problem FROM records
        WHERE kind = 'part' AND json_type(data, '$.pack_qty') IS NOT NULL AND json_type(data, '$.pack_qty_basis') IS NULL""")


def test_pack_qty_is_pitch(hard, db):
    """A gear's pack_qty is not its pitch (pitch_dp, or the pitch printed in its name: "90T SPUR GEAR (48P)")."""
    rows = []
    for p in _parts(db, "json_extract(p.data, '$.category') IN ('gear', 'pinion', 'spur-gear') AND json_type(p.data, '$.pack_qty') IS NOT NULL"):
        why = gear_pitch_as_count(p)
        if why:
            rows.append((p["id"], why))
    hard(rows, name="pack-qty-is-pitch")


def test_spec_mismatch(hard, db):
    """A spec link (equivalent_to or includes) is of a family the part's category or name carries: no bearing on a
    clip, no motor spec on a rebuild kit."""
    parts = _parts(db, "truthy(json_extract(p.data, '$.equivalent_to')) OR truthy(json_extract(p.data, '$.includes'))")
    hard([(i, f"{field} {spec}: {why}") for i, field, spec, why in spec_mismatches(parts)], name="spec-mismatch")


def test_wire_plug_no_connectors(ratchet, db):
    """A lead whose name names its plugs lists them in connectors (or is a plug, equivalent_to its connector spec).
    Reported, not blocking."""
    rows = [(p["id"], "plugs named, no connectors") for p in _parts(db, "json_extract(p.data, '$.category') = 'wire'")
            if PLUG.search(p.get("name", "")) and not p.get("connectors")
            and not any(str(e.get("spec", "")).startswith("spec/connector/") for e in p.get("equivalent_to", []) if isinstance(e, dict))]
    ratchet("wire-plug-no-connectors", rows, blocking=False)


def test_servo_plug_crossed(hard, db):
    """A part whose name gives only the Futaba plug is not linked to the JR plug, or the other way round (they mate
    but are two specs)."""
    rows = []
    for p in _parts(db, """json_extract(p.data, '$.name') REGEXP '(?i)futaba|\\bJ[- ]?plug|\\bJR\\b|hitec|universal'
            OR (json_extract(p.data, '$.brand') = 'brand/futaba' AND json_extract(p.data, '$.category') = 'servo')"""):
        want, got = servo_named(p), servo_plugs(p)
        if want and got and want not in got:
            rows.append((p["id"], f"named {want}, linked {', '.join(sorted(got))}"))
    hard(rows, name="servo-plug-crossed")


def test_battery_esc_no_connector(ratchet):
    """Batteries and ESCs state the plug they use (connector). Reported, not blocking."""
    ratchet("battery-esc-no-connector", """SELECT id AS record, json_extract(data, '$.category') || ' with no connector' AS problem
        FROM records WHERE kind = 'part' AND json_extract(data, '$.category') IN ('battery', 'esc')
          AND NOT truthy(json_extract(data, '$.connector'))""", blocking=False)


def test_battery_balance_name_no_connector(hard, db):
    """A battery whose name states the JST-XH balance lead has balance_connector = "JST-XH"."""
    hard([(p["id"], "JST-XH balance lead named, no balance_connector") for p in _parts(db, "json_extract(p.data, '$.category') = 'battery'")
          if not p.get("balance_connector") and BALANCE_NAME.search(p.get("name", ""))], name="battery-balance-name-no-connector")


def test_battery_accessory_name(ratchet, db):
    """A battery accessory (tape, lid, clasp, cup, strap ...) or a device named with its battery is not filed as a
    battery: it takes the category of what it belongs to."""
    ratchet("battery-accessory-name", [(p["id"], f"battery named {p.get('name')!r}") for p in _parts(db, "json_extract(p.data, '$.category') = 'battery'")
                                       if BATTERY_ACCESSORY.search(p.get("name", "")) and not BATTERY_ITSELF.search(p.get("name", ""))])


def test_bearing_default_material(ratchet, db):
    """A brand's bearings carry a material only where a source states it: when most of a brand's bearings (10 or
    more) carry one material that at most 5% of their names say, it is a default, not a source."""
    per = collections.defaultdict(list)
    for brand, name, material in db.execute("""SELECT json_extract(data, '$.brand'), json_extract(data, '$.name'),
            json_extract(data, '$.material') FROM records WHERE kind = 'part' AND json_extract(data, '$.category') = 'bearing'"""):
        per[brand].append((name if isinstance(name, str) else "", material))
    brands = {i for (i,) in db.execute("SELECT id FROM records WHERE kind = 'brand'")}
    rows = []
    for b, ps in per.items():
        for m, word in MAT_WORDS.items():
            with_m = [n for n, mat in ps if mat == m]
            if len(with_m) >= 10 and 2 * len(with_m) >= len(ps) and b in brands \
                    and 20 * sum(1 for n in with_m if re.search(word, n, re.I)) <= len(with_m):
                rows.append((b, f"{len(with_m)} of {len(ps)} bearings {m}, no name says so"))
                break
    ratchet("bearing-default-material", rows)


def test_electronics_field_rare(ratchet, db):
    """The electronics fields the schema defines for a category (motor, esc, servo, battery) that fewer than 5% of
    that category's parts carry: filled from the maker's own wording where it states them. Reported, not blocking."""
    rows = []
    for cat, fields in ELEC_FIELDS.items():
        cols = fields.split()
        # a field counts when it is there and not "" or an empty list (0 and false are values)
        sel = ", ".join(f"sum(json_type(data, '$.{f}') IS NOT NULL AND coalesce(json_extract(data, '$.{f}'), 1) NOT IN ('', '[]'))"
                        for f in cols)
        n, *with_ = db.execute(f"""SELECT count(*), {sel} FROM records WHERE kind = 'part'
            AND json_extract(data, '$.category') = ?""", (cat,)).fetchone()
        for f, w in zip(cols, with_):
            if n and 20 * (w or 0) < n:
                rows.append((f"{cat} {f}", f"{w or 0} of {n} parts ({100 * (w or 0) / n:.1f}%)"))
    ratchet("electronics-field-rare", rows, blocking=False)
