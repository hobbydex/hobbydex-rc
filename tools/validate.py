"""Validate every TOML file under data/.

Checks: file parses, the file is where tools/layout.py puts its id, required
fields per entity kind, every reference resolves, no duplicate ids, no two paths
that differ only in case. Also the art under art/ (see check_art). Exit code 1 on any error.

Run from the repo root: python3 -I tools/validate.py
"""
import datetime, os, re, sys, tomllib
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
}
KINDS = {k: dict(dir=DIRS[k], required=REQUIRED[k]) for k in REQUIRED}
REFS = {  # field -> expected id prefix
    "brand": "brand/", "kit": "kit/", "part": "part/", "spec": "spec/", "source": "doc/",
    "publisher": "brand/", "replaces": "part/", "supersedes": "part/", "replaced_by": "standard/",
}
LIST_REFS = {"documents": "doc/", "releases": "release/", "requires": ""}   # requires: kit or release ids, checked above
# real vehicle makes a release or body shell may depict (docs/schema.md "release", depicts); curated, add a make here first
VEHICLE_MAKES = {
    "Abarth", "Acura", "Alfa Romeo", "Alpine", "Aston Martin", "Audi", "BMW", "Bentley", "Bugatti", "Buggyra", "Buick", "Cadillac",
    "Can-Am", "Caterpillar", "Chevrolet", "Citroen", "DAF", "Datsun", "DeLorean", "Dodge", "Ducati", "Ferrari", "Fiat", "Ford",
    "Freightliner", "GMC", "Hino", "Honda", "Hummer", "Hyundai", "International", "Isuzu", "Iveco", "Jaguar", "Jeep", "KTM",
    "Kawasaki", "Kenworth", "Komatsu", "Lamborghini", "Lancia", "Land Rover", "Lexus", "Liebherr", "Lotus", "MAN", "Mack",
    "Maserati", "Mazda", "McLaren", "Mercedes-Benz", "Mini", "Mitsubishi", "Nissan", "Opel", "Pagani", "Peterbilt", "Peugeot",
    "Plymouth", "Polaris", "Pontiac", "Porsche", "Ram", "Renault", "Scania", "Seat", "Shelby", "Skoda", "Subaru", "Suzuki",
    "Toyota", "Tyrrell", "UAZ", "Vauxhall", "Volkswagen", "Volvo", "Willys", "Yamaha",
}
SURFACES = {"carpet", "astro", "clay", "dirt", "asphalt", "high-grip"}   # the track surface a race kit is built for

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
    "contains.role": {"kit", "option", "listed"},
    "doc.kind": {"manual", "part_list", "exploded_view", "supplement", "catalog", "setup_sheet", "product_page", "owner_report"},
    "equivalent_to.match": {"exact", "functional", "close"},
    "fits.type": {"direct", "replaces", "modification"},
    "rebrand_of.parts": {"interchangeable", "partly", "unknown"},
    "related.relation": {"requires", "fits", "use-with", "for", "replaces", "same-colour"},
    "same_platform_as.parts": {"interchangeable", "partly", "unknown"},
    "part.material": {"steel", "stainless", "titanium", "aluminium", "brass", "bronze", "plastic", "carbon", "ceramic", "carbide", "unknown"},
    "part.category_source": {"curated"},
    "part.seal": {"open", "metal", "rubber", "rubber-metal"},
    "part.lubricant": {"oil", "grease"},
    "part.viscosity": {"thin", "medium", "thick"},
    "spec.profile": {"regular", "thin"},
    "spec.shape": {"flat", "countersunk", "conical"},   # washer specs (docs/schema.md "Washer specs")
    "spec.motor_type": {"brushed", "brushless"},
    "spec.chemistry": {"lipo", "lihv", "life", "nimh"},
    "part.chemistry": {"lipo", "lihv", "life", "nimh"},
    "part.case": {"hard", "soft", "shorty"},
    "part.name_source": {"ocr", "manufacturer"},
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
    "washer": {"washer-shim"},
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

