"""Validate every TOML file under data/.

Checks: file parses, the file is where tools/layout.py puts its id, required
fields per entity kind, every reference resolves, no duplicate ids. Exit code 1
on any error.

Run from the repo root: python3 -I tools/validate.py
"""
import datetime, os, re, sys, tomllib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import DIRS, path_for

ROOT = "data"
REQUIRED = {
    "brand": ["id", "name", "status"],
    "kit": ["id", "brand", "name", "category"],
    "release": ["id", "kit", "brand", "name", "kind", "status"],   # year: optional, left out when unknown
    "part": ["id", "brand", "number", "name"],
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
LIST_REFS = {"documents": "doc/", "releases": "release/"}
SURFACES = {"carpet", "astro", "clay", "dirt", "asphalt", "high-grip"}   # the track surface a race kit is built for

ENUMS = {
    "release.status": {"announced", "released", "discontinued"},
    "release.kind": {"kit", "rtr", "arr"},
    # kit types (docs/schema.md "kit"); the site gives each a label and an icon (hobbydex src/lib/kitTypes.ts)
    "kit.category": {"buggy", "truggy", "stadium-truck", "short-course", "monster", "desert-truck", "truck", "race-truck",
                     "crawler", "touring", "formula", "pan-car", "rally", "street-basher", "drift", "drag", "lowrider",
                     "speed-run", "kart", "motorcycle", "tank", "construction", "car", "boat"},
    "brand.status": {"active", "dormant", "gone"},
    "contains.role": {"kit", "option", "listed"},
    "doc.kind": {"manual", "part_list", "exploded_view", "supplement", "catalog", "product_page", "owner_report"},
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
    "wheel-hex": {"drivetrain", "wheel", "tire", "suspension"},   # hexes, wheels and tyres with a hex, hubs and axles
}

def categories():
    """Part categories are the files in data/categories (category/<slug>)."""
    d = os.path.join(ROOT, "categories")
    return {f[:-5] for f in os.listdir(d) if f.endswith(".toml")} if os.path.isdir(d) else set()

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
        if kind in ("part", "release") and "gtin" in d:
            g = str(d["gtin"])
            digits = [int(c) for c in g] if g.isdigit() else []
            ok = len(digits) in (8, 12, 13, 14) and (10 - sum(x * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(digits[:-1]))) % 10) % 10 == digits[-1]
            if not ok:
                errors.append(f"{path}: gtin {g!r} is not a valid GTIN-8/12/13/14 (length or check digit)")
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
        su = d.get("surface") if kind in ("release", "kit") else None
        if su is not None and not (isinstance(su, list) and su and all(x in SURFACES for x in su)):
            errors.append(f"{path}: surface {su!r} should be a list of {sorted(SURFACES)}")
        lc = d.get("lipo_cells") if kind == "part" else None
        if lc is not None and not (isinstance(lc, list) and len(lc) == 2 and all(isinstance(x, int) for x in lc) and 0 < lc[0] <= lc[1]):
            errors.append(f"{path}: lipo_cells {lc!r} should be [min, max] cell counts")
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
        if kind == "part" and not re.match(r"^[A-Za-z0-9][A-Za-z0-9.+\-]*$", str(d.get("number", ""))):
            errors.append(f"{path}: odd part number {d.get('number')!r}")
    counts = {}
    for _, kind, _ in docs:
        counts[kind] = counts.get(kind, 0) + 1
    print("entities:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if errors:
        print(f"{len(errors)} error(s):")
        for e in errors[:200]:
            print(" ", e)
        sys.exit(1)
    print("ok")

if __name__ == "__main__":
    main()
