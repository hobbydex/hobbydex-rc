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
    "release": ["id", "kit", "brand", "name", "kind", "status"],   # year: optional, left out when unknown
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
    "publisher": "brand/", "replaces": "part/", "supersedes": "part/", "replaced_by": "standard/",
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

ENUMS = {
    "release.status": {"announced", "released", "discontinued"},
    "release.kind": {"kit", "rtr", "arr"},
    # kit types (docs/schema.md "kit"); the site gives each a label and an icon (hobbydex src/lib/kitTypes.ts)
    "kit.category": {"buggy", "truggy", "stadium-truck", "short-course", "monster", "desert-truck", "truck", "race-truck",
                     "crawler", "touring", "formula", "pan-car", "rally", "street-basher", "drift", "drag", "lowrider", "trailer",
                     "speed-run", "kart", "motorcycle", "tank", "construction", "car", "boat", "oval"},
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
    "part.status": {"available", "discontinued"},   # docs/schema.md "part"; set only where the maker or a shop states it
    "part.category_source": {"curated"},
    "part.seal": {"open", "metal", "rubber", "rubber-metal"},
    "part.lubricant": {"oil", "grease"},
    "part.viscosity": {"thin", "medium", "thick"},
    "spec.profile": {"regular", "thin"},
    "spec.shape": {"flat", "countersunk", "conical"},   # washer specs (docs/schema.md "Washer specs")
    "spec.variant": {"bowed"},   # e-clip specs (docs/schema.md "E-clip specs")
    "spec.motor_type": {"brushed", "brushless"},
    "spec.chemistry": {"lipo", "lihv", "life", "nimh"},
    "part.chemistry": {"lipo", "lihv", "life", "nimh"},
    "part.case": {"hard", "soft", "shorty"},
    "part.name_source": {"ocr", "manufacturer", "manual"},
    "part.ball_type": {"stud", "nut", "through-hole", "set-screw"},
    "part.paint_type": {"polycarbonate", "lacquer", "acrylic", "enamel"},
    "part.application": {"spray-can", "airbrush", "brush", "marker"},
    "part.paint_role": {"paint", "clear", "primer", "thinner", "cleaner", "masking"},
    "part.fuel": {"nitro", "gasoline"},
    # what a radio part is (docs/schema.md "documents"): set = a transmitter sold with its receiver
    "part.radio_unit": {"transmitter", "receiver", "set"},
    "part.shock_part": {"complete", "body", "shaft", "piston", "cap", "rebuild-kit", "rod-end", "spring-cup"},
}
# engine fields (docs/schema.md "Engines"): only on engine-fuel parts, numbers in these ranges
# servo spec fields (docs/schema.md "Servos"): bearings, bearing_kind, dead_band_us, frequency_hz
SERVO_FIELDS = ("bearings", "bearing_kind", "dead_band_us", "frequency_hz")
SERVO_BEARING_KIND = {"ball", "bushing"}
ENGINE_NUM = {"displacement_cc": (0.5, 120), "bore_mm": (5, 60), "stroke_mm": (5, 60), "output_hp": (0.05, 20), "output_rpm": (1000, 60000)}
ENGINE_FIELDS = set(ENGINE_NUM) | {"engine_class", "rpm_range", "fuel"}   # bore_mm is also a shock's bore: checked on engines only
PAINT_FINISH = {"gloss", "flat", "semi-gloss", "metallic", "pearl", "fluorescent", "translucent", "clear", "chrome", "flake"}   # part.finish of a paint; other parts' finish ("black oxide") is free

# spec.type per spec category (docs/schema.md: bearing types, nut types)
SPEC_TYPES = {
    "bearing": {"radial-ball", "flanged", "thrust"},
    "nut": {"hex", "nylon-lock", "metal-lock", "lock", "flanged", "flanged-lock", "flanged-nylon-lock", "serrated-flange",
            "serrated-flange-nylon-lock", "dome", "flanged-dome", "square", "knurled", "wing", "wheel"},
}
NUT_PROFILED = {"hex", "nylon-lock", "metal-lock", "lock"}   # the types that come in a regular and a thin height

