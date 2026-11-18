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
