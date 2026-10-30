"""Validate every TOML file under data/.

Checks: file parses, the file is where tools/layout.py puts its id, required
fields per entity kind, every reference resolves, no duplicate ids, no two paths
that differ only in case. Also the art under art/ (see check_art). Exit code 1 on any error.

Run from the repo root: python3 -I tools/validate.py
"""
import datetime, os, re, sys, tomllib, unicodedata, urllib.parse
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import ART_KINDS, DIRS, art_path, path_for

ROOT = "data"
ART_ROOT = "art"
ART_MAX = 4096   # bytes per art file
SVG_NS = "http://www.w3.org/2000/svg"
PATH_DATA = re.compile(r"[MmLlHhVvCcSsQqTtAaZz0-9.,+\-eE ]+")
REQUIRED = {
    "brand": ["id", "name", "status"],
    "kit": ["id", "brand", "name", "category"],
    "release": ["id", "kit", "brand", "name", "status"],   # kind and year: optional, left out when no source states them
    "part": ["id", "brand", "name"],   # number: required unless the brand has item_numbers = false
    "spec": ["id", "category"],
    "doc": ["id", "kind", "title"],
    "shop": ["id", "name", "status"],
    "category": ["id", "name"],
    "standard": ["id", "code", "title"],
    "company": ["id", "name"],
    "make": ["id", "name", "country", "notes"],   # a real vehicle make (docs/schema.md "Makes"); one file per VEHICLE_MAKES entry
}
KINDS = {k: dict(dir=DIRS[k], required=REQUIRED[k]) for k in REQUIRED}
REFS = {  # field -> expected id prefix
    "brand": "brand/", "kit": "kit/", "part": "part/", "spec": "spec/", "source": "doc/",
    "publisher": ("brand/", "company/"), "replaces": "part/", "supersedes": "part/", "replaced_by": "standard/",
    "owner": "company/", "parent": "company/",
}
LIST_REFS = {"documents": "doc/", "releases": "release/", "requires": "", "kits": "kit/", "parts": "part/"}   # requires: kit or release ids, checked above
# real vehicle makes a release or body shell may depict (docs/schema.md "release", depicts); curated, add a make here first
VEHICLE_MAKES = {
    "Abarth", "Acura", "Alfa Romeo", "Alpine", "Aston Martin", "Audi", "BMW", "Bentley", "Bugatti", "Buggyra", "Buick", "Cadillac",
    "Can-Am", "Caterpillar", "Chevrolet", "Citroen", "DAF", "Datsun", "DeLorean", "Dodge", "Ducati", "Ferrari", "Fiat", "Ford",
    "Freightliner", "GMC", "Hino", "Honda", "Hummer", "Hyundai", "International", "Isuzu", "Iveco", "Jaguar", "Jeep", "KTM",
    "Kawasaki", "Kenworth", "Komatsu", "Lamborghini", "Lancia", "Land Rover", "Lexus", "Liebherr", "Lotus", "MAN", "Mack",
    "Maserati", "Mazda", "McLaren", "Mercedes-Benz", "Mini", "Mitsubishi", "Nissan", "Opel", "Pagani", "Peterbilt", "Peugeot",
    "Plymouth", "Polaris", "Pontiac", "Porsche", "Ram", "Renault", "Scania", "Seat", "Shelby", "Skoda", "Subaru", "Suzuki",
    "Toyota", "Tyrrell", "UAZ", "Vauxhall", "Volkswagen", "Volvo", "Willys", "Yamaha",
    "Allison", "General Dynamics", "Henschel", "Krauss-Maffei", "Krupp", "MIAG", "Mitsubishi Heavy Industries",  # military vehicle makers (decisions.md 2026-10-20)
}
SOURCE_DATE_FIELDS = {"released", "announced", "year", "model_year", "seen_by", "launched", "ended", "owner", "owner_since"}   # dates and dated facts keep their own *_source fields
SURFACES = {"carpet", "astro", "clay", "dirt", "asphalt", "high-grip"}   # the track surface a race kit is built for

DOUBTABLE = {"release": ("released", "year", "announced"), "brand": ("launched", "ended")}   # dates that may carry <field>_doubt

# scale as a fraction of the real vehicle: "1/10", "1/13.5" (docs/schema.md "kit", "release")
SCALE_RE = re.compile(r"1/\d+(\.\d+)?")
PRINTED_KINDS = {"manual", "supplement", "part_list", "exploded_view", "setup_sheet", "catalog"}
# links: kind (none = the maker's product page); archive = a Wayback capture of a page that is gone (docs/schema.md "links")
LINK_KINDS = {"fan-site", "press", "dealer", "maker", "archive"}
ARCHIVE_URL = re.compile(r"https://web\.archive\.org/web/\d{14}/https?://.+")
YOUTUBE_CHANNEL = re.compile(r"https://www\.youtube\.com/@[A-Za-z0-9._-]+")

ENUMS = {
    "release.status": {"announced", "released", "discontinued"},
    "release.kind": {"kit", "rtr", "arr", "roller", "print"},
    "release.color_source": {"owner"},   # who states a colour the name does not give (docs/schema.md "release", color)
    # kit types (docs/schema.md "kit"); the site gives each a label and an icon (hobbydex src/lib/kitTypes.ts)
    "kit.category": {"buggy", "truggy", "stadium-truck", "short-course", "monster", "desert-truck", "truck", "tractor-truck", "race-truck",
                     "crawler", "touring", "formula", "pan-car", "rally", "street-basher", "drift", "drag", "lowrider", "trailer",
                     "speed-run", "kart", "motorcycle", "snowmobile", "tank", "construction", "car", "boat", "oval", "gt", "on-road"},
    # kit drive (docs/schema.md "kit"); tracks: tanks and other tracked vehicles, half-tracks included
    "kit.drive": {"2wd", "4wd", "6wd", "8wd", "fwd", "tracks"},
    "brand.status": {"active", "dormant", "gone"},
    "company.status": {"active", "dormant", "gone"},
    "contains.role": {"kit", "option", "listed"},
    # generic items a release needs from outside the box (docs/schema.md "release", needs); a part is named by part instead
    "needs.item": {"radio", "receiver", "servo", "esc", "motor", "engine", "battery", "charger", "pinion", "tyres", "wheels", "body", "paint", "glue", "fuel", "glow-starter", "tools"},
    "doc.kind": {"manual", "part_list", "exploded_view", "supplement", "catalog", "setup_sheet", "product_page", "news", "owner_report", "video"},
    "equivalent_to.match": {"exact", "functional", "close"},
    "fits.type": {"direct", "replaces", "modification"},
    "rebrand_of.parts": {"interchangeable", "partly", "unknown"},
    "related.relation": {"requires", "fits", "use-with", "for", "replaces", "same-colour"},
    "same_platform_as.parts": {"interchangeable", "partly", "unknown"},
    "part.material": {"steel", "stainless", "titanium", "aluminium", "brass", "bronze", "plastic", "carbon", "ceramic", "carbide", "unknown"},
    # where a pack_qty came from (docs/schema.md "part"); photo and photos are lower confidence than the text bases
    "part.pack_qty_basis": {"name", "page", "includes", "manual", "photo", "photos", "owner"},
    # where a shell's thickness_mm or a body's width_mm came from (docs/schema.md, bodies)
    # why a part is universal (docs/schema.md "part", universal): the maker says so; the category is inherently universal; sold by size or spec
    "part.universal_basis": {"maker", "category", "size"},
    "part.thickness_basis": {"name", "page", "manual", "flyer", "owner"},
    "part.width_basis": {"name", "page", "manual", "flyer", "owner"},
    "part.status": {"available", "discontinued"},   # docs/schema.md "part"; set only where the maker or a shop states it
    "part.category_source": {"curated", "fallback", "manual-section", "photo", "llm"},   # fallback: misc, a part no rule places; manual-section: a section of the maker's manual; photo: read from its product photo; llm: read from its name by a text model (docs/schema.md "category")
    "part.seal": {"open", "metal", "rubber", "rubber-metal"},
    "part.insulation": {"silicone", "pvc", "teflon"},   # wire parts (docs/schema.md "Wires")
    "part.lubricant": {"oil", "grease"},
    "part.viscosity": {"thin", "medium", "thick"},
    "spec.profile": {"regular", "thin"},
    "spec.shape": {"flat", "countersunk", "conical"},   # washer specs (docs/schema.md "Washer specs")
    "spec.variant": {"bowed"},   # e-clip specs (docs/schema.md "E-clip specs")
    "spec.motor_type": {"brushed", "brushless"},
    "part.motor_type": {"brushed", "brushless", "both"},   # ESCs (docs/schema.md "ESCs")
    "spec.chemistry": {"lipo", "lihv", "life", "nimh"},
    "part.chemistry": {"lipo", "lihv", "life", "nimh", "liion"},
    "part.case": {"hard", "soft", "shorty"},
    "part.name_source": {"ocr", "manufacturer", "manual", "dealer", "owner"},
    "part.ball_type": {"stud", "nut", "through-hole", "set-screw"},
    "part.paint_type": {"polycarbonate", "lacquer", "acrylic", "enamel"},
    "part.application": {"spray-can", "airbrush", "brush", "marker"},
    "part.paint_role": {"paint", "clear", "primer", "thinner", "cleaner", "masking"},
    "part.fuel": {"nitro", "gasoline"},
    # what a radio part is (docs/schema.md "documents"): set = a transmitter sold with its receiver
    "part.radio_unit": {"transmitter", "receiver", "set", "gyro"},
    "part.shock_part": {"complete", "body", "shaft", "piston", "cap", "rebuild-kit", "rod-end", "spring-cup"},
}
ENUMS["release.category"] = ENUMS["kit.category"]   # a release's kit type override (docs/schema.md "release", category)
# engine fields (docs/schema.md "Engines"): only on engine-fuel parts, numbers in these ranges
# servo spec fields (docs/schema.md "Servos"): bearings, bearing_kind, dead_band_us, frequency_hz
SERVO_FIELDS = ("bearings", "bearing_kind", "dead_band_us", "frequency_hz")
SERVO_BEARING_KIND = {"ball", "bushing"}
ESC_PROP_FIELDS = ("motor_type", "bec_v", "bec_a", "motor_limit_t", "motor_limit_kv", "nimh_cells", "programming", "resistance_mohm")   # docs/schema.md "ESCs"
# waterproof: the maker's wording on these categories; scales: the vehicle scales a maker names for an electronic part (docs/schema.md "scales")
WATERPROOF_CATEGORIES = ("esc", "motor", "servo", "radio")
SCALES_CATEGORIES = ("esc", "motor", "servo", "battery")
# receiver_connector: the servo plug on an ESC or light controller's lead to the receiver (docs/schema.md "ESCs")
RECEIVER_CATEGORIES = ("esc", "light")
RECEIVER_PLUGS = {"JR", "Futaba", "JR/Futaba"}
ESC_PROGRAMMING = {"card", "box", "app", "bluetooth", "wifi", "buttons", "transmitter"}
ENGINE_NUM = {"displacement_cc": (0.5, 120), "bore_mm": (5, 60), "stroke_mm": (5, 60), "output_hp": (0.05, 20), "output_rpm": (1000, 60000)}
ENGINE_FIELDS = set(ENGINE_NUM) | {"engine_class", "rpm_range", "fuel"}   # bore_mm is also a shock's bore: checked on engines only
PAINT_FINISH = {"gloss", "flat", "semi-gloss", "metallic", "pearl", "fluorescent", "translucent", "clear", "chrome", "flake"}   # part.finish of a paint; other parts' finish ("black oxide") is free

# spec.type per spec category (docs/schema.md: bearing types, nut types)
SPEC_TYPES = {
    "bearing": {"radial-ball", "flanged", "thrust"},
    "pin": {"screw"},   # screw pins: a smooth pin with a head and a short thread (docs/schema.md "Pin specs")
    "nut": {"hex", "nylon-lock", "metal-lock", "lock", "flanged", "flanged-lock", "flanged-nylon-lock", "serrated-flange",
            "serrated-flange-nylon-lock", "dome", "flanged-dome", "square", "knurled", "wing", "wheel"},
    "ball-end": {"stud", "nut", "through-hole", "set-screw"},   # docs/schema.md "Ball-end specs"
}
NUT_PROFILED = {"hex", "nylon-lock", "metal-lock", "lock"}   # the types that come in a regular and a thin height