# which part categories may be `equivalent_to` a spec of each kind
SPEC_PART_CATS = {
    "bearing": {"bearing"}, "screw": {"screw"}, "pin": {"pin-clip"}, "pinion": {"pinion"}, "oil": {"oil-grease"},
    "battery": {"battery"}, "motor": {"motor"}, "servo": {"servo"}, "nut": {"nut"},
    "washer": {"washer-shim"}, "eclip": {"pin-clip"},
    "wheel-hex": {"drivetrain", "wheel", "tire", "suspension"},   # hexes, wheels and tyres with a hex, hubs and axles
}

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
        maker = [l.get("site") for l in links if "kind" not in l]
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
            if rel == "retired.toml":
                continue   # retired ids, checked below
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
    codes = {d.get("code") for _, kind, d in docs if kind == "standard"}
    no_numbers = {d.get("id"): d.get("item_numbers") is False for _, kind, d in docs if kind == "brand"}   # makers that print no item numbers
    release_kit = {d.get("id"): d.get("kit") for _, kind, d in docs if kind == "release"}
    manual_links = {d.get("id"): {d[k] for k in ("url", "page") if d.get(k)} for _, kind, d in docs if kind == "doc" and d.get("kind") == "manual"}   # a manual's own file or maker page
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
        if kind == "part" and any(isinstance(f, dict) and f.get("kit") in placeholder_kits for f in d.get("fits", []) or []):
            errors.append(f"{path}: fits a placeholder kit; a placeholder holds no parts or fits of its own")
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
            if key in ENUMS and v not in ENUMS[key]:
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
            elif "kind" in l and l["kind"] not in ("fan-site", "press", "dealer"):
                errors.append(f"{path}: link kind = {l['kind']!r} not in ['fan-site', 'press', 'dealer']")
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
            has_seen = "seen_by" in d or "seen_by_source" in d
            if has_seen:
                sb, ss = d.get("seen_by"), d.get("seen_by_source")
                if not (isinstance(sb, str) and re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", sb) and int(sb[:4]) <= this_year and (len(sb) < 7 or 1 <= int(sb[5:7]) <= 12)):
                    errors.append(f"{path}: seen_by {sb!r} should be YYYY, YYYY-MM or YYYY-MM-DD (not after this year)")
                archive = isinstance(ss, str) and re.fullmatch(r"https://web\.archive\.org/web/\d{14}/https?://.+", ss)
                shop = isinstance(ss, str) and re.fullmatch(r"https://[^/\s]+/products/[^/\s]+", ss)
                manual = isinstance(ss, str) and any(ss in manual_links.get(x, ()) for x in d.get("documents", []))
                if not (archive or shop or manual):
                    errors.append(f"{path}: seen_by_source {ss!r} should be https://web.archive.org/web/<14-digit timestamp>/<original URL>, the maker's shop product page https://<host>/products/<handle>, or the url or page of the release's own manual")
                elif archive and not manual and isinstance(sb, str) and ss[len("https://web.archive.org/web/"):][:len(sb.replace("-", ""))] != sb.replace("-", ""):
                    errors.append(f"{path}: seen_by_source {ss} is not a capture of {sb}")
                if "released" in d or "year" in d or "announced" in d:
                    errors.append(f"{path}: seen_by is only for a release with no released, year or announced (a date a source states)")
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
                               or d.get("category") not in ("motor", "electronics", "chassis")):
            errors.append(f"{path}: motor_can_mm should be the can diameter 15..80 (mm) on a motor heat sink or fan mount (category motor, electronics or chassis)")
        lc = d.get("lipo_cells") if kind == "part" else None
        if lc is not None and not (isinstance(lc, list) and len(lc) == 2 and all(isinstance(x, int) for x in lc) and 0 < lc[0] <= lc[1]):
            errors.append(f"{path}: lipo_cells {lc!r} should be [min, max] cell counts")
        se = d.get("sensored") if kind == "part" else None
        if se is not None and (not isinstance(se, bool) or d.get("category") not in ("motor", "electronics")):
            errors.append(f"{path}: sensored should be true or false, on a motor or an ESC (category electronics)")
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
        if kind == "part" and "radio_unit" in d and d.get("category") != "electronics":
            errors.append(f"{path}: radio_unit only on radios and receivers (category electronics)")
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
            for kf in d.get("key_fields", []):
                if not kf.get("field") or not kf.get("label") or kf.get("from") not in ("part", "spec"):
                    errors.append(f"{path}: key_fields entry {kf!r} needs field, label and from = part|spec")
                elif not isinstance(kf.get("compare_only", False), bool):
                    errors.append(f"{path}: key_fields compare_only must be true or false")
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
    check_kit_supersedes(docs, errors)
    check_makes(docs, errors)
    check_dealer_links(docs, errors)
    check_names_no_brand(docs, errors)
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
