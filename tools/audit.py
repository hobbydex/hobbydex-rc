"""Gap audit: what the data and the site get wrong or leave out, ranked.

Reads data/ directly (TOML) plus the caches the checks need in hobbydex-tools
(the downloaded manuals, the art photo sources, the part classifier). Each
check prints a count, five example ids with their hobbydex.com page, and the
fix. The full list of one check: --list NAME. JSON for scripts: --json FILE.

    python3 -I tools/audit.py                    # ranked summary
    python3 -I tools/audit.py --list manual-unlinked
    python3 -I tools/audit.py --json work/audit.json
    python3 -I tools/audit.py --tools ../hobbydex-tools --site ../hobbydex

Exit code 0 always: this is a to-do list. Runs in well under five minutes.
"""
import argparse, collections, csv, glob, importlib.util, json, os, re, sys, tomllib

SITE = "https://hobbydex.com"
HERE = os.path.dirname(os.path.abspath(__file__))
RC = os.path.dirname(HERE)
YEAR = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")
HW = {"bearing", "screw", "nut", "washer-shim", "clip", "pin", "ball-end", "o-ring-seal"}   # hardware part categories
MAT_CATS = {"pinion", "spur-gear", "screw", "nut", "washer-shim", "pin", "bearing"}          # metal hardware: material from the name or the maker's page
SPEC_CATS = {"screw", "nut", "washer", "pin", "eclip", "bearing"}                          # spec categories with a bag drawing
SIZE = re.compile(r"\bM\d+(?:\.\d+)?\b|\b\d+(?:\.\d+)?\s*x\s*\d+(?:\.\d+)?(?:\s*x\s*\d+(?:\.\d+)?)?\s*(?:mm)?\b|\b\d+(?:\.\d+)?\s*mm\b", re.I)
CALLOUT_PAREN = re.compile(r"\(\s*[A-Z][A-Z0-9-]*\s+x\s*\d+\s*\)")   # (CODE xN): a space before the x, so not a size (BM3x15)
CALLOUT_JOINED = re.compile(r"\b[A-Z]{2,3}x\d{1,2}\b")                      # CODExN: letters then x and a count (RSx3, BSx2)
PCS = re.compile(r"\b\d+\s*pcs?\b", re.I)
PLUG = re.compile(r"\b(plug|connector|bullet|xt\d*|deans|jr|t-plug|banana|jst|xh|ec\d)\b", re.I)
CONFUSABLE = [frozenset(p) for p in (("5", "6"), ("3", "8"), ("0", "8"), ("1", "7"))]
BANNED_HOSTS = re.compile(r"https?://[^\s\"')]*(houseofrc|tamico)[^\s\"')]*", re.I)
# a tamico.de dealer link (kind = "dealer") is allowed for Tamiya spares without a maker page (tools/link_tamico_spares.py)
TAMICO_DEALER_LINK = re.compile(r'\{ site = "tamico\.de", url = "[^"]*", kind = "dealer" \}')
SCRAP_IMG = re.compile(r"https?://[^\s\"')]*rcscrapyard[^\s\"')]*\.(jpe?g|png|gif|webp)", re.I)
LOCAL_PATH = re.compile(r"(^|[\s\"'(=])(/home/|/Users/|/tmp/|file://|[A-Za-z]:\\|work/manuals/|cache/)")
FIX_PAGE = "add the maker's product page as a document (kind product_page, page = the maker's URL) and list it in the release's documents"


def load(root):
    db = collections.defaultdict(list)
    for folder in ("brands", "kits", "releases", "parts", "documents", "specs", "categories", "companies", "makes", "standards"):
        for dp, _, fs in os.walk(os.path.join(root, "data", folder)):
            for fn in sorted(fs):
                if fn.endswith(".toml"):
                    path = os.path.join(dp, fn)
                    with open(path, "rb") as f:
                        d = tomllib.load(f)
                    d["_path"] = os.path.relpath(path, root)
                    db[folder].append(d)
    return db


def url_for(item):
    i = item["id"]
    kind, _, rest = i.partition("/")
    if kind == "release":
        return f"{SITE}/rc/releases/{rest}/"
    if kind == "kit":
        return f"{SITE}/rc/platforms/{rest}/"
    if kind == "part":
        return f"{SITE}/rc/parts/{rest}/"
    if kind == "doc":
        b = item.get("brand", "").split("/")[-1]
        return f"{SITE}/rc/brands/{b}/" if b else SITE + "/rc/"
    if kind == "brand":
        return f"{SITE}/rc/brands/{rest}/"
    return SITE + "/rc/"


def walk_strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from walk_strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from walk_strings(x)


_CLS = None


def _classify_one(name):
    return _CLS(name)


_TARGET = _KEEP = None   # classify_parts.target and its KEEP marker, set by load_tools


def _category_of(p):
    """What tools/classify_parts.py writes for part p: a category, "" for none, or "keep" (its category stays)."""
    c = _TARGET(p)
    return "keep" if c is _KEEP else (c or "")


def classify_all(cls, names):
    """cls over the names in forked workers: the classifier is regex-heavy and one process takes about a minute."""
    global _CLS
    _CLS = cls   # set before the fork, so the workers inherit it
    try:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(min(8, os.cpu_count() or 1)) as pool:
            return pool.map(_classify_one, names, chunksize=4000)
    except (ValueError, OSError):   # no fork here: one process
        return [cls(n) for n in names]


def near_local(a, b):
    """b is a's number with one or two digits off, each off digit a confusable pair (same length)."""
    if len(a) != len(b) or a == b:
        return False
    diff = [frozenset((x, y)) for x, y in zip(a, b) if x != y]
    return len(diff) <= 2 and all(p in CONFUSABLE for p in diff)