# which part categories may be `equivalent_to` a spec of each kind
SPEC_PART_CATS = {
    "bearing": {"bearing"}, "screw": {"screw"}, "pin": {"pin"}, "pinion": {"pinion"}, "oil": {"oil-grease"},
    "battery": {"battery"}, "motor": {"motor"}, "servo": {"servo"}, "nut": {"nut"},
    "washer": {"washer-shim"}, "eclip": {"clip"}, "wire": {"wire"}, "circlip": {"clip"},
    "ball-end": {"ball-end"}, "o-ring": {"o-ring-seal"},
    "wheel-hex": {"drivetrain", "wheel", "tire", "suspension"},   # hexes, wheels and tyres with a hex, hubs and axles
}

SIZE_SPEC_CATS = {"ball-end", "o-ring", "circlip"}   # specs keyed by one size, written by tools/link_*_specs.py


def size_spec_problems(path, d):
    """Problems with a ball-end, O-ring or circlip spec: its size fields, and the id they are keyed by."""
    cat, out = d["category"], []
    if cat == "ball-end":
        b, t = d.get("ball_mm"), d.get("type")
        if not isinstance(b, (int, float)) or isinstance(b, bool) or not 3 <= b <= 14:
            return [f"{path}: ball-end spec needs ball_mm, the ball diameter (3 to 14 mm)"]
        if t not in SPEC_TYPES["ball-end"]:
            return [f"{path}: ball-end spec needs type, one of {sorted(SPEC_TYPES['ball-end'])}"]
        sid = f"spec/ball-end/{g(b)}mm-{t}" + (f"-{d['thread'].lower()}" if "thread" in d else "") + (f"-h{g(d['height_mm'])}" if "height_mm" in d else "")
        if d["id"] != sid:
            out.append(f"{path}: ball-end spec id should be {sid} (ball, type, then thread and height)")
        if "thread" in d and not re.fullmatch(r"M[2-6](\.\d)?", str(d["thread"])):
            out.append(f"{path}: ball-end thread {d['thread']!r} should be M2 to M6 (a metric diameter)")
    elif cat == "o-ring":
        i, c = d.get("inner_mm"), d.get("cross_mm")
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (i, c)) or not 0 < c < i:
            return [f"{path}: o-ring spec needs inner_mm and cross_mm, the section thinner than the inner diameter"]
        if d["id"] != f"spec/o-ring/{g(i)}x{g(c)}":
            out.append(f"{path}: o-ring spec id should be spec/o-ring/{g(i)}x{g(c)} (inner, then cross section)")
    elif cat == "circlip":
        s_, t = d.get("shaft_mm"), d.get("thickness_mm")
        if not isinstance(s_, (int, float)) or isinstance(s_, bool) or not 1 <= s_ <= 30:
            return [f"{path}: circlip spec needs shaft_mm (1 to 30 mm)"]
        sid = f"spec/circlip/{g(s_)}mm" + (f"-{g(t)}" if t is not None else "")
        if d["id"] != sid:
            out.append(f"{path}: circlip spec id should be {sid} (shaft, then thickness)")
    return out


def g(v):
    """A size as the spec ids write it: 4.0 is 4."""
    return str(int(v)) if float(v).is_integer() else f"{float(v):g}"


def categories():
    """Part categories are the files in data/categories (category/<slug>)."""
    d = os.path.join(ROOT, "categories")
    return {f[:-5] for f in os.listdir(d) if f.endswith(".toml")} if os.path.isdir(d) else set()

def check_case_clashes(errors):
    """Two paths under data/ or art/ that differ only in case (GE/ and Ge/, SG-M3x8 and
    SG-M3X8) cannot both exist in a checkout on a case-insensitive filesystem (macOS, Windows)."""
    seen = {}
    for top in (ROOT, ART_ROOT):
        for dirpath, dirs, files in os.walk(top):
            for name in dirs + files:
                path = os.path.join(dirpath, name)
                other = seen.setdefault(path.lower(), path)
                if other != path:
                    errors.append(f"{path}: differs only in case from {other}; a case-insensitive filesystem cannot hold both")

def make_slug(name):
    """The site's makeSlug (hobbydex src/lib/data.ts): the make's name as a URL part."""
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", name.lower())).strip("-")

RELEASE_RELATIONS = {"rerelease-of"}   # release `related` relations; more are added as needed (docs/schema.md "related")


def _release_date(d):
    """(year, month, day) of a release from `released` (YYYY, YYYY-MM or YYYY-MM-DD) or `year`; None when neither is set."""
    r = d.get("released")
    if isinstance(r, str) and re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", r):
        p = [int(x) for x in r.split("-")]
        return tuple(p + [0] * (3 - len(p)))
    if isinstance(d.get("year"), int):
        return (d["year"], 0, 0)
    return None


def check_release_related(docs, errors):
    rels = {d["id"]: d for _, kind, d in docs if kind == "release"}
    for path, kind, d in docs:
        if kind != "release" or "related" not in d:
            continue
        rows = d["related"]
        if not isinstance(rows, list) or not rows:
            errors.append(f"{path}: related should be a non-empty list")
            continue
        for i, row in enumerate(rows):
            if not isinstance(row, dict) or set(row) != {"release", "relation", "source"}:
                errors.append(f"{path}: related[{i}] should have exactly release, relation and source")
                continue
            if row["relation"] not in RELEASE_RELATIONS:
                errors.append(f"{path}: related[{i}].relation {row['relation']!r} not in {sorted(RELEASE_RELATIONS)}")
            tgt = row["release"]
            if not isinstance(tgt, str) or not tgt.startswith("release/"):
                errors.append(f"{path}: related[{i}].release {tgt!r} should be a release id")
            elif tgt == d.get("id"):
                errors.append(f"{path}: related[{i}] links the release to itself")
            elif tgt not in rels:
                errors.append(f"{path}: related[{i}].release -> {tgt} does not exist")
            else:
                t = rels[tgt]
                if t.get("brand") != d.get("brand"):
                    errors.append(f"{path}: related[{i}] points to another brand ({t.get('brand')})")
                a, b = _release_date(d), _release_date(t)
                if a and b and not b < a:
                    errors.append(f"{path}: related[{i}] -> {tgt} is not older ({'-'.join(map(str, b))} vs {'-'.join(map(str, a))})")
            if not isinstance(row["source"], str) or not row["source"].strip():
                errors.append(f"{path}: related[{i}].source should name the page that says so (doc id or URL)")


def check_release_ranges(docs, errors):
    """Releases sharing a `range` are one car in versions that differ in colour or livery: same brand, kit and
    kind, at least two of them (docs/schema.md "release")."""
    by = {}
    for path, kind, d in docs:
        if kind == "release" and isinstance(d.get("range"), str):
            by.setdefault(d["range"], []).append((path, d))
    for rg, rows in by.items():
        if len(rows) < 2:
            errors.append(f"{rows[0][0]}: range {rg!r} holds only this release")
        for path, d in rows:
            for f in ("brand", "kit", "kind"):
                if d.get(f) != rows[0][1].get(f):
                    errors.append(f"{path}: range {rg!r} mixes {f} {d.get(f)!r} with {rows[0][1].get(f)!r}")

POWERS = ("brushed", "brushless", "nitro", "gas", "none")
POWER_SOURCES = ("name", "kit", "kind", "curated")

def check_release_power(docs, ids, errors):
    """A release's `power` is one of POWERS and comes with `power_source`: "name" (the maker's wording in the release
    name), "kit" (the kit's power), "kind" (a roller has none), "curated", or the id of the part or document that
    states it (docs/schema.md "release")."""
    for path, kind, d in docs:
        if kind != "release" or ("power" not in d and "power_source" not in d):
            continue
        p, s = d.get("power"), d.get("power_source")
        if p not in POWERS:
            errors.append(f"{path}: power = {p!r} not in {list(POWERS)}")
        if not (isinstance(s, str) and (s in POWER_SOURCES or (s.startswith(("part/", "doc/")) and s in ids))):
            errors.append(f"{path}: power_source = {s!r} should be one of {list(POWER_SOURCES)} or an existing part or doc id")
        elif p in ("brushed", "brushless", "nitro", "gas") and s == "kind":
            errors.append(f"{path}: power_source kind only gives power none")

def check_makes(docs, errors):
    """data/makes/<slug>.toml: one record per VEHICLE_MAKES entry, named as the make spells itself. country is the
    ISO 3166 alpha-2 code of the make's home country; notes describe the make with no dates (docs/schema.md "Makes")."""
    seen = set()
    for path, kind, d in docs:
        if kind != "make":
            continue
        name = d.get("name")
        seen.add(name)
        if name not in VEHICLE_MAKES:
            errors.append(f"{path}: make {name!r} is not in VEHICLE_MAKES (add it there first)")
        elif d.get("id") != f"make/{make_slug(name)}":
            errors.append(f"{path}: id should be make/{make_slug(name)} for {name!r}")
        if not (isinstance(d.get("country"), str) and re.fullmatch(r"[A-Z]{2}", d["country"])):
            errors.append(f"{path}: country {d.get('country')!r} should be an ISO 3166 alpha-2 code, such as DE")
        notes = d.get("notes")
        if not (isinstance(notes, str) and notes.strip() == notes and notes):
            errors.append(f"{path}: notes should be one or two sentences")
        elif re.search(r"\b(1[5-9]|20)\d\d(s)?\b|\b\d{1,2}(st|nd|rd|th) century\b", notes):
            errors.append(f"{path}: notes give a date; years need a source, so leave them out")
    for name in sorted(VEHICLE_MAKES - seen):
        errors.append(f"data/makes: no make file for {name!r}")

NAME_BRAND_EXCEPTIONS = {   # a name that starts with its brand's name on purpose (docs/schema.md "release", "kit", "part")
    "release/kyosho/30645",   # KYOSHO AMERICA: the maker's US company, not a repeat of the brand
    "release/team-associated/9064", "release/team-associated/9065",   # "Team Associated / Yokomo": a shared kit
    "part/fms/FMSC2051", "part/fms/FMSC2139",   # "FMS / ROC": shared with ROC
}

def check_kit_supersedes(docs, errors):
    """A kit's supersedes: the kit it replaces, same brand, one predecessor per kit, no cycles (docs/schema.md "kit")."""
    kits = {d["id"]: d for _, kind, d in docs if kind == "kit"}
    succ = {}
    for path, kind, d in docs:
        if kind != "kit" or "supersedes" not in d:
            continue
        v = d["supersedes"]
        if not (isinstance(v, str) and v.startswith("kit/")):
            errors.append(f"{path}: supersedes = {v!r} should be a kit id")
            continue
        if v == d.get("id"):
            errors.append(f"{path}: supersedes itself")
            continue
        if v not in kits:
            errors.append(f"{path}: supersedes -> {v} does not exist")
            continue
        if kits[v].get("brand") != d.get("brand"):
            errors.append(f"{path}: supersedes -> {v} is of another brand")
        succ[d["id"]] = v
    looped = set()
    for start in succ:   # a chain of kits that replace each other must end, never loop
        seen, cur = [], start
        while cur in succ:
            if cur in seen:
                if cur not in looped:
                    errors.append(f"kit supersedes cycle: {' -> '.join(seen[seen.index(cur):] + [cur])}")
                    looped.update(seen)
                break
            seen.append(cur)
            cur = succ[cur]


def check_names_no_brand(docs, errors):
    """A release, kit or part name does not repeat its brand: the site prints the brand in front."""
    brand_names = {d.get("id"): d.get("name", "") for _, k, d in docs if k == "brand"}
    for path, kind, d in docs:
        if kind not in ("release", "kit", "part") or d.get("id") in NAME_BRAND_EXCEPTIONS:
            continue
        bn, name = brand_names.get(d.get("brand"), ""), d.get("name", "")
        if bn and isinstance(name, str) and re.match(re.escape(bn) + " ", name, re.I):
            errors.append(f"{path}: name {name!r} repeats the brand {bn!r}; the site prints it in front (docs/schema.md \"{kind}\")")

