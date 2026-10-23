"""Gap audit: what the data and the site get wrong or leave out, ranked.

Reads data/ directly (TOML) plus the caches the checks need in hobbydex-tools
(the downloaded manuals, the art photo sources, the part classifier). Each
check prints a count, five example ids with their hobbydex.com page, and the
fix. The full list of one check: --list NAME. JSON for scripts: --json FILE.

    python3 -I tools/audit.py                    # ranked summary
    python3 -I tools/audit.py --list manual-unlinked
    python3 -I tools/audit.py --json work/audit.json
    python3 -I tools/audit.py --tools ../hobbydex-tools

Exit code 0 always: this is a to-do list. Runs in well under five minutes.
"""
import argparse, collections, importlib.util, json, os, re, sys, tomllib

SITE = "https://hobbydex.com"
HERE = os.path.dirname(os.path.abspath(__file__))
RC = os.path.dirname(HERE)
YEAR = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")
BANNED_HOSTS = re.compile(r"https?://[^\s\"')]*(houseofrc|tamico)[^\s\"')]*", re.I)
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


def load_tools(tools):
    """The classifier and the art sources, from hobbydex-tools (None when absent)."""
    out = {"classify": None, "sources": None, "cache": None, "ocr": None}
    guard = os.path.join(tools, "tools", "ocr_numbers.py")   # the OCR number guard: twins and name kinds of OCR-named Tamiya parts
    if os.path.exists(guard):
        spec = importlib.util.spec_from_file_location("ocr_numbers", guard)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.join(tools, "tools"))
        try:
            spec.loader.exec_module(mod)
            out["ocr"] = mod
        except Exception as e:  # the audit still runs without it
            print(f"note: OCR number guard not loaded ({e})", file=sys.stderr)
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
        except Exception as e:  # the audit still runs without it
            print(f"note: classifier not loaded ({e})", file=sys.stderr)
        finally:
            sys.path.remove(HERE)
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
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tools", default=os.path.join(RC, "..", "hobbydex-tools"))
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
        cls = tools["classify"]
        moves = collections.Counter()
        drift = collections.defaultdict(list)
        for p in parts:
            if p.get("category_source") == "curated" or p["name"] == (p.get("number") or ""):
                continue
            new = cls(p["name"])
            if new is None:
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
        if BANNED_HOSTS.search(text):
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

    # 29. OCR-named Tamiya parts: a number with a same-name near twin (a digit misread), and a name whose kind
    # (screw, nut, bearing...) disagrees with the tamico.de German name of the same number (a neighbouring
    # line's number on a name). The guard lives in hobbydex-tools (tools/ocr_numbers.py).
    ocr = tools.get("ocr")
    if ocr:
        tam = [p for p in parts if p["id"].startswith("part/tamiya/")]
        twins = ocr.audit_twins(tam)
        check("tamiya-ocr-number-twin", "the OCR number is likely a misread: fold the read number into its twin (former_ids), or give the part its number from the maker's page; tools/ocr_numbers.py lists the twin",
              [{"id": f"part/tamiya/{n}"} for n, _ in twins], count=len(twins), twins={f"part/tamiya/{n}": [f"part/tamiya/{t}" for t in ts] for n, ts in twins})
        kinds = ocr.kind_mismatch(tam, ocr.tamico_rows(os.path.join(ocr.CACHE, "notes", "tamiya", "tamico-names.tsv")))
        check("tamiya-ocr-kind-mismatch", "the name is another part's (a neighbouring card line's number on it): read the part's name from the card or the maker's page; the tamico.de German name disagrees in kind",
              [{"id": f"part/tamiya/{n}"} for n, _, _ in kinds], count=len(kinds), names={f"part/tamiya/{n}": [o, t] for n, o, t in kinds})

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
        if r.get("per_brand"):
            pass
        for e in r["examples"][:args.examples]:
            print(f"{'':34} {'':>7}    {e['url']}")
        print(f"{'':34} {'':>7}    fix: {r['fix']}")
        if n == "classifier-drift":
            for k, v in results[n]["transitions"]:
                print(f"{'':34} {'':>7}    {k}: {v}")
        if n == "art-missing-photo":
            print(f"{'':34} {'':>7}    skip reasons: {results[n]['skip_reasons']}")
        if n == "release-no-product-page":
            print(f"{'':34} {'':>7}    per brand: {results[n]['per_brand'][:12]}")
    for n in skipped:
        print(f"{n:34} {'skipped':>7}  {results[n]['fix']}")
    if args.json:
        out = {n: {k: v for k, v in r.items() if k != "all"} | {"all": r.get("all", [])} for n, r in results.items()}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    main()
