"""The word rules and small helpers the invariants share: data-shape rules (what a name, title or date may look like),
nothing about fetching. Each pattern says which invariant reads it."""
import collections, re, urllib.parse

# platform-year-name: a year in a name (1950 to 2049)
YEAR = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")

# doc-placeholder-title: a title that is only item numbers, or repeats one token (the placeholder an importer wrote
# when no name was known: "Tamiya 43501 43501: instruction manual")
PLACEHOLDER_TITLE = re.compile(r"(?<![\w.'/-])(\S*?\d[\w.'/-]*) \1(?![\w.'/-])")
NUMBERS_ONLY_TITLE = re.compile(r"\d[\d.'/-]*(?: \d[\d.'/-]*)*")

# title-language: words of another language in a title: Dutch (YouTube's localised titles), and French, Spanish and
# German cues; English words, even "van" (Monster Van), are not listed
NON_ENGLISH = (r"(?i)(?<![A-Za-z])(het|een|voor|met|handleiding|nieuwe|nieuw|frisse|kies|gloednieuwe|garantie|"
               r"gebruikvoorzorgen|instructies|lijnen|onze|jouw|bekijk|guide de|fiche de|de référence|"
               r"réglage|instrucciones|démonstration|manual de|bedienungsanleitung|anleitung)(?![A-Za-z])")
# the document kinds that are a file the maker published in its own language: its title is that file's printed name
OWN_LANGUAGE_FILES = ("manual", "supplement", "setup_sheet", "part_list", "exploded_view", "catalog_pdf", "datasheet")

# service-pack-in-box: a service, rebuild or upgrade pack; a "(for use with #9080 upgrade kit)" clause names the kit
# the part works with, so it is no pack
SERVICE_PACK = re.compile(r"\b(service|rebuild|upgrade)\b.*\b(pack|kit|set)\b", re.I)
COMPAT_CLAUSE = re.compile(r"\(?\bfor use with\b[^()]*\)?|\bfits?\b.*$", re.I)

# body-manual-only: the manual of a body set sold apart from a chassis (Tamiya "51578 body parts set")
BODY_SET_DOC = re.compile(r"\bbody parts set\b|\bbody set\b|\bbody only\b|/spb-", re.I)

# the Horizon document kinds that are their own page (horizon-doc-no-page)
HORIZON_PAGE_KINDS = ("product_page", "owner_report", "video", "catalog")


def placeholder_title(title):
    t = (title or "").strip()
    return bool(PLACEHOLDER_TITLE.search(t)) or bool(NUMBERS_ONLY_TITLE.fullmatch(t))


def is_service_pack(name):
    return bool(SERVICE_PACK.search(COMPAT_CLAUSE.sub(" ", name or "")))


def is_body_set_doc(title, doc_id=""):
    return bool(BODY_SET_DOC.search((title or "") + " " + doc_id))


def unbalanced(s):
    """True when a name's brackets do not pair up (full-width brackets count): it was cut inside a bracket."""
    depth = 0
    for ch in s.replace("（", "(").replace("）", ")"):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return True
    return depth != 0