# A pack count, a set or part number and punctuation are not part of a name (former_names_problems)
NAME_COUNT = re.compile(r"\(\s*\d+\s*(?:pcs?\.?|pieces?|ea)?\s*\)|\b\d+\s*(?:pcs?\.?|pieces?|ea)\b|(?<![a-z0-9])x\d+\b", re.I)
NAME_NUMBER = re.compile(r"\b\d{5,}\b")
NAME_CATALOGUE = re.compile(r"^\d{3,6} ")   # a store's catalogue number in front of a name

def name_key(name):
    s = NAME_COUNT.sub(" ", name.lower())
    return re.sub(r"[^a-z0-9]+", " ", NAME_NUMBER.sub(" ", s)).strip()

def restate_key(name, brand=""):
    """name_key() without the brand word (brand: the brand's display name) and a catalogue
    number in front, either one or both, in any order. Mirrors former_names._norm in hobbydex-tools."""
    k, bk = name_key(name), name_key(brand)
    while True:
        prev = k
        if bk and k.startswith(bk + " "):
            k = k[len(bk) + 1:]
        k = NAME_CATALOGUE.sub("", k + " ", count=1).strip()
        if k == prev:
            return k

def former_names_problems(part, brand=""):
    """The former_names entries a part may not keep: the part's own name again once counts, numbers,
    the brand word and a catalogue number go, and a repeat of an earlier entry (case and spacing
    ignored). docs/schema.md "part"."""
    cur = restate_key(part.get("name", "") or "", brand)
    seen, bad = set(), []
    for n in part.get("former_names", []) or []:
        if not isinstance(n, str):
            continue
        norm = re.sub(r"\s+", " ", n).strip().lower()
        # a number the current name carries is part of it: an entry without it is a different name the maker printed
        lost = set(re.findall(r"\b\d{6}\b", part.get("name", "") or "")) - set(re.findall(r"\b\d{6}\b", n))
        if (cur and restate_key(n, brand) == cur and not lost) or norm in seen:
            bad.append(n)
        seen.add(norm)
    return bad

def check_former_names(docs, errors):
    brand_names = {d.get("id"): d.get("name", "") for _, k, d in docs if k == "brand"}
    for path, kind, d in docs:
        if kind == "part":
            for n in former_names_problems(d, brand_names.get(d.get("brand"), "")):
                errors.append(f"{path}: former name {n!r} is the part's name again (a pack count, a set number, the brand word or a catalogue number) or listed twice; a former name is a different name the maker published (docs/schema.md \"part\")")

def check_part_category(docs, errors):
    """Every part has a category (docs/schema.md "category"); a part no rule places is the fallback: misc with category_source "fallback"."""
    for path, kind, d in docs:
        if kind != "part":
            continue
        if not d.get("category"):
            errors.append(f"{path}: a part has no category; every part needs one (a part no rule places is misc with category_source = \"fallback\")")
        elif d.get("category_source") == "fallback" and d["category"] != "misc":
            errors.append(f"{path}: category_source \"fallback\" goes with category misc, not {d['category']}")
        elif d.get("category_source") in ("manual-section", "photo", "llm") and d["category"] == "misc":
            errors.append(f"{path}: category_source \"{d['category_source']}\" places a part in a real category, not misc")

def check_dealer_links(docs, errors):
    """A dealer link (a links entry with kind "dealer", a reseller's product page) is a fallback: a release or part
    with a dealer link has no maker product link (a links entry with no kind) and no maker product page (a
    document of kind product_page), so no dealer page is shown as the official one (docs/schema.md "Links")."""
    doc_kind = {d.get("id"): d.get("kind") for _, k, d in docs if k == "doc"}
    for path, kind, d in docs:
        if kind not in ("release", "part"):
            continue
        links = [l for l in d.get("links", []) if isinstance(l, dict)]
        if not any(l.get("kind") == "dealer" for l in links):
            continue
        maker = [l.get("site") for l in links if "kind" not in l and "gone" not in l]   # a page marked gone is no product page
        pages = [x for x in d.get("documents", []) + [d.get("source")] if doc_kind.get(x) == "product_page"]
        if maker:
            errors.append(f"{path}: dealer link beside a maker product link ({', '.join(map(str, maker))}); drop the dealer link")
        if pages:
            errors.append(f"{path}: dealer link beside a maker product page ({', '.join(pages)}); drop the dealer link")

def check_art(ids, errors, body_parts=frozenset()):
    """art/<kits|releases|parts>/<brand>/<key>.svg: our own outline of a kit, release or body part (category
    body), drawn by the site in its colours. One line: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 24">
    with one or more <path d="..."/> and nothing else (no fill, style, transform, class or title), at most
    ART_MAX bytes, named after a kit, release or body part that exists. Returns the number of art files."""
    lower = {i.lower(): i for i in ids if isinstance(i, str)}
    dirs = {DIRS[k]: k for k in ART_KINDS}
    n = 0
    for dirpath, _, files in os.walk(ART_ROOT):
        for fn in sorted(files):
            path = os.path.join(dirpath, fn)
            parts = os.path.relpath(path, ART_ROOT).split(os.sep)
            if len(parts) != 3 or parts[0] not in dirs or not fn.endswith(".svg"):
                errors.append(f"{path}: art goes in {ART_ROOT}/kits/<brand>/<slug>.svg, {ART_ROOT}/releases/<brand>/<key>.svg or {ART_ROOT}/parts/<brand>/<number>.svg")
                continue
            n += 1
            eid = f"{dirs[parts[0]]}/{parts[1]}/{fn[:-4]}"
            if os.path.normpath(art_path(eid, ART_ROOT)) != os.path.normpath(path):
                errors.append(f"{path}: art for {eid} belongs at {art_path(eid, ART_ROOT)}")
            if eid not in ids:
                hint = f" (the id is {lower[eid.lower()]}: names match the id exactly)" if eid.lower() in lower else ""
                errors.append(f"{path}: orphan art, no {eid}{hint}")
            elif eid.startswith("part/") and eid not in body_parts:
                errors.append(f"{path}: art is for body parts only, and {eid} is not of category body")
            elif parts[1] != parts[1].lower():
                errors.append(f"{path}: brand directory must be lowercase")
            size = os.path.getsize(path)
            if size > ART_MAX:
                errors.append(f"{path}: {size} bytes, art is at most {ART_MAX}")
                continue
            with open(path, "rb") as f:
                raw = f.read()
            text = raw.decode("utf-8", "replace")
            if not text.startswith("<svg") or "\n" in text.rstrip("\n") or "\r" in text:
                errors.append(f"{path}: art is one line starting with <svg (no XML declaration, doctype or line breaks)")
                continue
            try:
                root = ET.fromstring(raw)
            except ET.ParseError as e:
                errors.append(f"{path}: not well-formed XML: {e}")
                continue
            if root.tag != f"{{{SVG_NS}}}svg":
                errors.append(f"{path}: root must be <svg xmlns=\"{SVG_NS}\">, got {root.tag}")
                continue
            if root.get("viewBox") != "0 0 48 24":
                errors.append(f"{path}: viewBox must be \"0 0 48 24\", got {root.get('viewBox')!r}")
            extra = sorted(set(root.attrib) - {"viewBox"})
            if extra:
                errors.append(f"{path}: <svg> takes only xmlns and viewBox, not {', '.join(extra)}")
            if (root.text or "").strip():
                errors.append(f"{path}: text inside <svg>")
            if not len(root):
                errors.append(f"{path}: no <path>")
            for el in root:
                tag = el.tag.split("}")[-1]
                if el.tag != f"{{{SVG_NS}}}path":
                    errors.append(f"{path}: only <path> elements, found <{tag}>")
                    continue
                if not el.get("d"):
                    errors.append(f"{path}: <path> without d")
                elif not PATH_DATA.fullmatch(el.get("d")):
                    errors.append(f"{path}: <path> d holds characters that are not path data")
                elif not el.get("d").lstrip().startswith("M"):
                    errors.append(f"{path}: <path> d must start with an absolute M (the export joins the paths into one)")
                extra = sorted(set(el.attrib) - {"d"})
                if extra:
                    errors.append(f"{path}: <path> takes only d (the site sets the fill), not {', '.join(extra)}")
                if len(el) or (el.text or "").strip() or (el.tail or "").strip():
                    errors.append(f"{path}: <path> must be empty")
    return n

# the plug names of a wire part's `connectors` and of the battery and ESC `connector` field (tools/link_connector_specs.py PLUG_NAME);
# "JR/Futaba" is one plug sold as fitting both servo plugs, so it names both specs
PLUG_SPEC = {
    "XT30": "xt30", "XT60": "xt60", "XT60H": "xt60h", "XT90": "xt90", "XT90-S": "xt90s", "XT150": "xt150",
    "AS150": "as150", "QS8": "qs8", "EC2": "ec2", "EC3": "ec3", "EC5": "ec5", "EC8": "ec8", "IC3": "ic3", "IC5": "ic5",
    "Deans": "deans", "Tamiya": "tamiya", "Mini Tamiya": "tamiya-mini", "JST-RCY": "jst-rcy", "JST-XH": "jst-xh",
    "JR": "servo-jr", "Futaba": "servo-futaba", "JR/Futaba": ("servo-jr", "servo-futaba"), "Traxxas iD": "traxxas-trx-id", "Traxxas high-current": "traxxas-high-current",
    "2mm bullet": "bullet-2mm", "3.5mm bullet": "bullet-3.5mm", "4mm bullet": "bullet-4mm", "5mm bullet": "bullet-5mm",
    "6mm bullet": "bullet-6mm", "6.5mm bullet": "bullet-6.5mm", "8mm bullet": "bullet-8mm", "4mm banana": "banana-4mm",
}

# charger fields (docs/schema.md "Chargers"): what a charger charges and with which plugs, each stated by the maker
CHARGER_FIELDS = ("charges", "power_ac_w", "power_dc_w", "charge_current_a", "ac_input_v", "mains_plug", "mains_plug_basis",
                  "dc_input_v", "dc_input_connector", "output_connector", "balance_ports", "charger_source")
CHARGES = {"lipo", "lihv", "life", "liion", "nimh", "nicd", "pb", "nizn"}
MAINS_PLUGS = {"EU", "UK", "US", "AU"}
BALANCE_PORTS = {"JST-XH", "JST-EH", "XHP", "TP", "FP", "EHR", "Hyperion"}