def check_art(ids, errors):
    """art/<kits|releases>/<brand>/<key>.svg: our own outline of a kit or release, drawn by the site in its
    colours. One line: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 24"> with one or more
    <path d="..."/> and nothing else (no fill, style, transform, class or title), at most ART_MAX bytes,
    named after a kit or release that exists. Returns the number of art files."""
    lower = {i.lower(): i for i in ids if isinstance(i, str)}
    dirs = {DIRS[k]: k for k in ART_KINDS}
    n = 0
    for dirpath, _, files in os.walk(ART_ROOT):
        for fn in sorted(files):
            path = os.path.join(dirpath, fn)
            parts = os.path.relpath(path, ART_ROOT).split(os.sep)
            if len(parts) != 3 or parts[0] not in dirs or not fn.endswith(".svg"):
                errors.append(f"{path}: art goes in {ART_ROOT}/kits/<brand>/<slug>.svg or {ART_ROOT}/releases/<brand>/<key>.svg")
                continue
            n += 1
            eid = f"{dirs[parts[0]]}/{parts[1]}/{fn[:-4]}"
            if os.path.normpath(art_path(eid, ART_ROOT)) != os.path.normpath(path):
                errors.append(f"{path}: art for {eid} belongs at {art_path(eid, ART_ROOT)}")
            if eid not in ids:
                hint = f" (the id is {lower[eid.lower()]}: names match the id exactly)" if eid.lower() in lower else ""
                errors.append(f"{path}: orphan art, no {eid}{hint}")
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
    for path, kind, d in docs:
        def check_ref(field, value, where):
            prefix = REFS.get(field)
            if prefix is None:
                return
            if not isinstance(value, str) or not value.startswith(prefix):
                errors.append(f"{path}: {where}{field} = {value!r} should start with {prefix}")
            elif value not in ids:
                errors.append(f"{path}: {where}{field} -> {value} does not exist")
        for k, v in d.items():
            if k in REFS:
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
        if kind in ("part", "release") and "gtin" in d:
            g = str(d["gtin"])
            digits = [int(c) for c in g] if g.isdigit() else []
            ok = len(digits) in (8, 12, 13, 14) and (10 - sum(x * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(digits[:-1]))) % 10) % 10 == digits[-1]
            if not ok:
                errors.append(f"{path}: gtin {g!r} is not a valid GTIN-8/12/13/14 (length or check digit)")
        if kind == "doc":
            for f in ("url", "page"):
                if f in d and not str(d[f]).startswith(("https://", "http://")):
                    errors.append(f"{path}: {f} must be a web link, got {d[f]!r}")
        for l in d.get("links", []) if kind in ("part", "release", "kit") else []:
            if not (isinstance(l, dict) and l.get("site") and str(l.get("url", "")).startswith("https://")):
                errors.append(f"{path}: link {l!r} needs a site and an https url")
            elif "kind" in l and l["kind"] != "fan-site":
                errors.append(f"{path}: link kind = {l['kind']!r} not in ['fan-site']")
        if kind == "part" and d.get("category") == "paint" and "finish" in d and d["finish"] not in PAINT_FINISH:
            errors.append(f"{path}: paint finish = {d['finish']!r} not in {sorted(PAINT_FINISH)}")
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
        ve = d.get("depicts") if kind in ("release", "part") else None
        if ve is not None:
            if kind == "part" and d.get("category") != "body":
                errors.append(f"{path}: depicts only on a release or a body shell (category body)")
            elif not (isinstance(ve, dict) and set(ve) <= {"make", "model", "year", "licensed"} and ve.get("make") in VEHICLE_MAKES
                      and isinstance(ve.get("model"), str) and ve["model"].strip() == ve["model"] and ve["model"]
                      and (("year" not in ve) or (isinstance(ve["year"], int) and not isinstance(ve["year"], bool) and 1885 <= ve["year"] <= datetime.date.today().year + 1))
                      and ve.get("licensed", True) is True):
                errors.append(f"{path}: depicts should be {{ make = <one of VEHICLE_MAKES>, model = \"...\", year = 1885.. (optional), licensed = true (optional) }}, got {ve!r}")
        rq = d.get("requires") if kind == "release" else None
        if rq is not None and not (isinstance(rq, list) and rq and all(isinstance(x, str) and x.startswith(("kit/", "release/")) for x in rq)):
            errors.append(f"{path}: requires should be a list of kit or release ids (the car the release needs, one of them)")
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
        if kind == "brand" and not isinstance(d.get("item_numbers", True), bool):
            errors.append(f"{path}: item_numbers must be true or false")
        if kind == "part" and "number" not in d:
            if not no_numbers.get(d.get("brand")):
                errors.append(f"{path}: missing required field number (only parts of a brand with item_numbers = false go without)")
        elif kind == "part" and not re.match(r"^[A-Za-z0-9][A-Za-z0-9.+\-]*$", str(d.get("number", ""))):
            errors.append(f"{path}: odd part number {d.get('number')!r}")
    counts = {}
    for _, kind, _ in docs:
        counts[kind] = counts.get(kind, 0) + 1
    counts["art"] = check_art(ids, errors)
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