def load_tools(tools):
    """The classifier and the art sources, from hobbydex-tools (None when absent)."""
    out = {"classify": None, "sources": None, "cache": None, "near": None, "tamico": None, "colour": None, "packqty": None, "with_fasteners": None, "fastener_cats": None, "material": None}
    lpm = os.path.join(tools, "tools", "link_part_material.py")
    if os.path.exists(lpm):   # its decide() is the rule the material linker writes by: a flag is a value it would set
        spec = importlib.util.spec_from_file_location("link_part_material", lpm)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.dirname(lpm))
        try:
            spec.loader.exec_module(mod)
            out["material"] = mod
        except Exception as e:  # the check is skipped without it
            print(f"note: link_part_material not loaded ({e})", file=sys.stderr)
        finally:
            sys.path.remove(os.path.dirname(lpm))
    pq = os.path.join(tools, "tools", "packqty.py")
    if os.path.exists(pq):   # the count reader the importers use (a name's "(2)", "2pcs", "1 pair")
        spec = importlib.util.spec_from_file_location("packqty", pq)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out["packqty"] = mod
    lpc = os.path.join(tools, "tools", "link_part_colours.py")
    if os.path.exists(lpc):   # the colour a part's name states (tools/link_part_colours.py colour())
        spec = importlib.util.spec_from_file_location("link_part_colours", lpc)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.join(tools, "tools"))
        try:
            spec.loader.exec_module(mod)
            out["colour"] = mod.colour
        except Exception as e:
            print(f"note: colour linker not loaded ({e})", file=sys.stderr)
        finally:
            sys.path.remove(os.path.join(tools, "tools"))
    cls = os.path.join(tools, "tools", "classify_parts.py")
    if os.path.exists(cls):
        spec = importlib.util.spec_from_file_location("classify_parts", cls)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, HERE)   # classify_parts imports layout.py from the data repo
        try:
            spec.loader.exec_module(mod)
            out["classify"] = mod.classify
            out["with_fasteners"] = mod.with_fasteners
            out["fastener_cats"] = mod.FASTENER_CATS
            global _TARGET, _KEEP
            _TARGET, _KEEP = mod.target, mod.KEEP
        except Exception as e:  # the audit still runs without it
            print(f"note: classifier not loaded ({e})", file=sys.stderr)
        finally:
            sys.path.remove(HERE)
    ocr = os.path.join(tools, "tools", "ocr_numbers.py")
    if os.path.exists(ocr):
        spec = importlib.util.spec_from_file_location("ocr_numbers", ocr)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.dirname(ocr))   # ocr_numbers imports paths.py from the tools
        try:
            spec.loader.exec_module(mod)
            out["near"] = mod.near
        except Exception as e:  # the local rule (near_local) is used instead
            print(f"note: ocr_numbers not loaded ({e})", file=sys.stderr)
        finally:
            sys.path.remove(os.path.dirname(ocr))
    tamico = os.path.join(tools, "cache", "notes", "tamiya", "tamico-names.tsv")
    if os.path.exists(tamico):
        out["tamico"] = tamico
    srcdir = os.path.join(tools, "tools", "art", "sources")
    if os.path.isdir(srcdir):
        items = []
        for fn in sorted(os.listdir(srcdir)):
            if fn.endswith(".toml"):
                with open(os.path.join(srcdir, fn), "rb") as f:
                    items += tomllib.load(f).get("item", [])
        out["sources"] = items
    cache = os.path.join(tools, "cache")
    if os.path.isdir(os.path.join(cache, "manuals")):
        out["cache"] = cache
    # the hardware photo reader (its cache lookups; it reads no photo itself in the audit)
    hw = os.path.join(tools, "tools", "link_hw_photo_finish.py")
    out["hwphoto"] = None
    if os.path.exists(hw):
        spec = importlib.util.spec_from_file_location("link_hw_photo_finish", hw)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.dirname(hw))
        try:
            spec.loader.exec_module(mod)
            out["hwphoto"] = mod
        except Exception as e:  # the audit still runs without it
            print(f"note: link_hw_photo_finish not loaded ({e})", file=sys.stderr)
        finally:
            sys.path.remove(os.path.dirname(hw))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tools", default=os.path.join(RC, "..", "hobbydex-tools"))
    ap.add_argument("--site", default=os.path.join(RC, "..", "hobbydex"), help="the site checkout (its hardware drawings)")
    ap.add_argument("--list", metavar="CHECK", help="every id one check flags")
    ap.add_argument("--json", metavar="FILE", help="write the full result as JSON")
    ap.add_argument("--examples", type=int, default=5)
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="backslashreplace")
    os.chdir(RC)
    db = load(RC)
    tools = load_tools(os.path.abspath(args.tools))
    by_id = {}
    for k in db:
        for d in db[k]:
            if "id" in d:
                by_id[d["id"]] = d
    kits = {d["id"]: d for d in db["kits"]}
    rels = db["releases"]
    parts = db["parts"]
    docs = {d["id"]: d for d in db["documents"]}
    brands = {d["id"]: d for d in db["brands"]}
    rels_of_kit = collections.defaultdict(list)
    for r in rels:
        rels_of_kit[r.get("kit")].append(r)
    doc_rels = collections.defaultdict(set)   # doc id -> release ids that list it
    for r in rels:
        for dd in r.get("documents", []):
            doc_rels[dd].add(r["id"])
    horizon = {b["id"] for b in brands.values() if b.get("owner") == "company/horizon-hobby"}
    results = {}

    def check(name, fix, items, count=None, **extra):
        """items: a list of records (or ids) flagged; count defaults to len(items)."""
        ids = [x if isinstance(x, str) else x["id"] for x in items]
        recs = [{"id": i, "url": url_for(by_id.get(i, {"id": i}))} for i in sorted(set(ids))]
        results[name] = {"fix": fix, "count": len(set(ids)) if count is None else count, "examples": recs[:args.examples], "all": sorted(set(ids)), **extra}

    # 1. platforms named after a year that is later than one of their releases
    def oldest(k):
        ys = [r.get("year") or int((r.get("released") or "0")[:4] or 0) for r in rels_of_kit[k["id"]]]
        return min((y for y in ys if y), default=None)
    hits = []
    for k in kits.values():
        old = oldest(k)
        if old and any(int(y) > old for n in [k["name"], k["id"]] + k.get("former_ids", []) for y in YEAR.findall(n)):
            hits.append(k)
    check("platform-year-name", "rename the platform after its oldest release (the year lives on the release); keep the old id in former_ids", hits)

    # 1b. former names the rule rejects (validate.former_names_problems): must stay 0
    sys.path.insert(0, HERE)
    import validate
    check("former-name-restates", "drop the entry: it is the part's name again with a pack count or set number, or listed twice (former_names.store() in hobbydex-tools)",
          [p for p in parts if validate.former_names_problems(p)],
          count=sum(len(validate.former_names_problems(p)) for p in parts))

    # 2. release date marker "?" (a *_doubt reason shows as "?" in the date column)
    check("date-marker-question", "the ? sits in the date column of a narrow table: shorten the reason or move it to the release notes, and confirm the date",
          [r for r in rels if any(k in r for k in ("year_doubt", "released_doubt", "announced_doubt"))])

    # 3. bearing category holding a rebuild or service kit
    check("bearing-rebuild-kit", "recategorise the part (not bearing) or remove it from the bearing list; a rebuild kit is a set of parts",
          [p for p in parts if p.get("category") == "bearing" and re.search(r"\b(rebuild|service|overhaul|repair)\b", p["name"], re.I)])

    # 4. Traxxas service or rebuild packs marked as in the box
    check("service-pack-in-box", "change the row's role to option (or listed): a service or upgrade pack is not in the box",
          [r for r in rels if r.get("brand") == "brand/traxxas" for c in r.get("contains", []) if c.get("role") == "kit"
           and re.search(r"\b(service|rebuild|upgrade)\b.*\b(pack|kit|set)\b", (by_id.get(c["part"], {}).get("name", "")), re.I)])

    # 5. release whose contents come only from a body-set manual while a kit manual exists
    def is_body(doc_id):
        d = docs.get(doc_id, {})
        return bool(re.search(r"body", d.get("title", "") + " " + doc_id, re.I))
    hits = []
    for r in rels:
        srcs = {c.get("source") for c in r.get("contains", []) if c.get("source")}
        if not srcs or not all(is_body(s) for s in srcs):
            continue
        kit_manuals = [d for rr in rels_of_kit[r.get("kit")] for d in rr.get("documents", [])
                       if docs.get(d, {}).get("kind") == "manual" and not is_body(d)]
        if kit_manuals:
            hits.append(r)
    check("body-manual-only", "source the release's contents from the kit manual (or list the body manual's parts as listed only)", hits)

    # 6. downloaded manuals (hobbydex-tools cache/manuals) not linked to a release
    if tools["cache"]:
        # cache/manuals/** and cache/notes/<brand>/pdf/**; paths are relative to cache/
        pdf_dirs = [os.path.join(tools["cache"], "manuals")]
        notes = os.path.join(tools["cache"], "notes")
        if os.path.isdir(notes):
            pdf_dirs += [os.path.join(notes, b, "pdf") for b in sorted(os.listdir(notes)) if os.path.isdir(os.path.join(notes, b, "pdf"))]
        cached = []
        for top in pdf_dirs:
            for dp, _, fs in os.walk(top):
                for fn in fs:
                    if fn.lower().endswith(".pdf"):
                        cached.append(os.path.relpath(os.path.join(dp, fn), tools["cache"]))
        # a doc is linked when a release or a part lists it
        on_part = {dd for p in parts for dd in p.get("documents", [])}
        linked_docs = set(doc_rels) | on_part
        # the crawl queue maps each cached file to the URL it came from
        url_of = {}
        crawl = os.path.join(tools["cache"], "crawl.db")
        if os.path.exists(crawl):
            import sqlite3
            con = sqlite3.connect("file:%s?mode=ro" % crawl, uri=True)
            for path, url in con.execute("select path, url from queue where kind='pdf'"):
                url_of.setdefault(os.path.relpath(path, tools["cache"]) if path.startswith(tools["cache"]) else path, url)
            con.close()
        by_name = collections.defaultdict(list)
        by_url = collections.defaultdict(list)
        for d in docs.values():
            if d.get("file"):
                by_name[os.path.basename(d["file"])].append(d)
            if d.get("url"):
                by_url[d["url"]].append(d)
        unlinked = []
        for rel_path in cached:
            name = os.path.basename(rel_path)
            ds = by_name.get(name, []) + by_url.get(url_of.get(rel_path), [])
            if not any(d["id"] in linked_docs for d in ds):
                unlinked.append(rel_path)
        check("manual-unlinked", "add the cached manual as a document (file, page, url) and list it in its release's documents; a document listed by a part or matched by its URL counts as linked",
              [{"id": u} for u in unlinked], count=len(unlinked), _unlinked_ids=unlinked[:5])
        # keep the list ids as paths; url points at the brand
        res = results["manual-unlinked"]
        res["examples"] = [{"id": u, "url": SITE + "/rc/brands/" + u.split("/")[1] + "/"} for u in unlinked[:args.examples]]
    else:
        results["manual-unlinked"] = {"fix": "hobbydex-tools cache not found (--tools)", "count": None, "examples": [], "all": []}

    # 7. Horizon documents without a page
    check("horizon-doc-no-page", "give the document its page (the Horizon product or support page that lists the file)",
          [d for d in docs.values() if d.get("brand") in horizon and not d.get("page")])

    # 8. platforms with no releases
    check("platform-no-release", "add the platform's releases, or retire the platform if it is not a product",
          [k for k in kits.values() if not rels_of_kit[k["id"]]])

    # 9. releases and kits with no outline art although a photo is in the art sources
    art_dir = os.path.join(RC, "art")
    def has_art(i):
        kind, _, rest = i.partition("/")
        sub = {"kit": "kits", "release": "releases"}.get(kind)
        return bool(sub) and os.path.exists(os.path.join(art_dir, sub, rest + ".svg"))
    missing_art = []
    if tools["sources"] is not None:
        for it in tools["sources"]:
            if not it.get("photo"):
                continue
            for t in it.get("targets", []) + [it.get("id", "")]:
                if t.partition("/")[0] in ("kit", "release") and t in by_id and not has_art(t):
                    missing_art.append((t, it.get("skip", "")))
        seen = {}
        for t, skip in missing_art:
            seen.setdefault(t, skip)
        fixable = [t for t, s in seen.items() if re.search(r"needed to complete|another gallery|gallery shot", s, re.I)]
        check("art-missing-photo", "trace another gallery shot of the item (a Needed to complete graphic is not the car); the skip reason says which shot was rejected",
              [{"id": t} for t in seen], count=len(seen), _gallery_fixable=len(fixable))
        results["art-missing-photo"]["examples"] = [{"id": t, "url": url_for({"id": t})} for t in list(seen)[:args.examples]]
        results["art-missing-photo"]["skip_reasons"] = collections.Counter(s or "(none)" for s in seen.values()).most_common(8)
    else:
        results["art-missing-photo"] = {"fix": "hobbydex-tools art sources not found (--tools)", "count": None, "examples": [], "all": []}

    # 10. copyright-year release years
    check("copyright-year", "a copyright line is an on-sale bound, not a release year: move the year to seen_by (year precision) and drop year",
          [r for r in rels if r.get("year") and not r.get("released") and re.search(r"copyright|\(c\)|©", r.get("notes", ""), re.I)])

    # 11. classifier drift: stored category vs classify(name)
    if tools["classify"]:
        moves = collections.Counter()
        drift = collections.defaultdict(list)
        cands = [p for p in parts if not (p.get("category_source") == "curated" or p["name"] == (p.get("number") or ""))]
        for p, new in zip(cands, classify_all(_category_of, cands)):   # the classifier's own target(), as the run writes it
            if new == "keep":
                continue
            new = new or None
            old = p.get("category")
            if new != old:
                key = f"{old or '(none)'} -> {new or '(none)'}"
                moves[key] += 1
                drift[key].append(p)
        flat = [p for v in drift.values() for p in v]
        check("classifier-drift", "rerun tools/classify_parts.py in hobbydex-tools (the rules changed or the stored category is stale)", flat,
              transitions=moves.most_common(10))
    else:
        results["classifier-drift"] = {"fix": "classify_parts.py not found (--tools)", "count": None, "examples": [], "all": []}

    # 11b. a part that comes with screws, nuts or washers is the part: its category comes from the name before the fasteners
    if tools["with_fasteners"]:
        def part_before_fasteners(p):
            thing = tools["with_fasteners"](p["name"])
            return bool(thing) and p.get("category") in tools["fastener_cats"] and tools["classify"](thing) not in (None, "", *tools["fastener_cats"])
        check("with-fasteners-category", "a part that comes with screws, nuts or washers takes the category of the part (rerun tools/classify_parts.py in hobbydex-tools; a curated category is set by hand: the part, not screw)",
              [p for p in parts if part_before_fasteners(p)])
    else:
        results["with-fasteners-category"] = {"fix": "classify_parts.py not found (--tools)", "count": None, "examples": [], "all": []}
    # 11b. parts with no category: a name the classifier knows gets one (classify_parts.py --fill); a bare code stays uncategorised
    check("part-no-category", "run tools/classify_parts.py --fill in hobbydex-tools, or add the name's words to its rules",
          [p for p in parts if not p.get("category") and p.get("category_source") != "curated" and p["name"] != (p.get("number") or "")])

    # 11c. a colour word in the name that the part has no color for (tools/link_part_colours.py)
    if tools["colour"]:
        colour = tools["colour"]
        check("colour-word-no-color", "run tools/link_part_colours.py in hobbydex-tools (or the word is a product name: add it to its PRODUCT list)",
              [p for p in parts if not p.get("color") and p.get("category") != "paint" and not str(p.get("range", "")).endswith("-colours") and colour(p["name"])])
    else:
        results["colour-word-no-color"] = {"fix": "hobbydex-tools link_part_colours.py not found (--tools)", "count": None, "examples": [], "all": []}

    # 12. releases named only by their number
    check("release-named-by-number", "give the release its product name from the maker's page",
          [r for r in rels if re.fullmatch(r"[\w-]*\d[\w-]*", r.get("name", "")) and r.get("name") == r.get("number", r.get("name"))])

    # 13. platforms with no manual or product page linked
    def page_docs(r):
        return [docs[d] for d in r.get("documents", []) if d in docs and docs[d].get("kind") in ("manual", "product_page")]
    check("platform-no-manual-or-page", "link the platform's manual or the maker's product page on one of its releases",
          [k for k in kits.values() if rels_of_kit[k["id"]] and not any(page_docs(r) for r in rels_of_kit[k["id"]])])

    # 14. video documents without a date
    check("video-no-date", "add the date the maker's video was published, from the channel page",
          [d for d in docs.values() if d.get("kind") == "video" and not d.get("date")])

    # 15. release with no date at all
    check("release-no-date", "date the release from a source (released, year or announced); a seen_by bound is only a fallback",
          [r for r in rels if not any(r.get(k) for k in ("released", "year", "announced", "seen_by"))])

    # 16. release whose category is the same as its kit's (redundant override)
    check("release-category-redundant", "remove the release's category: it equals the kit's",
          [r for r in rels if r.get("category") and r.get("category") == kits.get(r.get("kit"), {}).get("category")])

    # 17. kit whose releases disagree on scale: no kit scale, or a release scale override with no note saying why
    hits = []
    for k in kits.values():
        rs = rels_of_kit[k["id"]]
        eff = {r.get("scale") or k.get("scale") for r in rs} - {None}
        unsourced = [r for r in rs if r.get("scale") and r.get("scale") != k.get("scale") and not r.get("notes")]
        if len(eff) > 1 and (not k.get("scale") or unsourced):
            hits.append(k)
    check("kit-mixed-scale", "set the kit's scale to the one the releases share, and give a release scale that differs from the kit a note that states its source", hits)

    # 18. document without page or url
    check("doc-no-page-or-url", "give the document a page (the maker's page that lists it) or a url",
          [d for d in docs.values() if not d.get("page") and not d.get("url")])

    # 19. release lists a document that does not list the release back
    # both sides: a release lists a document that does not list it, or a document lists a release that does not list it
    rel_by_id = {r["id"]: r for r in rels}
    one_sided = [r["id"] for r in rels for d in r.get("documents", []) if d in docs and r["id"] not in (docs[d].get("releases") or [])]
    one_sided += [rid for d in docs.values() for rid in (d.get("releases") or []) if rid in rel_by_id and d["id"] not in (rel_by_id[rid].get("documents") or [])]
    check("doc-not-back-linked", "run tools/sync_doc_links.py --write in hobbydex-tools (adds the missing side; catalogues, shared shop pages and dealer listings it holds are listed there)",
          one_sided)

    # 19b. a release lists one document more than once (a repeated append by an importer)
    check("duplicate-doc-ref", "remove the repeated entry from the release's documents; the importer that appends it should test membership first",
          [r for r in rels if len(set(r.get("documents", []))) != len(r.get("documents", []))])

    # 19b. a release lists one document more than once (a repeated append by an importer)
    check("duplicate-doc-ref", "remove the repeated entry from the release's documents; the importer that appends it should test membership first",
          [r for r in rels if len(set(r.get("documents", []))) != len(r.get("documents", []))])

    # 20. part fits a kit that has no releases
    check("fits-kit-no-release", "add the kit's release, or remove the fit row",
          [p for p in parts for f in p.get("fits", []) if f.get("kit") in kits and not rels_of_kit.get(f["kit"])])

    # 21. orphan art files
    orphans = []
    for sub, kind in (("kits", "kit"), ("releases", "release"), ("parts", "part")):
        base = os.path.join(art_dir, sub)
        for dp, _, fs in os.walk(base):
            for fn in fs:
                if fn.endswith(".svg"):
                    rel = os.path.relpath(os.path.join(dp, fn), base)[:-4]
                    eid = f"{kind}/{rel}" if kind != "part" else None
                    if kind == "part":
                        brand, _, rest = rel.partition("/")
                        eid = f"part/{brand}/{rest.split('/')[-1]}"
                    if eid not in by_id:
                        orphans.append(os.path.relpath(os.path.join(dp, fn), RC))
    check("orphan-art", "rename the art file to its record's id or delete it (validate.py reports them)",
          [{"id": o} for o in orphans], count=len(orphans))
    results["orphan-art"]["examples"] = [{"id": o, "url": SITE + "/rc/"} for o in orphans[:args.examples]]

    # 22. duplicate release names within one kit
    hits = []
    for k in kits.values():
        names = collections.Counter(r["name"].strip().lower() for r in rels_of_kit[k["id"]])
        if any(n > 1 for n in names.values()):
            hits.append(k)
    check("duplicate-name-in-kit", "give each release of the kit its own name (edition, colour or item number)", hits)

    # 23. release depicting a real vehicle without its make
    check("depicts-no-model", "set depicts.model: a real vehicle needs its model (make is optional)",
          [r for r in rels if r.get("depicts") and not r["depicts"].get("model")])

    # 24. never-link hosts and dealer doc references
    banned, scrap, local, dealer = [], [], [], []
    for path in sorted({d["_path"] for k in db for d in db[k]}):
        with open(os.path.join(RC, path), encoding="utf-8") as f:
            text = f.read()
        if BANNED_HOSTS.search(TAMICO_DEALER_LINK.sub("", text)):
            banned.append(path)
        if SCRAP_IMG.search(text):
            scrap.append(path)
        if "doc/tamiya/tamico-dealer-parts" in text:
            dealer.append(path)
    for k in db:
        for d in db[k]:
            for s in walk_strings(d):
                if LOCAL_PATH.search(s):
                    local.append(d["id"]); break
    to_id = lambda p: os.path.splitext(os.path.basename(p))[0]
    check("banned-host", "remove the link to the host (House of RC, Tamico, rcscrapyard image URLs are never linked)", [{"id": p} for p in banned + scrap], count=len(banned) + len(scrap))
    results["banned-host"]["examples"] = [{"id": p, "url": SITE + "/rc/"} for p in (banned + scrap)[:args.examples]]
    check("tamico-doc-reference", "cite the maker's own listing instead of the Tamico dealer catalogue", [{"id": p} for p in dealer], count=len(dealer))
    results["tamico-doc-reference"]["examples"] = [{"id": p, "url": SITE + "/rc/"} for p in dealer[:args.examples]]
    check("local-path", "replace the local path with the source's URL", local)

    # 25. releases with no maker product page (no product_page document, no maker link), per brand
    no_page = [r for r in rels if not any(docs.get(d, {}).get("kind") == "product_page" for d in r.get("documents", []))
               and not any(l.get("kind") != "fan-site" for l in r.get("links", []))]
    per_brand = collections.Counter(r["brand"].split("/")[-1] for r in no_page)
    check("release-no-product-page", FIX_PAGE, no_page, per_brand=per_brand.most_common())

    # 25b. releases typed "car": the catch-all, no category on the release or its kit (resolved release, else kit, else car)
    typed_car = [r for r in rels if (r.get("category") or kits.get(r.get("kit"), {}).get("category") or "car") == "car"]
    per_brand = collections.Counter(r["brand"].split("/")[-1] for r in typed_car)
    check("release-typed-other-cars", "give the kit its type from the maker's product page or manual (kit level first; a release-level category only where the release differs from its kit), with a sources entry for the page; a kit with no source stays car and is counted",
          typed_car, per_brand=per_brand.most_common())

    # 26. unnamed parts and cheap structural gaps (kept from the old audit)
    check("part-named-by-number", "give the part its name from the maker's parts list", [p for p in parts if p["name"] == p.get("number")])
    check("release-no-contents", "read the release's parts list into contains (or note there is none)", [r for r in rels if not r.get("contains")])
    used_specs = {e["spec"] for p in parts for e in p.get("equivalent_to", [])}
    check("spec-unlinked", "link a part to the spec, or retire the spec", [s for s in db["specs"] if s["id"] not in used_specs])

    # 26c. Tamiya parts with no maker link and no dealer link, by number form (tools/link_tamico_spares.py adds dealer links)
    def linked_somewhere(p):
        return any((l.get("kind") is None and l.get("site") == "Tamiya") or l.get("kind") == "dealer" for l in p.get("links", []))
    tam = [p for p in parts if p.get("brand") == "brand/tamiya"]
    bare = [p for p in tam if not linked_somewhere(p)]
    spares = [p for p in bare if re.fullmatch(r"\d{8}", str(p.get("number", "")))]
    items = [p for p in bare if re.fullmatch(r"\d{5}", str(p.get("number", "")))]
    check("tamiya-spare-no-link", "a Tamiya 8-digit spare with no maker or dealer page: run tools/plan_tamico_spares.py in hobbydex-tools (dealer pages are queued) and then tools/link_tamico_spares.py",
          spares, count=len(spares))
    check("tamiya-item-no-link", "a Tamiya item number with no maker product page: give it a maker link (tamiya.com page) or a manual or fan-site source",
          items, count=len(items))
    tsv = os.path.join(args.tools, "cache", "notes", "tamiya", "tamico-spares.tsv")
    conflicts = []
    if os.path.exists(tsv):
        with open(tsv, encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                if row["status"].startswith("conflict"):
                    conflicts.append({"id": row["part"]})
    check("tamico-pack-conflict", "no pack_qty from the dealers: the dealers' counts differ or the part's name states another count; set the count from the part's own source or leave it unset (tools/link_tamico_spares.py lists the rows)",
          conflicts, count=len(conflicts))

    # 26b. a count the name states that the part has no pack_qty for (a name that keeps the maker's count is fine)
    if tools["packqty"]:
        gap = [p for p in parts if "pack_qty" not in p and tools["packqty"].from_name(p.get("name", ""))]
        check("name-count-no-pack-qty", "set pack_qty from the count the name states: rerun the importer that wrote the part (it sets pack_qty from its name) or tools/link_pack_qty.py in hobbydex-tools",
              gap, per_brand=collections.Counter(p["brand"].split("/")[-1] for p in gap).most_common(12))

    # 27. video docs whose release has a product page with gallery videos not attached: skipped (needs fetched pages)
    results["video-gallery-unattached"] = {"fix": "not checked: needs the cached product pages parsed for gallery video IDs", "count": None, "examples": [], "all": [], "skipped": True}

    # 28. a release whose box (kit rows) holds two gears of one kind at different pitches: two pinions or two spurs
    part_of = {p["id"]: p for p in parts}
    clash = []
    for r in rels:
        pitches = collections.defaultdict(set)
        for c in r.get("contains", []):
            p = part_of.get(c["part"], {})
            if c.get("role") == "kit" and p.get("category") in ("pinion", "spur") and p.get("pitch_dp"):
                pitches[p["category"]].add(p["pitch_dp"])
        if any(len(v) > 1 for v in pitches.values()):
            clash.append(r)
    check("release-two-gear-pitches", "mark the other pitch as option or listed: the release's own parts list or exploded view says which one is in the box", clash)

    # 29-38. hardware bags, names, release boxes and the /tmp inodes
    brand_of = lambda x: x.get("brand", "").split("/")[-1]
    per_brand = lambda items: collections.Counter(brand_of(x) for x in items).most_common()

    def has_spec(p):
        return any(e.get("spec") for e in p.get("equivalent_to", [])) or any(i.get("spec") for i in p.get("includes", []))

    no_pack = [p for p in parts if p.get("category") in HW and "pack_qty" not in p and not p.get("includes")]
    check("hw-no-pack-count", "set pack_qty from the maker's listing (the count in the bag), or list the bag's specs in includes",
          no_pack, per_brand=per_brand(no_pack))

    # metal hardware whose name or cached maker page states a material the data lacks (tools/link_part_material.py's rule)
    lpm = tools.get("material")
    if lpm:
        idxs, stated = {}, []
        for p in parts:
            if p.get("category") in MAT_CATS and p.get("material") in (None, "unknown"):
                upd, _, _ = lpm.decide(p, brands.get(p.get("brand"), {}), idxs)
                if upd.get("material"):
                    stated.append(p)
        check("hw-no-material", "run tools/link_part_material.py in hobbydex-tools (it sets the material the name or the maker's page states, and reports the conflicts)",
              stated, per_brand=per_brand(stated))

    # 29b. hardware (any brand) whose cached product photo is not read yet for its colour or its piece count
    if tools["hwphoto"]:
        hw = tools["hwphoto"]
        unread = [p for p in parts if hw.unread_photo(p)]
        check("hw-photo-unread", "run link_hw_photo_finish.py read in hobbydex-tools (after calibrate passed), or set the colour or pack_qty by hand from the photo",
              unread, per_brand=per_brand(unread))

    # a hardware kit's pack_qty is the sum of its includes qty (hobbydex-tools packqty.from_includes)
    def kit_sum(p):
        """The sum of the includes qty of a hardware kit, or None when a row has no integer qty."""
        rows = p.get("includes") or []
        qtys = [r.get("qty") for r in rows]
        return sum(qtys) if rows and all(type(q) is int and q > 0 for q in qtys) else None
    kits_hw = [p for p in parts if p.get("category") in HW and p.get("includes")]
    no_qty = [p for p in kits_hw if kit_sum(p) is None]
    check("kit-includes-no-qty", "give every includes row of the kit its qty (the pieces in the bag); the kit's pack_qty is the sum once all rows have one",
          no_qty, per_brand=per_brand(no_qty))
    def sets_of(p):
        """True when the kit is pack_qty sets of the same contents: every includes qty divides by pack_qty
        (ARA-2804: 12 + 4 + 4 washers, screws and spacers in 4 sets of 5)."""
        return all(r["qty"] % p["pack_qty"] == 0 for r in p["includes"])
    off = [p for p in kits_hw if "pack_qty" in p and kit_sum(p) is not None and p["pack_qty"] != kit_sum(p) and not sets_of(p)]
    check("kit-pack-not-sum", "the kit's pack_qty differs from the sum of its includes qty and the rows are not whole sets of it: correct the rows to the bag's count, or the pack_qty to the maker's listing",
          off, per_brand=per_brand(off))
    results["kit-pack-not-sum"]["examples"] = [{"id": f"{p['id']} (pack_qty {p['pack_qty']}, includes sum {kit_sum(p)})", "url": url_for(p)} for p in off[:args.examples]]

    # pack count evidence (docs/schema.md "part", pack_qty_basis): a count with no recorded basis, a photo count that
    # disagrees with the text, a brand whose photo counts are written although its photos do not match known packs well
    no_basis = [p for p in parts if "pack_qty" in p and "pack_qty_basis" not in p]
    check("pack-qty-no-basis", "record pack_qty_basis (python3 -I tools/backfill_pack_basis.py in hobbydex-tools) or leave it: the count's source is not known",
          no_basis, per_brand=per_brand(no_basis))
    ev_dir = os.path.join(os.path.abspath(args.tools), "cache", "notes", "pack-evidence")
    dis = os.path.join(ev_dir, "photo-disagreements.tsv")
    ids = set()
    if os.path.exists(dis):
        with open(dis, encoding="utf-8") as f:
            next(f, None)
            ids = {ln.split("\t")[0] for ln in f if ln.strip()}
    by_id_all = {p["id"]: p for p in parts}
    check("pack-photo-disagrees", "look at the photo and the maker's text; the text count stands (tools/photo_chain.py lists them in cache/notes/pack-evidence/photo-disagreements.tsv)",
          [by_id_all[i] for i in sorted(ids) if i in by_id_all])
    wrong = os.path.join(os.path.abspath(args.tools), "cache", "notes", "review", "wrong-photos.tsv")
    wp = set()
    if os.path.exists(wrong):
        with open(wrong, encoding="utf-8") as f:
            wp = {ln.split("\t")[0] for ln in f if ln.strip()}
    check("pack-wrong-photo", "the owner marked the mapped photo as not the part's: fix the photo mapping (tools/link_hw_photo_finish.py gallery_for/photo_for) for the part",
          [by_id_all[i] for i in sorted(wp) if i in by_id_all])
    rel = os.path.join(os.path.abspath(args.tools), "tools", "data", "photo_pack_reliability.tsv")
    ok_brands, known = set(), False
    if os.path.exists(rel):
        known = True
        with open(rel, encoding="utf-8") as f:
            hdr = next(f).rstrip("\n").split("\t")
            for ln in f:
                r = dict(zip(hdr, ln.rstrip("\n").split("\t")))
                if r.get("passes") == "yes":
                    ok_brands.add(r["brand"])
    photo_parts = [p for p in parts if p.get("pack_qty_basis") in ("photo", "photos") and (not known or brand_of(p) not in ok_brands)]
    check("pack-photo-brand-below-bar", "remove the photo counts of the brand or raise its photo agreement to 97% on 30 cases (tools/photo_pack_reliability.py)",
          photo_parts, per_brand=per_brand(photo_parts))

    idx_path = os.path.join(args.site, "src", "assets", "hardware", "index.json")
    if os.path.exists(idx_path):
        with open(idx_path, encoding="utf-8") as f:
            drawn = set(json.load(f))
        spec_links = collections.defaultdict(set)   # spec id -> parts that link to it
        for p in parts:
            for e in p.get("equivalent_to", []):
                if e.get("spec"):
                    spec_links[e["spec"]].add(p["id"])
            for i in p.get("includes", []):
                if i.get("spec"):
                    spec_links[i["spec"]].add(p["id"])
        undrawn = []
        for s in db["specs"]:
            if s.get("category") not in SPEC_CATS:
                continue
            key = s["id"].removeprefix("spec/").replace("#", "-")   # hardwareBag.ts: the index key
            if key not in drawn and key + "-flat" not in drawn:
                undrawn.append(s)
        undrawn.sort(key=lambda s: -len(spec_links[s["id"]]))
        cats = collections.defaultdict(lambda: [0, 0])
        for s in undrawn:
            cats[s["category"]][0] += 1
            cats[s["category"]][1] += len(spec_links[s["id"]])
        check("spec-no-bag-drawing", "draw the spec's bag drawing (tools/hardware/make_more_drawings.py in hobbydex-tools) so the parts linked to it can show a bag",
              undrawn, breakdown=("category", [f"{c} {n} specs, {k} parts" for c, (n, k) in sorted(cats.items(), key=lambda kv: -kv[1][1])]))
        results["spec-no-bag-drawing"]["examples"] = [{"id": f"{s['id']} ({len(spec_links[s['id']])} parts)", "url": SITE + "/rc/"} for s in undrawn[:args.examples]]
    else:
        results["spec-no-bag-drawing"] = {"fix": "hobbydex site not found (--site)", "count": None, "examples": [], "all": []}

    unspec = [p for p in parts if p.get("category") in HW and not has_spec(p) and SIZE.search(p.get("name", ""))]
    check("hw-size-no-spec", "link the part to the spec of its size (equivalent_to, match functional), or add that spec",
          unspec, per_brand=per_brand(unspec))

    callouts = [p for p in parts if CALLOUT_PAREN.search(p.get("name", "")) or CALLOUT_JOINED.search(p.get("name", "")) or PCS.search(p.get("name", ""))]
    kinds = collections.Counter()
    for p in callouts:
        n = p.get("name", "")
        kinds["(CODE xN)"] += bool(CALLOUT_PAREN.search(n))
        kinds["CODExN"] += bool(CALLOUT_JOINED.search(n))
        kinds["Npcs"] += bool(PCS.search(n))
    check("name-callout-or-count", "strip the manual callout or count from the name (a count belongs in pack_qty, a callout in the release's notes)",
          callouts, per_brand=per_brand(callouts), breakdown=("pattern", [f"{k} {v}" for k, v in kinds.items()]))

    if tools["tamico"] and tools["classify"]:
        cls = tools["classify"]
        dealer = collections.defaultdict(set)   # part id -> kinds the dealer's German or English name gives
        with open(tools["tamico"], encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                kind = cls(row["tamico_name"])
                if kind:
                    dealer[row["part"]].add(kind)
        clash = [p for p in parts if p["id"] in dealer and p.get("name_source") == "ocr" and p.get("category")
                 and any(k != p["category"] for k in dealer[p["id"]])]
        check("ocr-kind-vs-dealer", "compare the part's category with the dealer's name: fix the category, or the OCR name if the scan misread it",
              clash, per_brand=per_brand(clash))

    near = tools["near"] or near_local
    by_name = collections.defaultdict(list)   # (brand, name) of OCR-named parts -> parts
    for p in parts:
        if p.get("name_source") == "ocr" and p.get("number"):
            by_name[(brand_of(p), p["name"].strip().lower())].append(p)
    twins = []
    for group in by_name.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if near(str(a["number"]), str(b["number"])):
                    twins.append((a, b))
    check("ocr-number-twins", "settle the number: the scan's digit may be misread (5/6, 3/8, 0/8, 1/7); check the maker's page and fold the wrong one into the right one",
          [x["id"] for pair in twins for x in pair], count=len(twins), per_brand=per_brand([a for a, _ in twins]))
    results["ocr-number-twins"]["examples"] = [{"id": f"{a['id']} ~ {b['id']}", "url": url_for(a)} for a, b in twins[:args.examples]]

    wire = [p for p in parts if p.get("category") == "wire" and PLUG.search(p.get("name", "")) and not p.get("connectors")]
    check("wire-plug-no-connectors", "set connectors to the plugs the lead carries (from the name or the maker's page)", wire, per_brand=per_brand(wire))

    bat = [p for p in parts if p.get("category") in ("battery", "esc") and not p.get("connector")]
    check("battery-esc-no-connector", "set connector to the plug the pack or ESC uses (from the maker's page or manual)", bat, per_brand=per_brand(bat))

    # Horizon-owned brands: parts with no maker link (tools/link_horizon_pages.py links the item's page; a part Horizon does not list stays unlinked)
    hz = [p for p in parts if p.get("brand") in horizon and not any(l.get("kind") not in ("dealer", "fan-site") for l in p.get("links", []))]
    hz_brands = collections.Counter(p["brand"].split("/")[-1] for p in hz)
    check("horizon-part-no-maker-link", "run tools/link_horizon_pages.py (queues the item's Horizon page first; a part Horizon lists nowhere stays unlinked)",
          hz, per_brand=hz_brands.most_common())

    hw_box = []
    for r in rels:
        if r.get("kind") != "kit" or not any(docs.get(d, {}).get("kind") in ("manual", "exploded_view") for d in r.get("documents", [])):
            continue
        n = sum(1 for c in r.get("contains", []) if c.get("role") == "kit" and part_of.get(c["part"], {}).get("category") in HW)
        if n < 10:
            hw_box.append(r)
    check("kit-box-few-hardware", "read the box's hardware from the manual or exploded view into contains (role kit): fewer than 10 hardware rows here",
          hw_box, per_brand=per_brand(hw_box))

    # bearings: the material most of a brand's bearings carry, that at most 5% of those names say, is a default: no source states it
    MAT_WORDS = {"steel": r"steel|chrom|hardened", "ceramic": r"ceramic", "stainless": r"stainless", "titanium": r"titan",
                 "aluminium": r"alumin", "carbide": r"carbide", "brass": r"brass", "bronze": r"bronze", "plastic": r"plastic|nylon|delrin"}
    per = collections.defaultdict(list)
    for p in parts:
        if p.get("category") == "bearing": per[p.get("brand")].append(p)
    flat = []
    for b, ps in per.items():
        for m, word in MAT_WORDS.items():
            with_m = [p for p in ps if p.get("material") == m]
            if len(with_m) >= 10 and 2 * len(with_m) >= len(ps) and b in brands \
                    and 20 * sum(1 for p in with_m if re.search(word, p.get("name", ""), re.I)) <= len(with_m):
                flat.append(brands[b]); break
    check("bearing-default-material", "set the bearings' material from the maker's page or name, or remove it: most of the brand's bearings carry one material that none of their names says (a default, not a source)",
          flat, detail="brands whose most bearings carry a material no name states")

    st = os.statvfs("/tmp")
    used = 100 * (st.f_files - st.f_ffree) / st.f_files if st.f_files else 0.0
    scratch = sorted(((sum(len(fs) for _, _, fs in os.walk(sp)), sp) for sp in glob.glob(f"/tmp/claude-{os.getuid()}/*/*/scratchpad")), reverse=True)
    check("tmp-inodes", "/tmp is above 50% of its inodes: delete the scratchpad folders listed (tmpfs; builds and big exports go on disk)",
          [], count=int(used > 50), detail=f"/tmp inodes {used:.1f}% used ({st.f_files - st.f_ffree} of {st.f_files})")
    results["tmp-inodes"]["examples"] = [{"id": f"{n} files {sp}", "url": ""} for n, sp in scratch[:args.examples]]

    ranked = sorted((n for n in results if results[n]["count"]), key=lambda n: -results[n]["count"])
    skipped = [n for n in results if results[n]["count"] is None]
    if args.list:
        for i in results.get(args.list, {}).get("all", []):
            print(i)
        return
    print(f"{'check':34} {'count':>7}  examples (hobbydex.com)  ->  fix")
    for n in ranked:
        r = results[n]
        print(f"{n:34} {r['count']:>7}  " + "  ".join(e["id"] for e in r["examples"]))
        if r.get("detail"):
            print(f"{'':34} {'':>7}    {r['detail']}")
        if r.get("breakdown"):
            label, rows = r["breakdown"]
            print(f"{'':34} {'':>7}    by {label}: " + "; ".join(rows[:15]))
        if r.get("per_brand"):
            print(f"{'':34} {'':>7}    per brand: " + ", ".join(f"{b} {c}" for b, c in r["per_brand"][:15]))
        for e in r["examples"][:args.examples]:
            if e["url"]:
                print(f"{'':34} {'':>7}    {e['url']}")
            else:
                print(f"{'':34} {'':>7}    {e['id']}")
        print(f"{'':34} {'':>7}    fix: {r['fix']}")
        if n == "classifier-drift":
            for k, v in results[n]["transitions"]:
                print(f"{'':34} {'':>7}    {k}: {v}")
        if n == "art-missing-photo":
            print(f"{'':34} {'':>7}    skip reasons: {results[n]['skip_reasons']}")
    for n in [n for n in results if results[n]["count"] == 0 and results[n].get("detail")]:
        print(f"{n:34} {'ok':>7}  {results[n]['detail']}")
    for n in skipped:
        print(f"{n:34} {'skipped':>7}  {results[n]['fix']}")
    if args.json:
        out = {n: {k: v for k, v in r.items() if k != "all"} | {"all": r.get("all", [])} for n, r in results.items()}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    main()