def check_charger(path, d):
    errors = []

    def num(x, lo, hi):
        return isinstance(x, (int, float)) and not isinstance(x, bool) and lo <= x <= hi

    def rng(x, lo, hi):
        return isinstance(x, list) and len(x) == 2 and all(num(v, lo, hi) for v in x) and x[0] <= x[1]

    def plug(x):
        return isinstance(x, str) and x in PLUG_SPEC
    ch = d.get("charges")
    if ch is not None and not (isinstance(ch, list) and ch and len(set(ch)) == len(ch) and all(c in CHARGES for c in ch)):
        errors.append(f"{path}: charges {ch!r} should be a list of {sorted(CHARGES)}")
    for k, hi in (("power_ac_w", 3000), ("power_dc_w", 6000), ("charge_current_a", 200)):
        if k in d and not num(d[k], 0.1, hi):
            errors.append(f"{path}: {k} {d[k]!r} should be a number up to {hi}")
    if "ac_input_v" in d and not rng(d["ac_input_v"], 90, 260):
        errors.append(f"{path}: ac_input_v {d['ac_input_v']!r} should be [min, max] volts (90..260)")
    if "dc_input_v" in d and not rng(d["dc_input_v"], 3, 60):
        errors.append(f"{path}: dc_input_v {d['dc_input_v']!r} should be [min, max] volts (3..60)")
    mp, mb = d.get("mains_plug"), d.get("mains_plug_basis")
    if mp is not None and mp not in MAINS_PLUGS:
        errors.append(f"{path}: mains_plug {mp!r} should be one of {sorted(MAINS_PLUGS)}")
    if (mp is None) != (mb is None) or (mb is not None and mb not in ("maker", "name")):
        errors.append(f"{path}: mains_plug_basis is \"maker\" (page or manual) or \"name\" (the part name says EU/UK/US/AU), and goes with mains_plug")
    dc = d.get("dc_input_connector")
    if dc is not None and not plug(dc):
        errors.append(f"{path}: dc_input_connector {dc!r} is not a plug name (validate.py PLUG_SPEC)")
    oc = d.get("output_connector")
    if oc is not None and not (isinstance(oc, list) and oc and len(set(oc)) == len(oc) and all(plug(x) for x in oc)):
        errors.append(f"{path}: output_connector {oc!r} should be a list of plug names (validate.py PLUG_SPEC)")
    bp = d.get("balance_ports")
    if bp is not None and not (isinstance(bp, list) and bp and len(set(bp)) == len(bp) and all(x in BALANCE_PORTS for x in bp)):
        errors.append(f"{path}: balance_ports {bp!r} should be a list of {sorted(BALANCE_PORTS)}")
    nc = d.get("nimh_cells")
    if nc is not None and not (isinstance(nc, list) and len(nc) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in nc) and 0 < nc[0] <= nc[1]):
        errors.append(f"{path}: nimh_cells {nc!r} should be [min, max] cell counts")
    cn = d.get("channels")
    if cn is not None and not (isinstance(cn, int) and not isinstance(cn, bool) and 1 <= cn <= 12):
        errors.append(f"{path}: channels {cn!r} should be a count of 1 to 12 outputs")
    src = d.get("charger_source")
    stated = [k for k in CHARGER_FIELDS + ("channels", "nimh_cells") if k in d and k not in ("charger_source", "mains_plug_basis")]
    needs = bool(stated) and not (stated == ["mains_plug"] and mb == "name")
    if needs and not (isinstance(src, str) and (src.startswith("doc/") or src.startswith("http"))):
        errors.append(f"{path}: charger fields need charger_source (a doc/ id or the maker's page URL)")
    if src is not None and not stated:
        errors.append(f"{path}: charger_source without a charger field")
    return errors


def check_connectors(docs, ids, errors):
    """A wire part lists the plugs of a lead, adapter or harness in `connectors`, each a plug name with a connector
    spec; a part that is the plug itself is equivalent_to its connector spec instead, so it never has both
    (docs/schema.md "Connector specs")."""
    for path, kind, d in docs:
        if kind != "part" or "connectors" not in d:
            continue
        if d.get("category") != "wire":
            errors.append(f"{path}: connectors is for wire parts (leads, adapters, harnesses), not a {d.get('category')}")
        names = d["connectors"]
        if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
            errors.append(f"{path}: connectors should be a non-empty list of plug names, got {names!r}")
            continue
        for n in names:
            if n not in PLUG_SPEC:
                errors.append(f"{path}: connectors {n!r} is not a plug name (validate.py PLUG_SPEC)")
            else:
                for slug in (PLUG_SPEC[n],) if isinstance(PLUG_SPEC[n], str) else PLUG_SPEC[n]:
                    if f"spec/connector/{slug}" not in ids:
                        errors.append(f"{path}: connectors {n!r} has no connector spec spec/connector/{slug}")
        if len(set(names)) != len(names):
            errors.append(f"{path}: connectors lists a plug twice: {names!r}")
        if any(str(e.get("spec", "")).startswith("spec/connector/") for e in d.get("equivalent_to", []) if isinstance(e, dict)):
            errors.append(f"{path}: has connectors and an equivalent_to connector spec; a lead lists its plugs only in connectors")

def check_protocols(docs, ids, errors):
    """A radio part's `protocols` lists protocol specs (spec/protocol/..., category protocol); a protocol spec's
    `compatible` rows name other protocol specs and the radio parts (`via`) that list both (docs/schema.md "Protocol specs")."""
    protocol_ids = {d["id"] for _, kind, d in docs if kind == "spec" and d.get("category") == "protocol"}
    part_ids = {d["id"] for _, kind, d in docs if kind == "part"}
    for path, kind, d in docs:
        if kind == "part" and "protocols" in d:
            names = d["protocols"]
            if d.get("category") != "radio":
                errors.append(f"{path}: protocols only on radio parts, not {d.get('category')}")
            if not isinstance(names, list) or not names or any(n not in protocol_ids for n in names):
                errors.append(f"{path}: protocols should be a non-empty list of protocol spec ids, got {names!r}")
            elif len(set(names)) != len(names):
                errors.append(f"{path}: protocols lists a protocol twice: {names!r}")
        if kind == "spec" and d.get("category") == "protocol":
            if not d["id"].startswith("spec/protocol/"):
                errors.append(f"{path}: a protocol spec id starts with spec/protocol/")
            for row in d.get("compatible", []):
                if not isinstance(row, dict) or row.get("spec") not in protocol_ids or row.get("spec") == d["id"]:
                    errors.append(f"{path}: compatible row {row!r} should name another protocol spec")
                    continue
                for v in row.get("via", []):
                    if v not in part_ids:
                        errors.append(f"{path}: compatible via {v} is not a part")

def check_plugs(docs, ids, errors):
    """`motor_connector` (the plug on an ESC's motor wires, or on a motor's leads) names a PLUG_SPEC plug that has its
    connector spec, and is on esc and motor parts only (docs/schema.md "ESCs"). The battery-side `connector` is not
    checked yet: some values predate PLUG_SPEC (JST-SYP, T-Plug, TRX) and are to be cleaned up first."""
    for path, kind, d in docs:
        if kind != "part" or "motor_connector" not in d:
            continue
        n = d["motor_connector"]
        if d.get("category") not in ("esc", "motor"):
            errors.append(f"{path}: motor_connector only on esc and motor parts, not {d.get('category')}")
        if not isinstance(n, str) or n not in PLUG_SPEC:
            errors.append(f"{path}: motor_connector {n!r} is not a plug name (validate.py PLUG_SPEC)")
            continue
        for slug in (PLUG_SPEC[n],) if isinstance(PLUG_SPEC[n], str) else PLUG_SPEC[n]:
            if f"spec/connector/{slug}" not in ids:
                errors.append(f"{path}: motor_connector {n!r} has no connector spec spec/connector/{slug}")

def check_receiver_plugs(docs, ids, errors):
    """`receiver_connector` (the servo plug on a lead to the receiver: JR, Futaba or JR/Futaba) is on esc and light parts
    only, and names one of those plugs with its servo connector spec (docs/schema.md "ESCs")."""
    for path, kind, d in docs:
        if kind != "part" or "receiver_connector" not in d:
            continue
        n = d["receiver_connector"]
        if d.get("category") not in RECEIVER_CATEGORIES:
            errors.append(f"{path}: receiver_connector only on {', '.join(RECEIVER_CATEGORIES)} parts, not {d.get('category')}")
        if n not in RECEIVER_PLUGS:
            errors.append(f"{path}: receiver_connector {n!r} is not JR, Futaba or JR/Futaba")
            continue
        for slug in (PLUG_SPEC[n],) if isinstance(PLUG_SPEC[n], str) else PLUG_SPEC[n]:
            if f"spec/connector/{slug}" not in ids:
                errors.append(f"{path}: receiver_connector {n!r} has no connector spec spec/connector/{slug}")