def norm_name(name):
    """A name or number in lower-case letters and digits, one space between the words."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", name.lower()).split())



# part-no-car-link: parts of brands that also sell aircraft, helicopters and drones (out of scope: no car to link).
# T2M's spare-part numbers start with the item code of the model ("T5190-01" is a part of T5190); each prefix is an
# aircraft, helicopter or drone item.
AIRCRAFT_PREFIXES = {"brand/t2m": frozenset(
    "T4511 T4515 T4516 T4517 T4518 T4519 T4520 T4521 T4522 T4523 T4524 T4531 T4540 T4549 T4578 T4588 T4591 T4594 T4599 "
    "T5120 T5130 T5146 T5157 T5158 T5161 T5166 T5167 T5170 T5172 T5175 T5176 T5180 T5181 T5184 T5187 T5188 T5189 T5190 "
    "T5191 T5192 T5194 T5195 T5196 T5197 T620 T621 T622 T624 T625".split())}


def is_aircraft_part(brand, number):
    """True for a part of an aircraft, helicopter or drone item (AIRCRAFT_PREFIXES)."""
    prefixes = AIRCRAFT_PREFIXES.get(brand)
    return bool(prefixes) and str("" if number is None else number).split("-")[0].upper() in prefixes


# near-duplicate-model: a real vehicle's model under two names in one make: the name without these words is the same
# (Actros 3363 and Actros 3363 GigaSpace). Colour, decoration and body words, chassis and kit codes are not the vehicle.
NEAR_DUP_WORDS = re.compile(r"\b(gigaspace|streamspace|classicspace|rtr|body|decoration|non[\s-]?deco|nondecoration|"
                            r"pick[\s-]?up|truck|190mm|tough[\s-]color|fcx\d*\w*|fsc\d*\w*|crc)\b")
# pairs that stay apart on purpose: the pick-up body of a model that also has its own name
NEAR_DUP_KEPT = {("Nissan", "sunny"), ("Toyota", "fj45"), ("Toyota", "landcruiser40")}


def near_dup_key(model):
    return re.sub(r"[^a-z0-9]+", "", NEAR_DUP_WORDS.sub(" ", model.lower()))


# release-suffix-twin: the tail that makes one item number the other plus a suffix (34902 / 34902D, 10428 / 10428-2)
SUFFIX_TAIL = re.compile(r"-\d{1,2}|-?[A-Za-z][A-Za-z0-9]{0,3}")


def number_relation(a, b):
    """True when one item number is the other plus a suffix (34902 / 34902D, 10428 / 10428-2)."""
    a, b = str(a or "").strip().upper(), str(b or "").strip().upper()
    if len(a) == len(b) or not a or not b:
        return False
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return (len(short) >= 5 and short[:5].isdigit() and long_.startswith(short)
            and SUFFIX_TAIL.fullmatch(long_[len(short):]) is not None)


def same_product_record(a, b):
    """Whether two release records name one product: the same barcode, or the same maker page with no other barcode."""
    if a.get("gtin") and b.get("gtin"):
        return str(a["gtin"]) == str(b["gtin"])
    sa, sb = a.get("released_source"), b.get("released_source")
    return bool(sa and sb and sa.lower().rstrip("/") == sb.lower().rstrip("/"))


# tamiya-*-no-link: a Tamiya record links its maker's page: the Tamiya product link (no kind), a kind maker link, or a
# kind archive capture of a tamiya.com or tamiyausa.com page. Dealer and fan-site links never count.
TAMIYA_CAPTURE = re.compile(r"^https?://web\.archive\.org/web/\d{14}\w*/https?://(?:www\.)?tamiya(?:usa)?\.com(?::\d+)?/")


def tamiya_maker_linked(links):
    for link in links or []:
        kind = link.get("kind")
        if (kind is None and link.get("site") == "Tamiya") or kind == "maker":
            return True
        if kind == "archive" and TAMIYA_CAPTURE.match(link.get("url", "")):
            return True
    return False


# hardware part categories (kit-box-few-hardware, the pack counts)
HW = ("bearing", "screw", "nut", "washer-shim", "clip", "pin", "ball-end", "o-ring-seal", "turnbuckle", "rod-end")

# too-many-diffs: a differential part that is a whole assembly by its name, not one of its cases, gears or cups
COMPLETE_DIFF = re.compile(r"\b(complete|assembled|assy|assembly|unit set)\b", re.I)
DIFF_PARTS = re.compile(r"\b(cases?|gears?|gearbox|cups?|joints?|gaskets?|shims?|o-?rings?)\b", re.I)


def complete_diff(category, name):
    return category == "differential" and bool(COMPLETE_DIFF.search(name or "")) and not DIFF_PARTS.search(name or "")


def twin_pairs(parts):
    """Records with the same number and the same normalised name under two different brands (part dicts with id,
    brand, name and number). A name that is only the number is no name, so such records never pair."""
    by_number = collections.defaultdict(list)
    for p in parts:
        if p.get("number") and p.get("name") and norm_name(p["name"]) != norm_name(str(p["number"])):
            by_number[p["number"]].append(p)
    out = []
    for ps in by_number.values():
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                if a["brand"] != b["brand"] and norm_name(a["name"]) == norm_name(b["name"]):
                    out.append((a, b))
    return out


def _host(url):
    host = urllib.parse.urlsplit(url or "").hostname or ""
    return host[4:] if host.startswith("www.") else host


# twin-parts: a pair that states different values for one of these measures is two products
TWIN_MEASURES = ("power_w", "weight_g", "dimensions_mm", "teeth", "kv", "diameter_mm", "length_mm", "width_mm", "shaft_mm")


def twin_class(a, b, brands, companies, docs):
    """shared: the brands are related (same owner, or one owns the other) and each record cites its own brand's source;
    also a pair where one record names the other in rebrand_of, or one that states different values for a measure.
    copy: a record's source or link is the other brand's site or one of its documents. unclear: anything else."""
    def sources(p):
        return list(p.get("documents", [])) + [e.get("source") for e in p.get("fits", []) + p.get("equivalent_to", [])]

    def cites(p, brand):
        site = _host(brands.get(brand, {}).get("website", ""))
        if any(docs.get(d, {}).get("brand") == brand for d in sources(p) if d):
            return True
        return bool(site) and any(_host(link.get("url")) == site for link in p.get("links", []))

    def related(x, y):
        ox, oy = brands.get(x, {}).get("owner"), brands.get(y, {}).get("owner")
        if ox and ox == oy:
            return True
        return any(companies.get(o, {}).get("brand") == other for o, other in ((ox, y), (oy, x)) if o)

    if any(r.get("part") in (a["id"], b["id"]) for x in (a, b) for r in x.get("rebrand_of", [])):
        return "shared"
    if any(k in a and k in b and a[k] != b[k] for k in TWIN_MEASURES):
        return "shared"
    if a["brand"] != b["brand"] and ((cites(a, b["brand"]) and not cites(a, a["brand"]))
                                     or (cites(b, a["brand"]) and not cites(b, b["brand"]))):
        return "copy"
    if related(a["brand"], b["brand"]) and cites(a, a["brand"]) and cites(b, b["brand"]):
        return "shared"
    return "unclear"


# spec-mismatch: a spec link (equivalent_to, or includes) whose spec family the part's category or name does not carry.
# A family's words are the ones a name uses for that kind of item; a link with a source (a page the maker or a store
# gave) is checked by its category only. A part's includes row for a family its category takes as an accessory is fine
# (a pinion with its set screws, a differential with its pins); any other family needs the name to name it.
SPEC_FAMILY_WORDS = {
    "bearing": r"bearings?|bush(?:ings?|es)?|busings?", "screw": r"screws?|bolts?|cap ?heads?|button ?heads?",
    "nut": r"nuts?", "washer": r"washers?|shims?|spacers?|collars?", "pin": r"pins?|shafts?|dowels?",
    "pinion": r"pinions?|gears?", "eclip": r"e-?clips?|e-?rings?|din ?6799", "circlip": r"c-?clips?|circlips?|seger|snap rings?",
    "ball-end": r"balls?|studs?|ball ?ends?|ball ?joints?", "o-ring": r"o-?rings?|gaskets?", "motor": r"motors?",
    "battery": r"batter(?:y|ies)|lipo|li-?po|nimh|packs?", "servo": r"servos?", "oil": r"oils?|grease|silicone",
    "wire": r"wires?|cables?|leads?", "connector": r"connectors?|plugs?|jst|xt\d*|ec\d|deans|bullets?|t-?plugs?|banana|xh|jr",
    "wheel-hex": r"hex(?:es)?|wheels?|tyres?|tires?|hubs?|axles?|rims?",
}
# the spec families a part of each category may hold as includes (its accessories); every other family needs its name
SPEC_INCLUDE_ACCESSORIES = {
    "gear": {"bearing", "pin", "screw", "washer", "nut", "o-ring", "eclip", "circlip"},
    "spur-gear": {"pin", "screw", "washer", "nut", "bearing"}, "pinion": {"screw", "pin", "washer"},
    "differential": {"bearing", "pin", "screw", "washer", "nut", "o-ring", "eclip", "circlip", "oil"},
    "drivetrain": {"bearing", "pin", "screw", "nut", "washer", "o-ring", "eclip", "circlip", "oil"},
    "steering": {"bearing", "screw", "nut", "washer", "ball-end", "pin", "eclip"},
    "bumper-guard": {"bearing", "screw", "nut", "washer"}, "body": {"screw", "nut", "washer", "pin", "eclip", "o-ring", "wire", "connector"},
    "body-accessory": {"screw", "nut", "washer", "pin", "eclip", "o-ring"}, "wing": {"screw", "nut", "washer"},
    "screw": {"washer", "nut"}, "nut": {"screw", "washer"}, "pin": {"screw"}, "washer-shim": {"screw", "nut", "pin", "washer"},
    "ball-end": {"nut", "screw", "washer", "ball-end"}, "clip": {"eclip", "circlip", "screw", "washer"},
    "shock": {"screw", "nut", "washer", "o-ring", "ball-end", "oil"}, "motor": {"screw", "wire", "connector", "pinion", "washer", "nut", "o-ring"},
    "esc": {"connector", "wire", "screw"}, "servo": {"screw", "connector", "wire", "washer", "nut", "pinion"},
    "charger": {"connector", "wire", "screw"}, "battery": {"connector", "wire", "screw"}, "radio": {"battery", "connector", "wire", "screw"},
    "chassis": {"bearing", "screw", "nut", "washer", "pin", "o-ring", "eclip", "circlip", "ball-end"},
    "suspension": {"bearing", "screw", "nut", "washer", "pin", "o-ring", "eclip", "circlip", "ball-end", "oil"},
    "wheel": {"bearing", "screw", "nut", "washer", "wheel-hex"}, "tire": {"screw", "nut", "washer", "wheel-hex"},
    "light": {"screw", "wire", "connector", "washer", "nut"}, "cooling": {"screw", "nut", "washer", "wire", "connector"},
}
# a fastener or small part the name itself lists ("Pins & M4 Nuts") may be an include on any category; a motor, battery or servo may not
SPEC_NAMED_HARDWARE = {"screw", "nut", "washer", "pin", "o-ring", "eclip", "circlip", "ball-end", "bearing"}
SPEC_DEFAULT_ACCESSORIES = {"screw", "nut", "washer"}   # any other category: fasteners it comes with
# the spec families a part of each category may be equivalent_to (validate.py's SPEC_PART_CATS, by family)
SPEC_EQUIVALENT_CATS = {
    "bearing": {"bearing"}, "screw": {"screw"}, "pin": {"pin"}, "pinion": {"pinion"}, "oil": {"oil-grease"},
    "battery": {"battery"}, "motor": {"motor"}, "servo": {"servo"}, "nut": {"nut"},
    "washer": {"washer-shim"}, "eclip": {"clip"}, "wire": {"wire"}, "circlip": {"clip"},
    "ball-end": {"ball-end"}, "o-ring": {"o-ring-seal"},
    "wheel-hex": {"drivetrain", "wheel", "tire", "suspension"},
}


GEAR_CATS = {"gear", "pinion", "spur-gear"}
GEAR_SET_NAME = re.compile(r"(?i)\b(gears|pinions|sets?)\b")   # "Pinion Gears 13T + Screws (2P)": several pieces, a count
PITCH_IN_NAME = re.compile(r"(?i)(?<![\w.])(\d{1,3})\s*(?:p|dp|pitch)\b")   # "(48P)", "48DP", "48 Pitch"


def gear_pitch_as_count(p):
    """Why a gear's pack_qty is its pitch, or None: the count equals the part's pitch_dp, or the pitch printed in its
    name ("90T SPUR GEAR (48P)"). A gear set's name ("Gears", "Set") states a count, so its printed number is no pitch.
    A pitch in a name is normal; only a count that equals it is the bug (tools#590 read "(48P)" as a count)."""
    pq = p.get("pack_qty")
    if pq is None or p.get("category") not in GEAR_CATS: return None
    if p.get("pitch_dp") == pq: return f"pack_qty {pq} is the pitch_dp"
    name = p.get("name") or ""
    if not GEAR_SET_NAME.search(name) and any(int(m.group(1)) == pq for m in PITCH_IN_NAME.finditer(name)):
        return f"pack_qty {pq} is the pitch printed in the name"
    return None

SPEC_KIT_NAME = re.compile(r"\b(?:rebuild|repair|maintenance|conversion)\b")


# hardware bought in packs: the pack tools' categories (tools/link_pack_qty.py PAGE_HARDWARE) and the name words of
# a bag of small items or a set (packqty SMALL, set, kit, pack, pair). A single turnbuckle or rod end needs no count.
PACK_SOLD_CATS = {"bearing", "screw", "nut", "washer-shim", "clip", "pin", "ball-end", "o-ring-seal", "turnbuckle", "rod-end"}
PACK_SOLD_NAME = re.compile(r"(?i)screw|bolt|clip|\bpins?\b|shim|washer|\bnuts?\b|locknut|\bballs?\b|bearing|bushing|sleeve"
                            r"|\bo[- ]?rings?\b|\be-?rings?\b|\bc-?rings?\b|rivet|spacer|collar|\bstuds?\b|\b(?:button|truss|countersunk|tapping|philips|grub)\b"
                            r"|\bsets?\b|\bkits?\b|\bpacks?\b|\bpairs?\b|\bbags?\b|\bassort\w*|\bcombo\b")


def sold_in_packs(p):
    """True when a hardware part is one of the small items sold in packs: its category and a name word of a bag or set."""
    return p.get("category") in PACK_SOLD_CATS and PACK_SOLD_NAME.search(p.get("name") or "") is not None


def count_unstated(p, brands):
    """True when the maker states no exact count for a kit: a minimum (the importer's "180+ pieces." note) or none (its brand has pack_counts = false)."""
    return re.match(r"\d+\+ pieces?\b", p.get("notes", "")) is not None or brands.get(p.get("brand"), {}).get("pack_counts") is False


def spec_mismatches(parts):
    """[(part id, field, spec id, reason)] for the spec links the part's category or name does not carry.

    equivalent_to: the family must be one the category holds (validate.py), and a rebuild or repair kit (its name
    says kit, set, rebuild) is never equivalent to the spec of the motor, screw or bearing it works on. includes: the
    family must be the part's own kind or an accessory its category comes with (a pinion with its set screws, a
    differential with its pins); a name that names another kind (a "MOTOR" on a decal) fails the category. A row with
    a source is checked by category only: the maker or store said it.
    """
    out = []
    for p in parts:
        name, cat = (p.get("name") or "").lower(), p.get("category")
        for field in ("equivalent_to", "includes"):
            for row in p.get(field) or []:
                bits = str(row.get("spec", "")).split("/")
                fam = bits[1] if len(bits) >= 3 else None
                if fam is None or cat is None or fam not in SPEC_FAMILY_WORDS or (field == "equivalent_to" and fam not in SPEC_EQUIVALENT_CATS):
                    continue
                own = cat in SPEC_EQUIVALENT_CATS.get(fam, ())
                named = re.search(r"(?<![a-z])(?:%s)(?![a-z])" % SPEC_FAMILY_WORDS[fam], name) is not None
                if field == "equivalent_to":
                    if not own:
                        out.append((p["id"], field, row["spec"], f"a {fam} spec on a {cat}"))
                    elif "source" not in row and SPEC_KIT_NAME.search(name) and not named:
                        out.append((p["id"], field, row["spec"], f"a {fam} spec on a kit that is not a {fam}"))
                elif not own and not (named and fam in SPEC_NAMED_HARDWARE) and "source" not in row and fam not in SPEC_INCLUDE_ACCESSORIES.get(cat, SPEC_DEFAULT_ACCESSORIES):
                    out.append((p["id"], field, row["spec"], f"a {fam} include on a {cat}"))
    return out


# wire-plug-no-connectors: a plug word in a lead's name
PLUG = re.compile(r"\b(plug|connector|bullet|xt\d*|deans|jr|t-plug|banana|jst|xh|ec\d)\b", re.I)
# battery-balance-name-no-connector: a battery name that states the JST-XH balance lead
BALANCE_NAME = re.compile(r"\bbalanc\w*[^,;|()]{0,30}\bjst[- ]?xhr?\b|\bjst[- ]?xhr?\b[^,;|()]{0,30}\bbalanc\w*", re.I)
# battery-accessory-name: an accessory (tape, lid, clasp ...) or a device named with its battery, filed as battery
BATTERY_ACCESSORY = re.compile(r"\b(tapes?|lids?|clasp|cups?|straps?|holders?|trays?|covers?|clamps?|plates?|mounts?|boosters?)\b", re.I)
BATTERY_ITSELF = re.compile(r"lipo|li-?po|nimh|li-?ion|\bpack\b|\d{3,5} ?mah", re.I)
# bearing-default-material: the name words of each bearing material
MAT_WORDS = {"steel": r"steel|chrom|hardened", "ceramic": r"ceramic", "stainless": r"stainless", "titanium": r"titan",
             "aluminium": r"alumin", "carbide": r"carbide", "brass": r"brass", "bronze": r"bronze",
             "plastic": r"plastic|nylon|delrin"}
# electronics-field-rare: the electronics fields the schema defines for each category
ELEC_FIELDS = {
    "motor": "motor_type kv turns lipo_cells diameter_mm length_mm shaft_mm weight_g sensored mount_holes motor_connector waterproof scales",
    "esc": "motor_type bec_v bec_a motor_limit_t motor_limit_kv nimh_cells programming resistance_mohm lipo_cells current_a peak_current_a "
           "dimensions_mm weight_g sensored motor_connector receiver_connector waterproof scales",
    "servo": "connector size_class spline_teeth torque_kgcm speed_s voltage_range gear_material motor rotation_deg bearings bearing_kind "
             "dead_band_us frequency_hz dimensions_mm weight_g waterproof scales",
    "battery": "chemistry cells capacity_mah nominal_v c_rating connector balance_connector case dimensions_mm weight_g scales",
}


def servo_plugs(p):
    """The servo plugs a part is linked to (its connector specs and plug names): JR, Futaba or both."""
    eq = {str(e.get("spec", "")) for e in p.get("equivalent_to", []) if isinstance(e, dict)}
    names = set(p.get("connectors", [])) | ({p["connector"]} if isinstance(p.get("connector"), str) else set())
    return (({"JR"} if "spec/connector/servo-jr" in eq or "JR" in names else set())
            | ({"Futaba"} if "spec/connector/servo-futaba" in eq or "Futaba" in names else set()))


def servo_named(p):
    """The one servo plug a part's name gives (Futaba, or a Futaba servo; JR, Hitec or universal), else None."""
    n = p.get("name", "")
    fut = bool(re.search(r"futaba|\bJ[- ]?plug", n, re.I)) or (p.get("brand") == "brand/futaba" and p.get("category") == "servo")
    jr = bool(re.search(r"\bJR\b|hitec|universal", n, re.I))
    return "Futaba" if fut and not jr else "JR" if jr and not fut else None


def kit_sum(p):
    """The sum of the includes qty of a hardware kit, or None when a row has no integer qty."""
    rows = p.get("includes") or []
    qtys = [r.get("qty") for r in rows]
    return sum(qtys) if rows and all(type(q) is int and q > 0 for q in qtys) else None


# banned-host: hosts never linked (House of RC, Tamico), and rcscrapyard image addresses; a tamico.de dealer link is
# allowed for Tamiya spares with no maker page, and Xtra Speed's two Tamico listing documents keep their address
BANNED_HOSTS = re.compile(r"https?://[^\s\"')]*(houseofrc|tamico)[^\s\"')]*", re.I)
SCRAP_IMG = re.compile(r"https?://[^\s\"')]*rcscrapyard[^\s\"')]*\.(jpe?g|png|gif|webp)", re.I)
TAMICO_OWNER_DOCS = "data/documents/xtra-speed/tamico-"
# local-path: a path on someone's computer or in the tools cache in place of a source's address
LOCAL_PATH = re.compile(r"(^|[\s\"'(=])(/home/|/Users/|/tmp/|file://|[A-Za-z]:\\|work/manuals/|cache/)")


def walk_strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from walk_strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from walk_strings(x)


# release-editions-not-grouped: colour, livery and named editions of one kit that share no `range`. The word lists
# and the edition, number and race-number rules are copied from hobbydex-tools tools/link_release_ranges.py (and the
# colour words from its tools/data/name_words.toml), the linker that writes the ranges; keep them in step.
EDITION_WORD = re.compile(r"[^\W_]+(?:[.][^\W_]+)*")
EDITION_RANGE_STOP = {
    "flux", "drift", "sport", "rtr", "arr", "kit", "brushless", "brushed", "combo", "lipo", "nimh", "evo", "pro", "v2",
    "v3", "v4", "ver", "version", "2wd", "4wd", "waterproof", "w", "with", "and", "bundle", "set", "pack", "edition",
    "limited", "special", "spec", "late", "early", "model", "type", "tuned", "mk", "gen", "body", "chassis", "wheels",
    "tires", "tyres", "tire", "radio", "battery", "charger", "readyset", "ready", "to", "run", "upgrade", "upgraded",
    "hop", "up"}
# editions that are another product (a chassis material, surface, class or a limited run), not a colour or livery
EDITION_STOP = {
    "limited", "special", "anniversary", "launch", "collector", "collectors", "deluxe", "standard", "premium", "first",
    "signature", "classic", "ultimate", "pro", "race", "racing", "competition", "comp", "trail", "elite", "champion",
    "championship", "tour", "team", "factory", "founder", "founders", "owner", "owners", "debut", "carbon",
    "graphite", "alu", "aluminium", "aluminum", "flex", "solid", "carpet", "dirt", "clay", "turf", "astro", "asphalt",
    "offroad", "onroad", "street", "track", "short", "long", "lwb", "swb", "lite", "light", "heavy", "max", "plus",
    "mini", "micro", "big", "small", "wide", "narrow", "lowered", "lifted", "scale", "basic", "starter", "beginner",
    "kids"}
EDITION_NUMBER_GAP = 50
EDITION_DAYS = 400
# colour words (name_words.toml [colour] base and material, link_release_ranges EXTRA_COLOURS) and the paint-name
# words around them (modifier, link_release_colours EXTRA_MOD and TRAIL)
RANGE_COLOURS = {
    "black", "white", "red", "blue", "green", "orange", "yellow", "pink", "purple", "violet", "grey", "gray", "silver",
    "gold", "golden", "gunmetal", "chrome", "clear", "silvery", "transparent", "smoke", "brown", "olive", "khaki",
    "tan", "turquoise", "magenta", "teal", "navy", "lime", "cyan", "cerulean", "bronze", "copper", "titanium"}
RANGE_COLOUR_MODS = {
    "light", "dark", "matte", "matt", "fluorescent", "fluo", "neon", "charcoal", "army", "sky", "metallic", "pearl",
    "gloss", "satin", "flat", "bright", "deep", "racing", "candy", "bahama", "lightning", "classic", "electric",
    "magic", "emerald", "daytona", "boost", "sunlight", "emotional", "platinum", "mint", "burnt", "slate", "iconic",
    "grayish", "greyish", "mica", "galaxy", "dust", "ii", "seafoam", "aqua", "gun", "metal"}
RACE_NUMBER = re.compile(r"^(?P<head>.*?)[\s,\-]*(?P<livery>(?:No\.?\s*\d+|#\s*\d+)(?!\w).*)$", re.I)
RACE_YEAR = re.compile(r"(?:19|20)\d\d")


def range_words(name):
    return [m.group().lower() for m in EDITION_WORD.finditer(name or "")]


def colour_clause(ws):
    """True when the words are a colour clause and nothing else: up to five colour and paint-name words (with "and"
    between colours), at least one a colour ("Imperial Blue", "black and red", "Matte Gun Metal")."""
    return (0 < len(ws) <= 5 and any(w in RANGE_COLOURS for w in ws)
            and all(w in RANGE_COLOURS or w in RANGE_COLOUR_MODS or w == "and" for w in ws))


def range_number(n):
    m = re.fullmatch(r"(.*?)(\d+)([A-Za-z]{0,2})", str(n or "").strip())
    return (m.group(1), int(m.group(2)), m.group(3), len(m.group(2))) if m else None


def colour_numbers_near(a, b):
    """Item numbers of one colour range (link_release_ranges near): one pattern and up to 10 apart (161300 /
    161301), the same number with another colour code (30615C / 30615R), or one stem with letter tails of up to
    four (118N02BDBK / 118N02BDGY)."""
    a, b = str(a or "").strip(), str(b or "").strip()
    pa, pb = range_number(a), range_number(b)
    if pa and pb:
        return pa[0] == pb[0] and pa[3] == pb[3] and (pa[1] == pb[1] or (pa[2] == pb[2] and abs(pa[1] - pb[1]) <= 10))
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    ta, tb = a[n:], b[n:]
    return (n >= 6 and any(c.isdigit() for c in a[:n]) and ta.isalpha() and tb.isalpha() and len(ta) <= 4
            and len(tb) <= 4 and ta != tb)


def site_colour_code(n):
    """(pattern, stem) of an item number whose colour code the site's colour-sibling rule reads
    (hobbydex src/lib/colourSiblings.ts numberParts): BRS-YW, 34118T1S, 30615C; else None."""
    n = str(n or "").replace(" ", "").upper()
    for pattern, rx in (("dash", r"(.*[A-Z0-9])-[A-Z]{2,3}"), ("type", r"(.*\d)T\dS?"), ("letter", r"(.*\d)[A-Z]{1,2}")):
        m = re.fullmatch(rx, n)
        if m:
            return pattern, m.group(1)
    return None


def colour_diff(a, b):
    """The colour clauses of two names that are equal but for one colour clause each (or one name without it:
    the base release), or None. The names must share at least two words."""
    wa, wb = range_words(a), range_words(b)
    n = 0
    while n < min(len(wa), len(wb)) and wa[n] == wb[n]:
        n += 1
    m = 0
    while m < min(len(wa), len(wb)) - n and wa[-1 - m] == wb[-1 - m]:
        m += 1
    da, db = wa[n:len(wa) - m], wb[n:len(wb) - m]
    if n + m < 2 or da == db or not (da or db):
        return None
    if not all(colour_clause(d) for d in (da, db) if d):
        return None
    return " ".join(da), " ".join(db)


def edition_diff(a, b):
    """The edition texts of two names that differ only in the one or two words before their one "Edition"
    (link_release_ranges edition_diff: Nebula / Supernova Edition), or None; Limited, Founder's, Graphite and the
    other EDITION_STOP editions are other products."""
    wa, wb = range_words(a), range_words(b)
    ia = [i for i, w in enumerate(wa) if w == "edition"]
    ib = [i for i, w in enumerate(wb) if w == "edition"]
    if len(ia) != 1 or len(ib) != 1 or not ia[0] or not ib[0]:
        return None
    ia, ib = ia[0], ib[0]
    if wa[ia:] != wb[ib:]:
        return None
    n = 0
    while n < min(ia, ib) and wa[n] == wb[n]:
        n += 1
    da, db = wa[n:ia], wb[n:ib]
    if not (1 <= len(da) <= 2 and 1 <= len(db) <= 2) or da == db or n < 2:
        return None
    if any(w in EDITION_RANGE_STOP or w in EDITION_STOP or re.search(r"\d", w) for w in da + db):
        return None
    return " ".join(da) + " edition", " ".join(db) + " edition"


def race_split(name):
    """(head words, livery) of a race-numbered name ("... Jaguar XJR-14 No.17 SUGO 1991"), or None
    (link_release_ranges race_split: the race number plus up to four event, year or result words)."""
    m = RACE_NUMBER.match((name or "").strip())
    if not m or re.search(r"[()\"]", m.group("head")):
        return None
    head, livery = range_words(m.group("head")), m.group("livery").strip(" -,")
    tail = range_words(re.sub(r"^(?:No\.?\s*\d+|#\s*\d+)", "", livery, flags=re.I))
    if (len(head) < 2 or len(tail) > 4 or re.search(r"[()\"]", livery)
            or any(w in EDITION_RANGE_STOP or (re.search(r"\d", w) and not RACE_YEAR.fullmatch(w)) for w in tail)):
        return None
    return head, livery


def race_diff(a, b):
    """The liveries of two race-numbered names with the same words before the race number, or None."""
    ra, rb = race_split(a), race_split(b)
    if not ra or not rb or ra[0] != rb[0] or ra[1].lower() == rb[1].lower():
        return None
    ya, yb = ({int(w) for w in range_words(r[1]) if RACE_YEAR.fullmatch(w)} for r in (ra, rb))
    return None if ya and yb and ya != yb else (ra[1], rb[1])


def stem_close(a, b):
    """Item numbers sharing a stem of five or more characters (three digits) that add up to three each:
    32369S17 / 32369LE."""
    a, b = str(a or "").strip().upper(), str(b or "").strip().upper()
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return a != b and n >= 5 and sum(c.isdigit() for c in a[:n]) >= 3 and len(a) - n <= 3 and len(b) - n <= 3


# reissue markers: a name with one of these words (or a year in brackets, "(2026)") that the other name lacks is a
# re-release, never a launch variant (Kyosho Javelin 30618 vs Legendary Series Javelin 30618C)
REISSUE_WORD = re.compile(r"(?i)\bre-?releases?d?\b|\bre-?issues?d?\b|\blegendary\b|\bclassic\b|\banniversary\b"
                          r"|\bvintage\b|\brevival\b|\(\s*(?:19|20)\d\d\s*\)")
# variants come to market together (one announcement, one listing): dates of month or day precision this close
MARKET_DAYS = 90
# race-numbered liveries of one car come out over a year (Kyosho XJR-14 1991: February and December 2026): one range
# (owner, 2026-11-18; hobbydex-tools link_release_ranges RACE_MARKET_DAYS)
LIVERY_MARKET_DAYS = 365


def range_day(r):
    """(day number, precise) of a release's first date (released, announced, seen_by, then year): precise when it
    names the month."""
    for f in ("released", "announced", "seen_by", "year"):
        m = re.match(r"(\d{4})(?:-(\d\d))?(?:-(\d\d))?", str(r.get(f) or ""))
        if m:
            day = (int(m.group(1)) * 12 + int(m.group(2) or 7) - 1) * 30.44 + int(m.group(3) or 1)
            return day, m.group(2) is not None
    return None


def reissue_marks(name):
    return {m.group().lower().replace("-", "") for m in REISSUE_WORD.finditer(name or "")}


def rerelease_targets(r):
    rel = r.get("related") or []
    return {x.get("release") for x in rel if isinstance(x, dict) and x.get("relation") == "rerelease-of"}


def market_bucket(a, b, days=MARKET_DAYS):
    """How two name-matched releases came to market: "together" (dates of month precision at most `days`
    apart: one launch, so one range), "apart" (a re-release: a reissue word or bracketed year only one name has,
    a supersedes or rerelease-of link between them, or re-releases of different originals) or "review" (dates far apart or unknown, no reissue marker: a
    person decides)."""
    if reissue_marks(a.get("name")) != reissue_marks(b.get("name")):
        return "apart"
    ra, rb = rerelease_targets(a), rerelease_targets(b)
    if (a.get("supersedes") in (b.get("id"),) or b.get("supersedes") in (a.get("id"),) or b.get("id") in ra
            or a.get("id") in rb or bool(ra) != bool(rb) or ra != rb):
        return "apart"
    da, db = range_day(a), range_day(b)
    if da and db and da[1] and db[1] and abs(da[0] - db[0]) <= days:
        return "together"
    return "review"


def edition_pair(a, b):
    """Why two releases of one brand, kit, kind and scale read as editions of one range by name and item number
    ("colour", "edition" or "livery" with the two texts), or None. a and b are dicts with name, number and
    depicts. Whether they came to market together is market_bucket's."""
    if not a.get("number") or not b.get("number") or str(a["number"]).strip() == str(b["number"]).strip():
        return None
    da, db = a.get("depicts") or {}, b.get("depicts") or {}
    if any(da.get(f) and db.get(f) and str(da[f]).lower() != str(db[f]).lower() for f in ("make", "model")):
        return None
    e = edition_diff(a["name"], b["name"])
    if e:
        pa, pb = range_number(a["number"]), range_number(b["number"])
        if (pa and pb and pa[0] == pb[0] and pa[3] == pb[3] and pa[2] == pb[2]
                and abs(pa[1] - pb[1]) <= EDITION_NUMBER_GAP):
            return ("edition",) + e
        return None
    r = race_diff(a["name"], b["name"])
    if r:
        return ("livery",) + r if stem_close(a["number"], b["number"]) else None
    c = colour_diff(a["name"], b["name"])
    if not c or not colour_numbers_near(a["number"], b["number"]):
        return None
    sa, sb = site_colour_code(a["number"]), site_colour_code(b["number"])
    if sa and sa == sb and all(c):
        return None   # the site pairs these by item number and name already (colourSiblings.ts)
    return ("colour",) + c


# fits-scale-contradicts-kit: a vehicle scale a listing states ("1/16", "1:16", "1/12th"); an inch size ("1/8 in",
# '1/8"') is no scale
LISTED_SCALE = re.compile(r'(?<![\d./])1\s*[/:]\s*(5|6|7|8|10|12|14|16|18|24|28|32|35|36|43)(?:th)?(?![\d"]|\s*(?:in|inch)\b)', re.I)
# the items of a listed car list ("1/18 4WD Temper, 1.9 Barrage"): each item may name a car of its own scale
LISTED_ITEM = re.compile(r"\s*(?:,|;|&|\band\b|/(?!\d))\s*", re.I)
# drive, power and package words a kit name carries beside the car's own name ("1/16 Slash 4X4" is the Slash)
KIT_TRIM = re.compile(r"\b(?:4x4|4wd|2wd|vxl|brushless|brushed|rtr|edition)\b", re.I)


def listed_scales(text):
    """The scales a listing states, as "1/N"."""
    return {"1/" + m for m in LISTED_SCALE.findall(text or "")}


def item_scales_contradict(text, kit_scale):
    """True when every item of a listed car text states a scale and none of them is the kit's ("1/18 Ruckus 4WD" for
    a 1/10 kit). An item with no scale may be the kit's car, so it contradicts nothing."""
    per = [listed_scales(x) for x in LISTED_ITEM.split(text or "") if x.strip()]
    return bool(kit_scale) and bool(per) and all(per) and kit_scale not in set().union(*per)


def kit_words(name):
    """The words of a kit's name without its scale and its drive, power and package words."""
    return set(re.findall(r"[a-z0-9]+", KIT_TRIM.sub(" ", re.sub(r"^\d+/\d+\s+", "", name or "")).lower()))


def scaled_name_scales(text, kit_name, brand=""):
    """The scales the text states right before a kit's whole name ("1/16 Mini Slash", "1:16 scale Traxxas Mini
    Slash", the brand word optional): the text names that car at that scale."""
    words = (kit_name or "").split()
    if not words:
        return set()
    name = r"[\s-]+".join(map(re.escape, words))
    make = r"(?:" + r"[\s-]+".join(map(re.escape, brand.split())) + r"\s+)?" if brand.strip() else ""
    rx = r"(?<![\d./])1\s*[/:]\s*(\d+)(?:th)?\s+(?:scale\s+)?" + make + name + r"(?![a-z0-9])"
    return {"1/" + m.group(1) for m in re.finditer(rx, text or "", re.I)}


# dimension-plausible: a car's figures times its scale divisor give the full-size figure, which lies in these bounds
# (millimetres; weight in grams times the divisor cubed). They catch a wrong unit or a misread digit, not a fine error.
DIM_FULL_SIZE = {"wheelbase_mm": (800, 9000), "track_mm": (400, 5000), "track_front_mm": (400, 5000),
                 "track_rear_mm": (400, 5000), "length_mm": (1000, 25000), "width_mm": (500, 6000),
                 "height_mm": (300, 6000), "ground_clearance_mm": (20, 1500), "weight_g": (1e5, 1e8)}


def dim_values(v):
    """The numbers of a dimension value: a number, a range { min, max } or a list of { mm, label } options."""
    if isinstance(v, bool):
        return []
    if isinstance(v, (int, float)):
        return [v]
    if isinstance(v, dict):
        return [x for x in (v.get("min"), v.get("max")) if isinstance(x, (int, float))]
    if isinstance(v, list):
        return [o["mm"] for o in v if isinstance(o, dict) and isinstance(o.get("mm"), (int, float))]
    return []


def scale_divisor(scale):
    m = re.fullmatch(r"1/(\d+(?:\.\d+)?)", str(scale or "").strip())
    return float(m.group(1)) if m else None


def dimension_problems(dims, scale):
    """What is implausible in a dimensions table (or a body's wheelbase and track) for a car of this scale: a figure
    whose full-size equivalent is out of DIM_FULL_SIZE, a wheelbase longer than the car, a track more than 5 % wider than the car."""
    out = []
    n = scale_divisor(scale)
    for k, (lo, hi) in DIM_FULL_SIZE.items():
        for x in dim_values(dims.get(k)):
            full = x * (n ** 3 if k == "weight_g" else n) if n else None
            if full is not None and not lo <= full <= hi:
                out.append(f"{k} {x:g} at {scale} is {full:g} full size, outside {lo:g}..{hi:g}")
    wb, ln, wd = dim_values(dims.get("wheelbase_mm")), dim_values(dims.get("length_mm")), dim_values(dims.get("width_mm"))
    if wb and ln and min(wb) > max(ln):
        out.append(f"wheelbase {min(wb):g} mm longer than the length {max(ln):g} mm")
    tracks = [x for k in ("track_mm", "track_front_mm", "track_rear_mm") for x in dim_values(dims.get(k))]
    if tracks and wd and min(tracks) > 1.05 * max(wd):   # a track measured over the tyres may equal the width
        out.append(f"track {min(tracks):g} mm wider than the width {max(wd):g} mm")
    return out