def main():
    ENUMS["part.category"] = categories()
    errors, ids, docs = [], {}, []
    for dirpath, _, files in os.walk(ROOT):
        for fn in sorted(files):
            if not fn.endswith(".toml"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "rb") as f:
                    d = tomllib.load(f)
            except Exception as e:
                errors.append(f"{path}: parse error: {e}")
                continue
            rel = os.path.relpath(path, ROOT)
            if rel in ("retired.toml", "confirmed-distinct.toml"):
                continue   # retired ids and confirmed pairs, checked below
            top = rel.split(os.sep)[0]
            kind = next((k for k, v in KINDS.items() if v["dir"] == top), None)
            if kind is None:
                errors.append(f"{path}: unknown entity directory {top}")
                continue
            try:
                expected_path = path_for(str(d.get("id", "")), ROOT)
            except ValueError as e:
                expected_path = None
                errors.append(f"{path}: {e}")
            if expected_path and os.path.normpath(expected_path) != os.path.normpath(path):
                errors.append(f"{path}: id {d.get('id')!r} belongs at {expected_path}")
            if not str(d.get("id", "")).startswith(f"{kind}/"):
                errors.append(f"{path}: id {d.get('id')!r} is not a {kind} id")
            if d.get("id") in ids:
                errors.append(f"{path}: duplicate id {d['id']} (also {ids[d['id']]})")
            ids[d.get("id")] = path
            for r in KINDS[kind]["required"]:
                if r not in d:
                    errors.append(f"{path}: missing required field {r}")
            docs.append((path, kind, d))
    gone_brands = {d.get("id") for _, k, d in docs if k == "brand" and d.get("status") == "gone"}   # defunct: everything discontinued
    # hosts of brands whose own site serves http only (website = "http://..."): their maker pages may be linked over http
    http_hosts = {urllib.parse.urlsplit(d["website"]).hostname for _, k, d in docs
                  if k == "brand" and str(d.get("website", "")).startswith("http://")}
    brand_site = {d.get("id"): urllib.parse.urlsplit(d["website"]).hostname for _, k, d in docs if k == "brand" and d.get("website")}
    # stable ids: an id is never reused; a changed id stays as former_ids on its successor or in retired.toml
    claimed = {}
    for path, kind, d in docs:
        for old in d.get("former_ids", []):
            if not isinstance(old, str) or not old.startswith(f"{kind}/"):
                errors.append(f"{path}: former_ids entry {old!r} is not a {kind} id")
            elif old in ids:
                errors.append(f"{path}: former id {old} is a live id again ({ids[old]})")
            elif old in claimed:
                errors.append(f"{path}: former id {old} is also claimed by {claimed[old]}")
            claimed[old] = path
    retired_path = os.path.join(ROOT, "retired.toml")
    if os.path.exists(retired_path):
        with open(retired_path, "rb") as f:
            for r in tomllib.load(f).get("retired", []):
                rid = r.get("id")
                if rid in ids:
                    errors.append(f"{retired_path}: retired id {rid} is a live id again ({ids[rid]})")
                if rid in claimed:
                    errors.append(f"{retired_path}: retired id {rid} is also a former id of {claimed[rid]}")
                if not r.get("reason"):
                    errors.append(f"{retired_path}: retired id {rid} needs a reason")
                if r.get("replaced_by") and r["replaced_by"] not in ids:
                    errors.append(f"{retired_path}: {rid} replaced_by {r['replaced_by']} does not exist")
    distinct_path = os.path.join(ROOT, "confirmed-distinct.toml")
    if os.path.exists(distinct_path):   # pairs of parts confirmed as two parts (the audit's ocr-number-twins skips them)
        with open(distinct_path, "rb") as f:
            doc_ids = {d.get("id") for _, kind, d in docs if kind == "doc"}
            seen_pairs = set()
            for p in tomllib.load(f).get("pair", []):
                pair = frozenset(p.get("parts", []))
                if len(pair) != 2 or any(x not in ids for x in pair):
                    errors.append(f"{distinct_path}: pair {sorted(pair)} needs two live parts")
                elif pair in seen_pairs:
                    errors.append(f"{distinct_path}: pair {sorted(pair)} listed twice")
                seen_pairs.add(pair)
                if not p.get("evidence"):
                    errors.append(f"{distinct_path}: pair {sorted(pair)} needs evidence (a manual that prints each number)")
                for e in p.get("evidence", []):
                    if e not in doc_ids:
                        errors.append(f"{distinct_path}: evidence {e} is not a document")
    codes = {d.get("code") for _, kind, d in docs if kind == "standard"}
    no_numbers = {d.get("id"): d.get("item_numbers") is False for _, kind, d in docs if kind == "brand"}   # makers that print no item numbers
    release_kit = {d.get("id"): d.get("kit") for _, kind, d in docs if kind == "release"}
    manual_links = {d.get("id"): {d[k] for k in ("url", "page") if d.get(k)} for _, kind, d in docs if kind == "doc" and d.get("kind") == "manual"}
    # a dated catalogue or manual document whose printed year bounds a part's seen_by (docs/schema.md, seen_by_source)
    printed_docs = {d.get("id"): str(d["printed"]) for _, kind, d in docs if kind == "doc" and d.get("kind") in PRINTED_KINDS and d.get("printed")}   # any document with a printed date (YYYY or YYYY-MM)
    doc_pages = {d.get("id"): d["page"] for _, kind, d in docs if kind == "doc" and d.get("kind") != "catalog" and d.get("page")}   # a non-catalogue document's maker page
    product_urls = {d.get("id"): d["url"] for _, kind, d in docs if kind == "doc" and d.get("kind") == "product_page" and d.get("url")}   # a product page document's url
    placeholder_kits = {d.get("id") for _, kind, d in docs if kind == "kit" and d.get("placeholder") is True}
    kit_scale = {d.get("id"): d.get("scale") for _, kind, d in docs if kind == "kit"}
    for path, kind, d in docs:
        if kind in ("kit", "release") and "scale" in d and not (isinstance(d["scale"], str) and SCALE_RE.fullmatch(d["scale"])):
            errors.append(f"{path}: scale {d['scale']!r} should be a fraction like \"1/10\"")
        if kind == "release" and "scale" in d and d["scale"] == kit_scale.get(d.get("kit")):
            errors.append(f"{path}: scale {d['scale']!r} repeats its kit's; leave it out (docs/schema.md \"release\")")
        if kind == "kit" and "placeholder" in d and not isinstance(d["placeholder"], bool):
            errors.append(f"{path}: placeholder should be true (a group for releases whose chassis no source names yet)")
        if kind == "category" and "terms" in d:   # glossary on the category page (docs/schema.md "category")
            ts = d["terms"]
            if not isinstance(ts, list) or not ts or not all(isinstance(t, dict) and set(t) == {"term", "text"} and all(
                    isinstance(t[k], str) and t[k].strip() == t[k] and t[k] for k in ("term", "text")) for t in ts):
                errors.append(f"{path}: terms should be a list of {{ term, text }} strings")
        if kind == "part" and "source" in d:   # the site reads documents, links and sources on a part, not a single source (docs/schema.md "part")
            errors.append(f"{path}: part has a singular source = {d['source']!r}; put it in documents (a list) instead")
        # a placeholder kit (its chassis unknown) takes a fits row only for the releases the set names (releases, checked
        # below against the kit): a whole-kit fit would put the set on cars of unknown chassis (decision 2026-10-28)
        if kind == "part" and any(isinstance(f, dict) and f.get("kit") in placeholder_kits and not f.get("releases") for f in d.get("fits", []) or []):
            errors.append(f"{path}: fits a placeholder kit without releases; a placeholder takes a part only for the releases it names")
        def check_ref(field, value, where):
            prefix = REFS.get(field)
            if prefix is None:
                return
            if not isinstance(value, str) or not value.startswith(prefix):
                errors.append(f"{path}: {where}{field} = {value!r} should start with {prefix}")
            elif value not in ids:
                errors.append(f"{path}: {where}{field} -> {value} does not exist")
        for k, v in d.items():
            if kind == "release" and k == "related":   # checked with the other releases in check_release_related
                continue
            if kind == "kit" and k == "supersedes":   # checked in check_kit_supersedes
                continue
            if kind == "release" and k == "supersedes":   # the release this one replaces (docs/schema.md "release")
                if not (isinstance(v, str) and v.startswith("release/")):
                    errors.append(f"{path}: supersedes = {v!r} should be a release id")
                elif v == d.get("id"):
                    errors.append(f"{path}: supersedes itself")
                elif v not in ids:
                    errors.append(f"{path}: supersedes -> {v} does not exist")
            elif kind == "release" and k == "range":   # versions of one car that differ only in colour or livery (docs/schema.md "release")
                brand_slug = str(d.get("brand", "")).split("/")[-1]
                if not (isinstance(v, str) and re.fullmatch(r"[a-z0-9.-]+/[a-z0-9.-]+-colours", v) and v.split("/")[0] == brand_slug):
                    errors.append(f"{path}: range {v!r} should be <brand slug>/<slug>-colours of the release's own brand")
            elif kind == "release" and k == "color_source":
                if "color" not in d:
                    errors.append(f"{path}: color_source without color; it says who states the colour")
            elif kind == "release" and k == "livery":
                if not (isinstance(v, str) and v.strip() == v and v):
                    errors.append(f"{path}: livery {v!r} should be a non-empty string without edge spaces")
                elif "range" not in d:
                    errors.append(f"{path}: livery without a range; it names what sets a version apart within its range")
            elif k in REFS:
                check_ref(k, v, "")
            elif k in LIST_REFS and isinstance(v, list):
                for x in v:
                    if x not in ids:
                        errors.append(f"{path}: {k} -> {x} does not exist")
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                for i, row in enumerate(v):
                    for kk, vv in row.items():
                        check_ref(kk, vv, f"{k}[{i}].")
                        key = f"{k}.{kk}"
                        if key in ENUMS and vv not in ENUMS[key]:
                            errors.append(f"{path}: {key} = {vv!r} not in {sorted(ENUMS[key])}")
            key = f"{kind}.{k}"
            if key == "release.kind" and v not in ENUMS[key]:
                errors.append(f"{path}: release kind {v!r} is not kit, rtr, arr or roller (docs/schema.md \"release\")")
            elif key in ENUMS and v not in ENUMS[key]:
                errors.append(f"{path}: {key} = {v!r} not in {sorted(ENUMS[key])}")
        # a fit narrowed to the releases the maker lists the part for (releases of that kit, at least one), or to a car
        for i, f in enumerate(d.get("fits", []) if kind == "part" else []):
            if "car" in f:   # the car the maker lists the part for, when none of the kit's releases is that car
                if not (isinstance(f["car"], str) and f["car"].strip()):
                    errors.append(f"{path}: fits[{i}].car should be the car's name as the maker lists it")
                if "releases" in f:
                    errors.append(f"{path}: fits[{i}] has both car and releases (car is only for a car none of the releases is)")
            if "releases" not in f:
                continue
            rs = f["releases"]
            if not (isinstance(rs, list) and rs and len(set(rs)) == len(rs)):
                errors.append(f"{path}: fits[{i}].releases should be a non-empty list of distinct release ids")
                continue
            for r in rs:
                if r not in release_kit:
                    errors.append(f"{path}: fits[{i}].releases -> {r} does not exist")
                elif release_kit[r] != f.get("kit"):
                    errors.append(f"{path}: fits[{i}].releases -> {r} is a release of {release_kit[r]}, not of {f.get('kit')}")
        # a date we keep but doubt (docs/schema.md "Dates"): <field>_doubt says why, next to the date it doubts
        for k in [k for k in d if k.endswith("_doubt")]:
            base = k[:-len("_doubt")]
            if base not in DOUBTABLE.get(kind, ()):
                errors.append(f"{path}: {k}: only {', '.join(f'{f}_doubt' for f in DOUBTABLE.get(kind, ())) or 'no doubt field'} on a {kind}")
            elif base not in d:
                errors.append(f"{path}: {k} needs {base}")
            elif not (isinstance(d[k], str) and d[k].strip()):
                errors.append(f"{path}: {k} must say why the date is in doubt")
        if kind in ("part", "release") and d.get("brand") in gone_brands and d.get("status") != "discontinued":
            errors.append(f"{path}: {d['brand']} is gone, so status must be discontinued")
        if kind in ("part", "release") and "gtin" in d:
            g = str(d["gtin"])
            digits = [int(c) for c in g] if g.isdigit() else []
            ok = len(digits) in (8, 12, 13, 14) and (10 - sum(x * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(digits[:-1]))) % 10) % 10 == digits[-1]
            if not ok:
                errors.append(f"{path}: gtin {g!r} is not a valid GTIN-8/12/13/14 (length or check digit)")
        if kind == "doc" and d.get("kind") == "video":
            # a maker's own YouTube video (docs/schema.md "Videos")
            vid = str(d.get("id", "")).rsplit("/", 1)[-1].removeprefix("youtube-")
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) or not str(d.get("id", "")).rsplit("/", 1)[-1].startswith("youtube-"):
                errors.append(f"{path}: a video's id should be doc/<brand>/youtube-<11-character video id>")
            elif d.get("url") != f"https://www.youtube.com/watch?v={vid}":
                errors.append(f"{path}: url should be https://www.youtube.com/watch?v={vid}")
            if not d.get("publisher") or not d.get("channel"):
                errors.append(f"{path}: a video needs its publisher (the maker) and channel")
            if not any(d.get(k) for k in ("releases", "kits", "parts")):
                errors.append(f"{path}: a video should show a release, kit or part (releases, kits or parts)")
            if "date" in d and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d["date"])):
                errors.append(f"{path}: date {d['date']!r} should be YYYY-MM-DD")
            if "duration_s" in d and not (isinstance(d["duration_s"], int) and d["duration_s"] > 0):
                errors.append(f"{path}: duration_s should be a whole number of seconds")
        if kind == "doc" and ("printed" in d or "printed_source" in d):
            pr, ps = d.get("printed"), d.get("printed_source")
            if d.get("kind") not in PRINTED_KINDS:
                errors.append(f"{path}: printed is only for a manual, supplement, part_list, exploded_view, setup_sheet or catalog document")
            if not (isinstance(pr, str) and re.fullmatch(r"(19[6-9]\d|20[0-3]\d)(-(0[1-9]|1[0-2]))?", pr) and int(pr[:4]) <= datetime.date.today().year):
                errors.append(f"{path}: printed {pr!r} should be YYYY or YYYY-MM (the date the document itself prints)")
            if ("printed_source" in d and "printed" not in d) or ("printed_source" in d and not (isinstance(ps, str) and ps.strip())):
                errors.append(f"{path}: printed_source (what the document's text says) goes with printed")
        if kind == "doc":
            for f in ("url", "page"):
                if f in d and not str(d[f]).startswith(("https://", "http://")):
                    errors.append(f"{path}: {f} must be a web link, got {d[f]!r}")
            if "manual_no" in d and not (isinstance(d["manual_no"], str) and d["manual_no"].strip()):
                errors.append(f"{path}: manual_no must be a non-empty string, got {d['manual_no']!r}")
        for l in d.get("links", []) if kind in ("part", "release", "kit") else []:
            u = str(l.get("url", "")) if isinstance(l, dict) else ""
            if not (isinstance(l, dict) and l.get("site") and (u.startswith("https://") or
                    (u.startswith("http://") and urllib.parse.urlsplit(u).hostname in http_hosts))):
                errors.append(f"{path}: link {l!r} needs a site and an https url (http only for a maker site that has no https)")
            elif "kind" in l and l["kind"] not in LINK_KINDS:
                errors.append(f"{path}: link kind = {l['kind']!r} not in {sorted(LINK_KINDS)}")
            elif "kind" not in l and urllib.parse.urlsplit(u).hostname == "web.archive.org":
                errors.append(f"{path}: link {u!r} is a Wayback capture: kind = \"archive\" (the maker product link is the live page)")
            elif l.get("kind") == "archive" and not ARCHIVE_URL.fullmatch(u):
                errors.append(f"{path}: archive link {u!r} should be https://web.archive.org/web/<14-digit timestamp>/<original URL>")
            if isinstance(l, dict) and "gone" in l and not (isinstance(l["gone"], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", l["gone"])):
                errors.append(f"{path}: link gone = {l['gone']!r} should be the day the page answered 404 or 410, \"YYYY-MM-DD\"")
        if kind == "part" and ("universal" in d or "universal_basis" in d):
            if d.get("universal") is not True:
                errors.append(f"{path}: universal is true or left out")
            elif "universal_basis" not in d:
                errors.append(f"{path}: universal needs a universal_basis (maker, category or size)")
            elif d.get("applies_to"):
                errors.append(f"{path}: a part that names the model it is for (applies_to) is not universal")
        if kind == "part" and "pack_qty_basis" in d and not (isinstance(d.get("pack_qty"), int) and d["pack_qty"] >= 1):
            errors.append(f"{path}: pack_qty_basis needs a pack_qty (a whole number, 1 or more)")
        if kind == "part" and d.get("category") == "paint" and "finish" in d and d["finish"] not in PAINT_FINISH:
            errors.append(f"{path}: paint finish = {d['finish']!r} not in {sorted(PAINT_FINISH)}")
        if kind in ("release", "part"):
            if "announced" in d and "announced_source" not in d:
                errors.append(f"{path}: announced needs announced_source (the https URL the date comes from)")
            if "announced_source" in d and ("announced" not in d or not str(d["announced_source"]).startswith("https://")):
                errors.append(f"{path}: announced_source needs announced and an https URL, got {d['announced_source']!r}")
            if kind == "part" and "announced" in d and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d["announced"])):
                errors.append(f"{path}: announced {d['announced']!r} on a part should be YYYY-MM-DD")
        # a part is equivalent only to a spec of its own kind; a part that comes with bearings, screws or a battery lists them in `includes`
        if kind == "part" and d.get("category"):
            for e in d.get("equivalent_to", []):
                sk = str(e.get("spec", "")).split("/")[1] if str(e.get("spec", "")).count("/") >= 2 else None
                if sk in SPEC_PART_CATS and d["category"] not in SPEC_PART_CATS[sk]:
                    errors.append(f"{path}: equivalent_to {e['spec']} is a {sk} spec, but the part is a {d['category']} (list it in includes if the part comes with one)")
        sw = d.get("swatch") if kind == "part" else None
        if sw is not None and not (isinstance(sw, str) and re.fullmatch(r"#[0-9a-f]{6}", sw)):
            errors.append(f"{path}: swatch {sw!r} should be a lowercase hex colour \"#rrggbb\"")
        rg = d.get("range") if kind == "part" else None
        if rg is not None and not (isinstance(rg, str) and re.fullmatch(r"[a-z0-9-]+/[a-z0-9.-]+", rg) and rg.split("/")[0] == d["brand"].split("/")[1]):
            errors.append(f"{path}: range {rg!r} should be <brand slug>/<slug> of the part's own brand")
        on = d.get("ocr_names") if kind == "part" else None
        if on is not None and not (isinstance(on, list) and all(isinstance(x, str) and x and x == x.strip() for x in on)):
            errors.append(f"{path}: ocr_names should be a list of strings (names read by OCR, hidden from the site, kept for the matchers)")
        if kind == "release":
            this_year = datetime.date.today().year
            if isinstance(d.get("year"), int) and d["year"] > this_year and d.get("status") == "released":
                errors.append(f"{path}: year {d['year']} is in the future, so status cannot be released (announced; a model year label goes in model_year)")
            rel = str(d.get("released", ""))
            if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", rel) and d.get("status") == "released":
                y, mo, *dd = (int(x) for x in rel.split("-"))
                if datetime.date(y, mo, dd[0] if dd else 1) > datetime.date.today():
                    errors.append(f"{path}: released {rel} is still to come, so status cannot be released (announced)")
            my = d.get("model_year")
            if my is not None and not (isinstance(my, int) and 1970 <= my <= this_year + 3):
                errors.append(f"{path}: model_year {my!r} should be a year")
            if "announced" in d:
                an = str(d["announced"])
                if not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", an):
                    errors.append(f"{path}: announced {an!r} should be YYYY, YYYY-MM or YYYY-MM-DD")
                elif "released" in d and an > str(d["released"]):
                    errors.append(f"{path}: announced {an} is after released {d['released']}")
            ans = d.get("announced_source")
            if ans is not None and ("announced" not in d or not (isinstance(ans, str) and ans.startswith("https://"))):
                errors.append(f"{path}: announced_source is an https URL that comes with announced (the video or page that gives the day), got {ans!r}")
        if kind in ("release", "part"):
            this_year = datetime.date.today().year
            has_seen = "seen_by" in d or "seen_by_source" in d
            if has_seen:
                sb, ss = d.get("seen_by"), d.get("seen_by_source")
                if not (isinstance(sb, str) and re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", sb) and int(sb[:4]) <= this_year and (len(sb) < 7 or 1 <= int(sb[5:7]) <= 12)):
                    errors.append(f"{path}: seen_by {sb!r} should be YYYY, YYYY-MM or YYYY-MM-DD (not after this year)")
                archive = isinstance(ss, str) and re.fullmatch(r"https://web\.archive\.org/web/\d{14}/https?://.+", ss)
                shop = isinstance(ss, str) and re.fullmatch(r"https://[^/\s]+/products/[^/\s]+", ss)
                manual = isinstance(ss, str) and any(ss in manual_links.get(x, ()) for x in d.get("documents", []))
                own_urls = {l.get("url") for l in d.get("links", []) if isinstance(l, dict) and "kind" not in l}
                own_urls |= set((d.get("sources") or {}).values())
                own_urls |= {doc_pages[x] for x in d.get("documents", []) if x in doc_pages}
                own_urls |= {product_urls[x] for x in d.get("documents", []) if x in product_urls}
                own_page = isinstance(ss, str) and ss in own_urls   # the maker's page we fetched first (the day it was on its site)
                video = isinstance(ss, str) and re.fullmatch(r"https://www\.youtube\.com/watch\?v=[\w-]+", ss)   # a back-catalogue video (the bound is its upload day)
                printed = isinstance(ss, str) and ss in printed_docs and isinstance(sb, str) and sb == printed_docs[ss]   # the document's printed date, as precise as printed
                # the maker's product sitemap that lists the record's page, its <lastmod> the day (on a host of the brand or of its links)
                maker_hosts = {urllib.parse.urlsplit(u).hostname for u in own_urls if isinstance(u, str) and u.startswith("https://")} | {brand_site.get(d.get("brand"))}
                sitemap = isinstance(ss, str) and re.fullmatch(r"https://[^\s/]+/\S+\.xml(\.gz)?", ss) and urllib.parse.urlsplit(ss).hostname in maker_hosts
                if not (archive or shop or manual or own_page or video or printed or sitemap):
                    errors.append(f"{path}: seen_by_source {ss!r} should be https://web.archive.org/web/<14-digit timestamp>/<original URL>, the maker's shop product page https://<host>/products/<handle>, the url or page of the release's own manual, the maker's page the release declares (its link, source, product page or document page), the maker's YouTube video of its first 60 days, or the maker's product sitemap (https://<host>/....xml) that lists the page")
                elif archive and not manual and isinstance(sb, str) and ss[len("https://web.archive.org/web/"):][:len(sb.replace("-", ""))] != sb.replace("-", ""):
                    errors.append(f"{path}: seen_by_source {ss} is not a capture of {sb}")
                if "released" in d or "year" in d or "announced" in d:
                    errors.append(f"{path}: seen_by is only for a release or part with no released, year or announced (a date a source states)")
        srcs = d.get("sources")
        if srcs is not None:
            if kind not in ("kit", "release", "part"):
                errors.append(f"{path}: sources is only for a kit, release or part")
            elif not (isinstance(srcs, dict) and srcs):
                errors.append(f"{path}: sources should be a non-empty table of field = https URL")
            else:
                for k, v in srcs.items():
                    if k in SOURCE_DATE_FIELDS:
                        errors.append(f"{path}: sources.{k} is not allowed: a date keeps its own {k}_source field")
                    elif k not in d:
                        errors.append(f"{path}: sources.{k} names a field the record does not have")
                    elif not (isinstance(v, str) and (v.startswith("https://") or
                              (v.startswith("http://") and urllib.parse.urlsplit(v).hostname in http_hosts))):
                        errors.append(f"{path}: sources.{k} should be an https URL (http only for a maker site that has no https), got {v!r}")
        ve = d.get("depicts") if kind in ("release", "part") else None
        if ve is not None:
            if kind == "part" and d.get("category") != "body":
                errors.append(f"{path}: depicts only on a release or a body shell (category body)")
            elif not (isinstance(ve, dict) and set(ve) <= {"make", "model", "year", "licensed"}
                      and ("make" not in ve or ve["make"] in VEHICLE_MAKES)
                      and isinstance(ve.get("model"), str) and ve["model"].strip() == ve["model"] and ve["model"]
                      and (("year" not in ve) or (isinstance(ve["year"], int) and not isinstance(ve["year"], bool) and 1885 <= ve["year"] <= datetime.date.today().year + 1))
                      and ve.get("licensed", True) is True):
                errors.append(f"{path}: depicts should be {{ make = <one of VEHICLE_MAKES> (optional when model is set), model = \"...\", year = 1885.. (optional), licensed = true (optional) }}, got {ve!r}")
        rq = d.get("requires") if kind == "release" else None
        if rq is not None and not (isinstance(rq, list) and rq and all(isinstance(x, str) and x.startswith(("kit/", "release/")) for x in rq)):
            errors.append(f"{path}: requires should be a list of kit or release ids (the car the release needs, one of them)")
        nd = d.get("needs")
        if nd is not None and kind != "release":
            errors.append(f"{path}: needs only on a release")
        elif nd is not None:
            if not (isinstance(nd, list) and nd):
                errors.append(f"{path}: needs should be a non-empty list of {{ part = \"part/...\" or item = \"...\", source = \"doc/...\", qty = 1.. (optional), note = \"...\" (optional) }}")
            for i, n in enumerate(nd if isinstance(nd, list) else []):
                if not isinstance(n, dict) or not (set(n) <= {"part", "item", "source", "qty", "note"}) or ("part" in n) == ("item" in n) or "source" not in n:
                    errors.append(f"{path}: needs[{i}] should have exactly one of part or item, and a source")
                    continue
                if "qty" in n and not (isinstance(n["qty"], int) and not isinstance(n["qty"], bool) and n["qty"] >= 1):
                    errors.append(f"{path}: needs[{i}].qty {n['qty']!r} should be an int of 1 or more")
                if "note" in n and not (isinstance(n["note"], str) and n["note"].strip()):
                    errors.append(f"{path}: needs[{i}].note should be a short string")
        se_ = d.get("series") if kind == "release" else None   # the car line a release belongs to (docs/schema.md "release")
        if se_ is not None and not (isinstance(se_, str) and se_.strip() and se_.strip() == se_):
            errors.append(f"{path}: series {se_!r} should be a non-empty string naming the car line")
        su = d.get("surface") if kind in ("release", "kit") else None
        if su is not None and not (isinstance(su, list) and su and all(x in SURFACES for x in su)):
            errors.append(f"{path}: surface {su!r} should be a list of {sorted(SURFACES)}")
        mh = d.get("mount_holes") if kind == "part" else None
        if mh is not None and (d.get("category") != "motor" or not isinstance(mh, list) or not mh or not all(
                isinstance(h, dict) and set(h) <= {"thread", "count", "circle_mm"} and {"thread", "circle_mm"} <= set(h)
                and isinstance(h["thread"], str) and re.fullmatch(r"M\d+(\.\d+)?", h["thread"])
                and h.get("count", 2) in (2, 3, 4, 6, 8, 12) and not isinstance(h.get("count"), bool) and isinstance(h["circle_mm"], (int, float)) and not isinstance(h["circle_mm"], bool)
                and 5 <= h["circle_mm"] <= 80 for h in mh)):
            errors.append(f"{path}: mount_holes should be a list of {{ thread = \"M3\", count = 2|3|4|6|8|12 (optional), circle_mm = 5..80 }} on a motor")
        mc = d.get("motor_can_mm") if kind == "part" else None
        if mc is not None and (isinstance(mc, bool) or not isinstance(mc, (int, float)) or not 15 <= mc <= 80
                               or d.get("category") not in ("motor", "cooling", "electronics", "chassis")):
            errors.append(f"{path}: motor_can_mm should be the can diameter 15..80 (mm) on a motor heat sink or fan mount (category cooling, motor, electronics or chassis)")
        lc = d.get("lipo_cells") if kind == "part" else None
        if lc is not None and not (isinstance(lc, list) and len(lc) == 2 and all(isinstance(x, int) for x in lc) and 0 < lc[0] <= lc[1]):
            errors.append(f"{path}: lipo_cells {lc!r} should be [min, max] cell counts")
        bc = d.get("balance_connector") if kind == "part" else None
        if bc is not None:
            nc = d.get("cells")
            if d.get("category") != "battery" or not isinstance(bc, str) or not bc.strip():
                errors.append(f"{path}: balance_connector only on batteries, as a plug name (JST-XH)")
            elif bc == "JST-XH" and not (isinstance(nc, int) and not isinstance(nc, bool) and 1 <= nc <= 8
                                         and os.path.exists(os.path.join(ROOT, "specs", "connector", f"jst-xh-{nc + 1}.toml"))):
                errors.append(f"{path}: balance_connector JST-XH needs cells 1..8 (the spec jst-xh-<cells+1> must exist)")
        bb = d.get("balance_connector_basis") if kind == "part" else None
        if bb is not None or (bc is not None and kind == "part"):
            if bc is None or bb not in ("maker", "convention"):
                errors.append(f"{path}: balance_connector_basis is \"maker\" (the maker's text names the plug) or \"convention\" (LiPo, LiHV or LiFe 2S to 8S, no statement), and only with balance_connector")
        se = d.get("sensored") if kind == "part" else None
        if se is not None and (not isinstance(se, bool) or d.get("category") not in ("motor", "esc", "electronics")):
            errors.append(f"{path}: sensored should be true or false, on a motor or an ESC (category esc; motor and electronics systems too)")
        if kind == "part" and d.get("category") == "motor" and d.get("motor_type") == "both":
            errors.append(f"{path}: motor_type both is for ESCs only (a motor is brushed or brushless)")
        if kind == "part" and any(k in d for k in ESC_PROP_FIELDS if k not in ("motor_type", "nimh_cells")) and d.get("category") not in ("esc", "motor"):
            errors.append(f"{path}: {', '.join(k for k in ESC_PROP_FIELDS if k in d and k not in ('motor_type', 'nimh_cells'))} only on ESCs (category esc) or 2-in-1 motors (category motor, ESC built in)")
        if kind == "part" and "motor_type" in d and d.get("category") not in ("esc", "motor"):
            errors.append(f"{path}: motor_type only on ESCs and motors (category esc or motor)")
        if kind == "part" and "waterproof" in d:
            if d.get("category") not in WATERPROOF_CATEGORIES:
                errors.append(f"{path}: waterproof only on {', '.join(WATERPROOF_CATEGORIES)} parts (docs/schema.md \"ESCs\")")
            elif not isinstance(d["waterproof"], bool):
                errors.append(f"{path}: waterproof should be true or false")
        if kind == "part" and "scales" in d:
            sc = d["scales"]
            if d.get("category") not in SCALES_CATEGORIES:
                errors.append(f"{path}: scales only on {', '.join(SCALES_CATEGORIES)} parts (docs/schema.md \"scales\")")
            elif not (isinstance(sc, list) and sc and len(set(sc)) == len(sc) and all(isinstance(x, str) and SCALE_RE.fullmatch(x) for x in sc)):
                errors.append(f"{path}: scales {sc!r} should be a list of scales like [\"1/10\", \"1/12\"]")
        if kind == "part" and "nimh_cells" in d and d.get("category") not in ("esc", "motor", "charger"):
            errors.append(f"{path}: nimh_cells only on ESCs, 2-in-1 motors (ESC built in) and chargers")
        if kind == "part" and d.get("category") == "esc":
            def _isnum(x, lo, hi):
                return isinstance(x, (int, float)) and not isinstance(x, bool) and lo <= x <= hi
            bv = d.get("bec_v")
            if bv is not None and not (_isnum(bv, 1, 24) or (isinstance(bv, list) and len(bv) >= 2 and len(set(bv)) == len(bv) and all(_isnum(x, 1, 24) for x in bv))):
                errors.append(f"{path}: bec_v {bv!r} should be a voltage (1..24) or a list of two or more when switchable")
            ba = d.get("bec_a")
            if ba is not None and not _isnum(ba, 0.1, 50):
                errors.append(f"{path}: bec_a {ba!r} should be the BEC current in A (0.1..50)")
            mlt = d.get("motor_limit_t")
            if mlt is not None and not _isnum(mlt, 1, 80):
                errors.append(f"{path}: motor_limit_t {mlt!r} should be the lowest motor turns allowed (1..80)")
            mlk = d.get("motor_limit_kv")
            if mlk is not None and not (isinstance(mlk, int) and not isinstance(mlk, bool) and 500 <= mlk <= 20000):
                errors.append(f"{path}: motor_limit_kv {mlk!r} should be a kV figure (int, 500..20000)")
            nc = d.get("nimh_cells")
            if nc is not None and not (isinstance(nc, list) and len(nc) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in nc) and 0 < nc[0] <= nc[1]):
                errors.append(f"{path}: nimh_cells {nc!r} should be [min, max] cell counts")
            pg = d.get("programming")
            if pg is not None and not (isinstance(pg, list) and pg and len(set(pg)) == len(pg) and all(x in ESC_PROGRAMMING for x in pg)):
                errors.append(f"{path}: programming {pg!r} should be a list of {sorted(ESC_PROGRAMMING)}")
            rm = d.get("resistance_mohm")
            if rm is not None and not _isnum(rm, 0.01, 100):
                errors.append(f"{path}: resistance_mohm {rm!r} should be the internal resistance in milliohms (0.01..100)")
        if kind == "part":
            present = [k for k in CHARGER_FIELDS if k in d]
            if present and d.get("category") != "charger":
                errors.append(f"{path}: {', '.join(present)} only on chargers (category charger)")
            if d.get("category") == "charger":
                errors.extend(check_charger(path, d))
        if kind == "part" and any(k in d for k in SERVO_FIELDS) and d.get("category") != "servo":
            errors.append(f"{path}: {', '.join(k for k in SERVO_FIELDS if k in d)} only on servos (category servo)")
        if kind == "part" and d.get("category") == "servo":
            bn, bk, db, fq = (d.get(k) for k in SERVO_FIELDS)
            if bn is not None and not (isinstance(bn, int) and not isinstance(bn, bool) and 1 <= bn <= 10):
                errors.append(f"{path}: bearings {bn!r} should be a count of 1 to 10")
            if bk is not None and bk not in SERVO_BEARING_KIND:
                errors.append(f"{path}: bearing_kind {bk!r} should be one of {sorted(SERVO_BEARING_KIND)}")
            if db is not None and not (isinstance(db, int) and not isinstance(db, bool) and 1 <= db <= 100):
                errors.append(f"{path}: dead_band_us {db!r} should be whole microseconds, 1 to 100")
            if fq is not None:
                one = isinstance(fq, int) and not isinstance(fq, bool) and 30 <= fq <= 5000
                rng = isinstance(fq, list) and len(fq) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in fq) \
                    and 30 <= fq[0] < fq[1] <= 5000
                if not (one or rng):
                    errors.append(f"{path}: frequency_hz {fq!r} should be an int (hz) or [low, high] in hz, 30 to 5000")
        if kind == "spec" and d.get("category") == "wire":
            awg = d.get("awg")
            if not (isinstance(awg, int) and not isinstance(awg, bool) and 8 <= awg <= 30):
                errors.append(f"{path}: wire spec needs awg, the gauge from 8 to 30")
            elif d["id"] != f"spec/wire/{awg}awg":
                errors.append(f"{path}: wire spec id should be spec/wire/{awg}awg")
            for k in ("conductor_mm", "conductor_in", "cross_section_mm2"):
                if not (isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool) and d[k] > 0):
                    errors.append(f"{path}: wire spec needs {k} > 0")
        if kind == "part" and ("thickness_mm" in d or "thickness_basis" in d):
            tm = d.get("thickness_mm")
            if d.get("category") not in ("body", "wing", "body-accessory"):
                errors.append(f"{path}: thickness_mm only on a body, wing or body-accessory part (the shell's thickness)")
            elif not (isinstance(tm, (int, float)) and not isinstance(tm, bool) and 0.1 <= tm <= 5):
                errors.append(f"{path}: thickness_mm {tm!r} should be the shell thickness in mm, 0.1 to 5")
            if "thickness_basis" in d and "thickness_mm" not in d:
                errors.append(f"{path}: thickness_basis needs thickness_mm")
        if kind == "part" and "width_basis" in d and not (d.get("category") == "body" and isinstance(d.get("width_mm"), (int, float))):
            errors.append(f"{path}: width_basis needs width_mm on a body")
        WIRE_ONLY = ("wire_awg", "insulation", "strands", "shrink_ratio", "flat_width_mm")
        if kind == "part" and any(k in d for k in WIRE_ONLY) and d.get("category") != "wire":
            errors.append(f"{path}: {', '.join(k for k in WIRE_ONLY if k in d)} only on wires (category wire)")
        if kind == "part" and d.get("category") == "wire":
            wa = d.get("wire_awg")
            if wa is not None:
                ok_one = isinstance(wa, int) and not isinstance(wa, bool) and 4 <= wa <= 32
                ok_two = isinstance(wa, list) and len(wa) == 2 and all(isinstance(x, int) and not isinstance(x, bool) and 4 <= x <= 32 for x in wa) and wa[0] != wa[1]
                if not (ok_one or ok_two):
                    errors.append(f"{path}: wire_awg {wa!r} should be a gauge from 4 to 32, or two gauges as a list")
            st = d.get("strands")
            if st is not None and not (isinstance(st, int) and not isinstance(st, bool) and 2 <= st <= 100000):
                errors.append(f"{path}: strands {st!r} should be a count of 2 or more")
            sr = d.get("shrink_ratio")
            if sr is not None and not (isinstance(sr, (int, float)) and not isinstance(sr, bool) and 1 <= sr <= 10):
                errors.append(f"{path}: shrink_ratio {sr!r} should be the ratio as a number (2:1 is 2), 1 to 10")
            fw = d.get("flat_width_mm")
            if fw is not None and not (isinstance(fw, (int, float)) and not isinstance(fw, bool) and fw > 0):
                errors.append(f"{path}: flat_width_mm {fw!r} should be a width in mm")
            dm = d.get("diameter_mm")
            if dm is not None:
                vals = dm if isinstance(dm, list) else [dm]
                if not (vals and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in vals)):
                    errors.append(f"{path}: diameter_mm {dm!r} should be a size in mm, or a list of sizes")
        if kind == "part" and "radio_unit" in d and d.get("category") not in ("radio", "esc"):
            errors.append(f"{path}: radio_unit only on radios and receivers (category radio, or esc for an ESC with a receiver)")
        # weight_g and teeth on any part (docs/schema.md "part"): grams as a number, a tooth count as an integer
        if kind == "part" and "weight_g" in d:
            w = d["weight_g"]
            if isinstance(w, bool) or not isinstance(w, (int, float)) or not 0 < w <= 50000:
                errors.append(f"{path}: weight_g {w!r} should be grams above 0 and up to 50000")
        if kind == "part" and "teeth" in d:
            t = d["teeth"]
            if isinstance(t, bool) or not isinstance(t, int) or not 5 <= t <= 300:
                errors.append(f"{path}: teeth {t!r} should be a whole tooth count from 5 to 300")
        eng = ENGINE_FIELDS & d.keys() if kind == "part" else set()
        if eng - {"bore_mm"} and d.get("category") != "engine-fuel":
            errors.append(f"{path}: {', '.join(sorted(eng - {'bore_mm'}))} only on engine parts (category engine-fuel)")
        if d.get("category") != "engine-fuel":
            eng = set()
        for k in eng & set(ENGINE_NUM):
            lo, hi = ENGINE_NUM[k]
            if isinstance(d[k], bool) or not isinstance(d[k], (int, float)) or not lo <= d[k] <= hi or (k == "output_rpm" and not isinstance(d[k], int)):
                errors.append(f"{path}: {k} {d[k]!r} should be a number from {lo} to {hi}")
        if "engine_class" in eng and not (isinstance(d["engine_class"], str) and re.fullmatch(r"\.\d\d", d["engine_class"])):
            errors.append(f"{path}: engine_class {d['engine_class']!r} should be a class like \".21\"")
        rr = d.get("rpm_range") if "rpm_range" in eng else None
        if rr is not None and not (isinstance(rr, list) and len(rr) == 2 and all(isinstance(x, int) and 500 <= x <= 60000 for x in rr) and rr[0] < rr[1]):
            errors.append(f"{path}: rpm_range {rr!r} should be [min, max] rpm")
        if kind == "spec" and "type" in d:
            allowed = SPEC_TYPES.get(d.get("category"), set())
            if d["type"] not in allowed:
                errors.append(f"{path}: spec.type = {d['type']!r} not in {sorted(allowed)} for a {d.get('category')} spec")
        if kind == "spec" and d.get("category") in ("screw", "pin"):
            lm = d.get("length_mm")
            if not isinstance(lm, (int, float)) or isinstance(lm, bool) or lm <= 0:
                errors.append(f"{path}: {d['category']} spec needs length_mm above 0 (a pitch or an OCR zero is not a length)")
        if kind == "spec" and d.get("category") == "nut":
            if not re.fullmatch(r"M\d{1,2}(\.\d)?(x\d(\.\d{1,2})?)?", str(d.get("thread", ""))):
                errors.append(f"{path}: nut spec needs a thread like \"M3\" or \"M5x0.5\"")
            if "type" not in d:
                errors.append(f"{path}: nut spec needs a type")
            if "profile" in d and d.get("type") not in NUT_PROFILED:
                errors.append(f"{path}: profile only on {sorted(NUT_PROFILED)} nuts")
            for k in ("across_flats_mm", "height_mm"):
                if k in d and not (isinstance(d[k], (int, float)) and 0.5 <= d[k] <= 40):
                    errors.append(f"{path}: {k} {d[k]!r} should be millimetres")
        if kind == "spec" and d.get("category") == "washer":
            b, o, t = (d.get(k) for k in ("bore_mm", "outer_mm", "thickness_mm"))
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in (b, o, t)) or not b < o:
                errors.append(f"{path}: washer spec needs bore_mm, outer_mm and thickness_mm in millimetres, the bore under the outer")
            else:
                sid = f"spec/washer/{d['shape'] + '-' if d.get('shape') not in (None, 'flat') else ''}{b}x{o}x{t}"
                if d["id"] != sid:
                    errors.append(f"{path}: washer spec id should be {sid} (shape prefix, then bore x outer x thickness)")
        if kind == "spec" and d.get("category") == "pin" and d.get("type") == "screw":
            dm, lm = d.get("diameter_mm"), d.get("length_mm")
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in (dm, lm)):
                errors.append(f"{path}: screw pin spec needs diameter_mm and length_mm in millimetres")
            elif d["id"] != f"spec/pin/{dm:g}x{lm:g}-screw":
                errors.append(f"{path}: screw pin spec id should be spec/pin/{dm:g}x{lm:g}-screw")
            if "thread" in d and d["thread"] != f"M{dm:g}":
                errors.append(f"{path}: screw pin thread {d['thread']!r} should be M{dm:g} (the diameter) unless the name states another, which is not yet in the data")
        elif kind == "spec" and d.get("category") == "pin" and "thread" in d:
            errors.append(f"{path}: thread only on screw pin specs (type screw)")
        if kind == "spec" and d.get("category") == "bearing":
            fields = [k for k in ("flange_mm", "flange_width_mm", "flange_source") if k in d]
            if fields and d.get("type") != "flanged":
                errors.append(f"{path}: {', '.join(fields)} only on flanged bearings")
            if d.get("type") == "flanged" and fields:
                fm, fw = d.get("flange_mm"), d.get("flange_width_mm")
                if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in (fm, fw)):
                    errors.append(f"{path}: flange_mm and flange_width_mm need numbers in millimetres")
                elif not fm > d.get("outer_mm", 0):
                    errors.append(f"{path}: flange_mm {fm} should be larger than outer_mm")
                if not str(d.get("flange_source", "")).startswith("https://"):
                    errors.append(f"{path}: flange_source should be the catalogue page URL")
        if kind == "spec" and d.get("category") in SIZE_SPEC_CATS:
            errors.extend(size_spec_problems(path, d))
        if kind == "spec" and d.get("category") == "eclip":
            s = d.get("shaft_mm")
            if not isinstance(s, (int, float)) or isinstance(s, bool) or not 1 <= s <= 12:
                errors.append(f"{path}: e-clip spec needs shaft_mm, the shaft it fits (1 to 12 mm)")
            else:
                suffix = "-bowed" if d.get("variant") == "bowed" else f"-{d['thickness_mm']}" if "thickness_mm" in d else ""
                sid = f"spec/eclip/{s}mm{suffix}"
                if d["id"] != sid:
                    errors.append(f"{path}: e-clip spec id should be {sid} (shaft, then thickness or bowed)")
        if kind == "spec":
            for code in d.get("standards", []):
                if code not in codes:
                    errors.append(f"{path}: standard {code!r} has no data/standards entry (code = {code!r})")
        if kind == "release" and "released" in d:
            rd = str(d["released"])
            if not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", rd):
                errors.append(f"{path}: released {rd!r} is not YYYY, YYYY-MM or YYYY-MM-DD")
            elif "year" in d and int(rd[:4]) != d["year"]:
                errors.append(f"{path}: released {rd} does not match year {d['year']}")
        if kind == "category":
            if "any_car" in d and d["any_car"] is not True:
                errors.append(f"{path}: any_car is true or left out")
            for kf in d.get("key_fields", []):
                if not kf.get("field") or not kf.get("label") or kf.get("from") not in ("part", "spec"):
                    errors.append(f"{path}: key_fields entry {kf!r} needs field, label and from = part|spec")
                elif not all(isinstance(kf.get(k, False), bool) for k in ("compare_only", "multi", "plug", "pick")):
                    errors.append(f"{path}: key_fields compare_only, multi, plug and pick must be true or false")
                elif kf.get("filter", "range") != "range":
                    errors.append(f"{path}: key_fields filter is \"range\" (a from-to box on the column's largest number)")
                elif kf["from"] == "spec" and not d.get("spec_type"):
                    errors.append(f"{path}: key field {kf['field']} comes from the spec, but the category names no spec")
        # when a brand launched and ended (docs/schema.md "brand"): ISO dates at the precision the source gives, each with its source
        if kind == "brand":
            for f in ("launched", "ended"):
                if f not in d:
                    if f"{f}_source" in d:
                        errors.append(f"{path}: {f}_source needs {f}")
                    continue
                if not (isinstance(d[f], str) and re.fullmatch(r"\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?", d[f])):
                    errors.append(f"{path}: {f} {d[f]!r} must be an ISO date string: \"2016\", \"2016-03\" or \"2016-03-01\"")
                src = str(d.get(f"{f}_source", ""))
                if not (src.startswith(("https://", "http://")) or src in ids):
                    errors.append(f"{path}: {f} needs {f}_source: the URL of the page, or the doc/ id of the document, that states it")
            if d.get("status") == "gone" and "ended" not in d:
                errors.append(f"{path}: a gone brand needs ended (when it stopped), with ended_source")
            if "ended" in d and d.get("status") != "gone":
                errors.append(f"{path}: ended is set, so status must be gone")
            if "launched" in d and "ended" in d and d["ended"][:len(d["launched"])] < d["launched"][:len(d["ended"])]:
                errors.append(f"{path}: ended {d['ended']} is before launched {d['launched']}")
        # a brand's official YouTube channels (docs/schema.md "brand"): a list of channel URLs
        if kind == "brand" and "youtube" in d:
            if not (isinstance(d["youtube"], list) and d["youtube"]
                    and all(isinstance(u, str) and YOUTUBE_CHANNEL.fullmatch(u) for u in d["youtube"])):
                errors.append(f"{path}: youtube should be a list of https://www.youtube.com/@<handle> URLs")
        # the company that owns a brand (docs/schema.md "company"): stated on a page of the brand or the company
        if kind == "brand" and ("owner_source" in d or "owner_since" in d) and "owner" not in d:
            errors.append(f"{path}: owner_source and owner_since need an owner")
        if kind == "brand" and "owner" in d:
            src = str(d.get("owner_source", ""))
            if src.startswith("doc/"):
                if src not in ids:
                    errors.append(f"{path}: owner_source -> {src} does not exist")
            elif not src.startswith(("https://", "http://")):
                errors.append(f"{path}: owner needs owner_source: the URL of the page, or the doc/ id of the document, that states it")
        if kind == "brand" and "owner_since" in d and not (isinstance(d["owner_since"], int) and 1900 <= d["owner_since"] <= datetime.date.today().year):
            errors.append(f"{path}: owner_since should be a year")
        if kind == "company":
            if d.get("parent") == d.get("id"):
                errors.append(f"{path}: a company cannot be its own parent")
            if "website" in d and not str(d["website"]).startswith(("https://", "http://")):
                errors.append(f"{path}: website should be a URL")
        if kind == "brand" and not isinstance(d.get("item_numbers", True), bool):
            errors.append(f"{path}: item_numbers must be true or false")
        if kind == "part" and "number" not in d:
            if not no_numbers.get(d.get("brand")):
                errors.append(f"{path}: missing required field number (only parts of a brand with item_numbers = false go without)")
        elif kind == "part" and not re.match(r"^[A-Za-z0-9][A-Za-z0-9.+\-]*$", str(d.get("number", ""))):
            errors.append(f"{path}: odd part number {d.get('number')!r}")
    # numbers: the part's other numbers (the maker's number of a part sold under a store number); one record per part
    claimed = {}
    for path, kind, d in docs:
        if kind == "part" and d.get("number"):
            claimed[(d.get("brand"), str(d["number"]).upper())] = d.get("id")
    for path, kind, d in docs:
        if kind != "part" or "numbers" not in d:
            continue
        nums = d["numbers"]
        if not isinstance(nums, list) or not nums or not all(isinstance(n, str) and re.match(r"^[A-Za-z0-9][A-Za-z0-9.+\-]*$", n) for n in nums):
            errors.append(f"{path}: numbers should be a non-empty list of part numbers")
            continue
        if len(set(nums)) != len(nums) or d.get("number") in nums:
            errors.append(f"{path}: numbers repeats a number or the part's own number")
        for n in nums:
            other = claimed.setdefault((d.get("brand"), n.upper()), d.get("id"))
            if other != d.get("id"):
                errors.append(f"{path}: number {n} is also {other}: one record per part")
    counts = {}
    for _, kind, _ in docs:
        counts[kind] = counts.get(kind, 0) + 1
    supersedes = {d["id"]: d["supersedes"] for _, kind, d in docs if kind == "release" and isinstance(d.get("supersedes"), str)}
    for start in supersedes:   # a chain of releases that replace each other must end, never loop
        seen, cur = [], start
        while cur in supersedes:
            if cur in seen:
                errors.append(f"supersedes cycle: {' -> '.join(seen[seen.index(cur):] + [cur])}")
                break
            seen.append(cur)
            cur = supersedes[cur]
    body_parts = {d.get("id") for _, kind, d in docs if kind == "part" and d.get("category") == "body"}
    counts["art"] = check_art(ids, errors, body_parts)
    check_release_related(docs, errors)
    check_release_ranges(docs, errors)
    check_release_power(docs, ids, errors)
    check_kit_supersedes(docs, errors)
    check_makes(docs, errors)
    check_dealer_links(docs, errors)
    check_connectors(docs, ids, errors)
    check_protocols(docs, ids, errors)
    check_plugs(docs, ids, errors)
    check_receiver_plugs(docs, ids, errors)
    check_names_no_brand(docs, errors)
    check_former_names(docs, errors)
    check_part_category(docs, errors)
    check_case_clashes(errors)
    print("entities:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if errors:
        print(f"{len(errors)} error(s):")
        for e in errors[:200]:
            print(" ", e)
        sys.exit(1)
    print("ok")

if __name__ == "__main__":
    main()
