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
import argparse, collections, csv, importlib.util, json, os, re, subprocess, sys, tempfile, tomllib, urllib.parse

SITE = "https://hobbydex.com"
HERE = os.path.dirname(os.path.abspath(__file__))
RC = os.path.dirname(HERE)
HW = {"bearing", "screw", "nut", "washer-shim", "clip", "pin", "ball-end", "o-ring-seal", "turnbuckle", "rod-end"}   # hardware part categories
PLUG = re.compile(r"\b(plug|connector|bullet|xt\d*|deans|jr|t-plug|banana|jst|xh|ec\d)\b", re.I)
CONFUSABLE = [frozenset(p) for p in (("5", "6"), ("3", "8"), ("0", "8"), ("1", "7"))]
BANNED_HOSTS = re.compile(r"https?://[^\s\"')]*(houseofrc|tamico)[^\s\"')]*", re.I)
# a tamico.de dealer link (kind = "dealer") is allowed for Tamiya spares without a maker page (tools/link_tamico_spares.py)
# Xtra Speed has no maker page: the owner chose tamico.de's listings as its dealer fallback (hobbydex-tools docs/decisions.md,
# 2026-10-23), so the two documents that stand for those listings keep their tamico.de address
TAMICO_OWNER_DOCS = ("data/documents/xtra-speed/tamico-",)
TAMICO_DEALER_LINK = re.compile(r'\{ site = "tamico\.de", url = "[^"]*", kind = "dealer" \}')
SCRAP_IMG = re.compile(r"https?://[^\s\"')]*rcscrapyard[^\s\"')]*\.(jpe?g|png|gif|webp)", re.I)
LOCAL_PATH = re.compile(r"(^|[\s\"'(=])(/home/|/Users/|/tmp/|file://|[A-Za-z]:\\|work/manuals/|cache/)")
FIX_PAGE = "add the maker's product page as a document (kind product_page, page = the maker's URL) and list it in the release's documents"


# the folders every real data checkout has records in: an empty one is a wrong or half-present checkout, never "no holes"
REQUIRED_FOLDERS = ("brands", "kits", "releases", "parts", "documents")


def _raise(err):
    raise err


def walk(top):
    """os.walk that fails on a folder it cannot list (os.walk skips it silently). A top folder that does not exist is
    empty, as before; any other error, at the top or below it, raises."""
    if not os.path.isdir(top):
        if os.path.lexists(top):
            raise NotADirectoryError(f"{top}: not a folder")
        return iter(())
    return os.walk(top, onerror=_raise)


def load(root):
    data = os.path.join(root, "data")
    if not os.path.isdir(data):
        raise SystemExit(f"audit: {data} is not a folder: --rc (or HOBBYDEX_RC) must name a data checkout")
    db = collections.defaultdict(list)
    for folder in ("brands", "kits", "releases", "parts", "documents", "specs", "categories", "companies", "makes", "standards"):
        for dp, _, fs in walk(os.path.join(data, folder)):
            for fn in sorted(fs):
                if fn.endswith(".toml"):
                    path = os.path.join(dp, fn)
                    with open(path, "rb") as f:
                        d = tomllib.load(f)
                    d["_path"] = os.path.relpath(path, root)
                    db[folder].append(d)
    empty = [f for f in REQUIRED_FOLDERS if not db[f]]
    if empty:
        raise SystemExit(f"audit: no records in data/{', data/'.join(empty)} of {root}: a wrong or half-present data "
                         f"checkout, not one without holes")
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


# the per-host English addresses of the maker links: hobbydex-tools tools/data/english_variants.toml (read by link_language_variants.py too)
ENGLISH_MISSING = "hobbydex-tools tools/data/english_variants.toml not found (--tools): the English addresses of the maker links are read from it"
ENGLISH_LINK = re.compile(r"https?://[^\s\"'<>)\]]+")
ERROR_RX = re.compile(r"Fatal error|Call to (?:a )?member function|Parse error:|Uncaught (?:Exception|Error)")   # a PHP error page (the English shop answers so)


# a name read from an English page ("https://rc.kyosho.com/en/32629w.html"): its German-looking words are the maker's
ENGLISH_PAGE = re.compile(r"/en(?:[-_][a-z]{2})?(?:/|\.html?|$)|[?&](?:lang|language)=en\b", re.I)


def german_names(records, german_words):
    """[(record, German words)] of the parts and releases whose name still has German words (german_words:
    hobbydex-tools translate_de.german_words). A name whose source (sources.name) is an English page is the maker's
    English and is not listed (Kyosho's "V.specII Nür")."""
    out = []
    for r in records:
        if not isinstance(r.get("name"), str):
            continue
        src = (r.get("sources") or {}).get("name") if isinstance(r.get("sources"), dict) else None
        if isinstance(src, str) and ENGLISH_PAGE.search(src):
            continue
        words = german_words(r["name"])
        if words:
            out.append((r, words))
    return out


def english_swaps(path):
    """{host: (from, to)} of the swap rules in the English table at path: a maker link under `from` has its English
    address under `to`."""
    with open(path, "rb") as fh:
        hosts = tomllib.load(fh)["hosts"]
    return {r["host"]: (r["from"], r["to"]) for r in hosts if r.get("how") == "swap"}


def non_english(url, swaps):
    """Whether url is a maker link of a host with a swap rule that is not under the English address."""
    host = urllib.parse.urlsplit(url).hostname or ""
    rule = swaps.get(host)
    if not rule:
        return False
    u = url if url.count("/") > 2 else url + "/"
    return u.startswith(rule[0]) and not u.startswith(rule[1])


def english_twin(url, swaps):
    """The English address of a maker link under a swap rule, or None."""
    rule = swaps.get(urllib.parse.urlsplit(url).hostname or "")
    return rule[1] + url[len(rule[0]):] if rule and url.startswith(rule[0]) else None


def has_foreign_link(text, swaps, gone=frozenset(), unavailable=None):
    """Whether a record's text has a non-English maker link with no English twin beside it in the same record.
    A twin the crawl found gone (gone: the URLs the queue marks gone) is no switch: the maker has no such page.
    unavailable(twin, url, text) -> True for a twin that is no English page of the item (the English page failed in the
    crawl, answers with an error, or names none of the record's item numbers): the link stays and is not listed."""
    links = [u for line in text.splitlines() if not line.lstrip().startswith("notes") for u in ENGLISH_LINK.findall(line)]
    here = set(links)
    for u in links:
        twin = english_twin(u, swaps)
        if non_english(u, swaps) and twin not in here and twin not in gone:
            if unavailable and unavailable(twin, u, text):
                continue
            return True
    return False


def english_state(cache, swaps):
    """{url: (status, path)} of the queue rows that are done or failed on the English hosts of the swap rules (read-only)."""
    hosts = sorted({urllib.parse.urlsplit(to).hostname or "" for _, to in swaps.values()})
    crawl = (os.environ.get("HOBBYDEX_CRAWL_DB") or os.path.join(cache, "crawl.db")) if cache else ""   # the daily audit's copy
    if not hosts or not crawl or not os.path.exists(crawl):
        return {}
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % crawl, uri=True)
    try:
        rows = con.execute("select url, status, path from queue where status in ('done', 'failed') and host in (%s)" % ",".join("?" * len(hosts)), hosts).fetchall()
    finally:
        con.close()
    return {u: (s, p) for u, s, p in rows}


def record_numbers(text, url):
    """The item numbers a record's link names: its `number`, the 5-plus digit runs of its id, and of the maker link."""
    nums = set(re.findall(r"(?<!\d)(\d{5,})(?!\d)", url))
    m = re.search(r'^number = "([^"]+)"', text, re.M)
    if m:
        nums.add(m.group(1))
    i = re.search(r'^id = "(.*)"', text, re.M)
    if i:
        nums.update(re.findall(r"(?<!\d)(\d{5,})(?!\d)", i.group(1).rsplit("/", 1)[-1]))
    return nums


def english_unavailable(english):
    """The unavailable() of has_foreign_link for the English addresses in english (url -> (status, path))."""
    def check(twin, url, text):
        st = english.get(twin)
        if st is None:
            return False
        status, path = st
        if status == "failed":
            return True   # the crawl gave up: the maker's English page answers with a server error
        if not path or not os.path.exists(path):
            return False
        page = open(path, "rb").read().decode("utf-8", "replace")
        if ERROR_RX.search(page):
            return True   # a PHP error page in place of the product
        nums = record_numbers(text, url)
        return bool(nums) and not any(re.search(r"(?<!\d)" + re.escape(n) + r"(?!\d)", page) for n in nums)
    return check


def gone_urls(cache, swaps):
    """The URLs the crawl queue marks gone on the English hosts of the swap rules (read-only; empty without a queue)."""
    hosts = sorted({urllib.parse.urlsplit(to).hostname or "" for _, to in swaps.values()})
    crawl = (os.environ.get("HOBBYDEX_CRAWL_DB") or os.path.join(cache, "crawl.db")) if cache else ""   # the daily audit's copy
    if not hosts or not crawl or not os.path.exists(crawl):
        return frozenset()
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % crawl, uri=True)
    try:
        rows = con.execute("select url from queue where status='gone' and host in (%s)" % ",".join("?" * len(hosts)), hosts).fetchall()
    finally:
        con.close()
    return frozenset(u for (u,) in rows)


def walk_strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from walk_strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from walk_strings(x)


def near_local(a, b):
    """b is a's number with one or two digits off, each off digit a confusable pair (same length)."""
    if len(a) != len(b) or a == b:
        return False
    diff = [frozenset((x, y)) for x, y in zip(a, b) if x != y]
    return len(diff) <= 2 and all(p in CONFUSABLE for p in diff)


# A cached PDF whose name states no manual kind is a non-manual only when its name says what it is (paint
# safety sheets, battery and safety notices, press releases, product sheets, declarations of conformity). Any other name with no kind
# word (a car-named file such as "300012657_Ducati_Gabel-Set.pdf") is "kind unknown" and stays a gap.
NOT_MANUAL_NAME = re.compile(r"msds|sicherheit|safety|warning|hinweis|akku|battery|lipo|press|news|video|product|"
                             r"datenblatt|data ?sheet|spruehfarbe|paint|flyer|leaflet|declaration|conformity|konformit|"
                             r"catalog|katalog|preis|price|compatib|required.?separately|setting.?sheet|"
                             r"spezifikation|specification|leistungsmerkmale|\u898f\u683c\u66f8|\u89c4\u683c\u4e66|\u304a\u77e5\u3089\u305b|"
                             r"^od\d{4}[a-z]?-20\d{6}-", re.I)
# The \u escapes are Japanese and Chinese words for a spec sheet and a notice (規格書, 规格书, お知らせ). The last pattern is
# Overdose's shop notice ("OD2500-20250922-OD2491-OD3889-o": an item, the date, the items it names): a one-page image
# of "商品に関するお知らせ" (delivery dates of the named parts), never a manual.


def name_slug(path):
    """The file name of a path or address without its extension, lower case, letters and digits only."""
    base = os.path.basename(urllib.parse.unquote(urllib.parse.urlsplit(path).path))
    return re.sub(r"[^a-z0-9]", "", re.sub(r"(?i)\.pdf$", "", base).lower())


def archive_files(docs, resolve):
    """{real path of a cached PDF: [documents]} for the archive documents that carry no file or url of their own (RC
    Documents, Valkyrie): their file is the PDF their listing page links, which resolve(id, doc) returns as (path, why)
    (tools/archive_pdf.py). A document whose PDF is not cached maps nothing; resolve None maps nothing."""
    out = collections.defaultdict(list)
    if resolve is None:
        return out
    for did, d in docs.items():
        if d.get("page") and not d.get("url") and not d.get("file"):
            path = resolve(did, d)[0]
            if path:
                out[os.path.realpath(path)].append(d)
    return out


TRUNCATED = re.compile(r"(?i)^(.*)\.truncated-\d{4}-\d\d-\d\d\.pdf$")


def truncated_full(rel):
    """The path of the complete file of a PDF the crawl set aside as cut short (hobbydex-tools tools/crawl.py
    truncated_aside: <name>.truncated-<YYYY-MM-DD>.pdf), or None for any other file."""
    m = TRUNCATED.match(rel)
    return m.group(1) + ".pdf" if m else None


def archive_copy_of_maker_manual(rel, held):
    """True for an archive scan (manuals/rcscrapyard/<brand>/<name>.pdf) whose name holds the item number of a release of
    that brand that lists the maker's manual (hobbydex-tools tools/import_manual_archives.py: the maker wins, the archive
    copy gets no document); held is the set of (brand slug, number in upper case) of those releases."""
    seg = rel.split("/")
    if len(seg) != 4 or seg[:2] != ["manuals", "rcscrapyard"]:
        return False
    stem = re.sub(r"(?i)\.pdf$", "", seg[3])
    return any((seg[2], t.upper()) in held for t in re.split(r"[^A-Za-z0-9]+", stem) if len(t) >= 4 and re.search(r"\d", t))


def drop_copies_of_linked(cache, unlinked, linked_files):
    """The unlinked cached files (paths relative to the cache) that are not a byte-identical copy of a linked file of the
    same brand (second path part): same size first, then the SHA-256."""
    import hashlib
    def brand(rel):
        return rel.split("/")[1]
    def sha(rel):
        h = hashlib.sha256()
        with open(os.path.join(cache, rel), "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    sizes = collections.defaultdict(list)
    for rel in linked_files:
        try:
            sizes[brand(rel), os.path.getsize(os.path.join(cache, rel))].append(rel)
        except OSError:
            pass
    out, known = [], {}
    for rel in unlinked:
        try:
            cands = sizes.get((brand(rel), os.path.getsize(os.path.join(cache, rel))))
            if cands:
                digest = sha(rel)
                if any(known.setdefault(c, sha(c)) == digest for c in cands):
                    continue
        except OSError:
            pass
        out.append(rel)
    return out


def not_manual_name(stem):
    """True when a file name identifies a non-manual (safety sheet, battery notice, press release, product sheet)."""
    return NOT_MANUAL_NAME.search(stem) is not None


# Tamiya item numbers of static kits and other items that are not RC: plastic kits, figures and military (10000-39999),
# aircraft and dinosaur kits (60000-61999), airbrushes, tools, paints, putty, ships (74000-89999). The shop's article
# is 3000 + the item number (cache/manuals/tamiya-de/<article>). Option parts (40000-56999), RC cars and tanks (56-58xxx),
# the 70xxx crawlers and every number the data has as a Tamiya release or part stay in the check.
TAMIYA_STATIC = ((10000, 39999), (60000, 61999), (74000, 89999))


HORIZON_LIST_KINDS = ("exploded_view", "part_list", "manual", "supplement")   # documents that list parts, not pages that sell them
IMAGE_URL = re.compile(r"\.(?:jpe?g|png|gif)$", re.I)


def horizon_no_page(part, docs, gone):
    """True when a Horizon part has no maker page to link: every document that names it is an exploded view, a parts
    list, a manual or a supplement, its seen_by_source is such a document (or a captured product image), and its item
    page answers 404 in the cache (gone: the item numbers with a cached horizon-items/<number>-item.html.http404.txt)."""
    if part.get("number") not in gone or not part.get("documents"):
        return False
    if any(docs.get(d, {}).get("kind") not in HORIZON_LIST_KINDS for d in part["documents"]):
        return False
    src = part.get("seen_by_source")
    if not src or src in docs:
        return not src or docs[src].get("kind") in HORIZON_LIST_KINDS
    return bool(IMAGE_URL.search(src))


def horizon_gone_items(tools):
    """Item numbers whose Horizon item page answered 404 (cache/notes/horizon-items/<number>-item.html.http404.txt)."""
    d = os.path.join(tools, "cache", "notes", "horizon-items")
    suffix = "-item.html.http404.txt"
    return {n[:-len(suffix)] for n in os.listdir(d) if n.endswith(suffix)} if os.path.isdir(d) else set()


def tamiya_static_non_rc(rel_path, tamiya_numbers):
    """True when a cached tamiya-de file (rel_path relative to cache/) is a static kit, paint or tool: its item number
    is in TAMIYA_STATIC and no Tamiya release or part of the data has that number, so no release can take the manual."""
    seg = rel_path.replace(os.sep, "/").split("/")
    if len(seg) < 4 or seg[0] != "manuals" or seg[1] != "tamiya-de":
        return False
    m = re.fullmatch(r"3000(\d{5})", seg[2])
    if m is None or m.group(1) in tamiya_numbers:
        return False
    return any(lo <= int(m.group(1)) <= hi for lo, hi in TAMIYA_STATIC)


# what the audit says when cache/gtin_sweep_holes.json is absent: the file is written by `report`, which reads the index `scan` builds
GTIN_HOLES_MISSING = ("hobbydex-tools cache/gtin_sweep_holes.json not found: it is written by tools/gtin_sweep.py report, which needs "
                      "the index: run python3 -I tools/gtin_sweep.py scan, then python3 -I tools/gtin_sweep.py report")


def load_gtin_holes(tools):
    """{record id: [code, label, cached file]} of the barcodes the cache states for a record (hobbydex-tools
    tools/gtin_sweep.py report writes cache/gtin_sweep_holes.json); None when the file is absent."""
    p = os.path.join(tools, "cache", "gtin_sweep_holes.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("holes", {})
    except (OSError, ValueError):
        return None


def load_linker_drift(tools):
    """[(step, files)] of the last daily derive's verify pass (hobbydex-tools tools/derive_fields.py writes
    cache/notes/linker-drift.tsv: step, files changed on a second run over the data it had just derived, date);
    None when the file is absent."""
    p = os.path.join(tools, "cache", "notes", "linker-drift.tsv")
    try:
        with open(p, encoding="utf-8") as f:
            rows = [ln.rstrip("\n").split("\t") for ln in f if ln.strip() and not ln.startswith("step\t")]
    except OSError:
        return None
    return [(r[0], int(r[1])) for r in rows if len(r) >= 2 and r[1].isdigit()]


CHILD_TIMEOUT = 3600   # seconds a tool the audit runs may take; past it the check says "child timed out" and the audit goes on.
# A cold run of link_maker_pages.py takes about 21 minutes; a kill also loses what it parsed, so the limit leaves room.


def run_child(args, timeout=CHILD_TIMEOUT, **kw):
    """subprocess.run for a tool the audit runs: the captured result, or None when the tool runs past timeout
    (subprocess kills it). A hung child must not hang the audit: the check reports the timeout instead."""
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kw)
    except subprocess.TimeoutExpired:
        names = [os.path.basename(a) for a in args if a.endswith(".py")]
        print(f"child timed out after {timeout} s: {' '.join(names)}", file=sys.stderr)
        return None


def linkers_that_would_change(drift):
    """Lines "<step>: <n> files" for each wired linker that changed data when run again over derived data (it should change none)."""
    return [f"{step}: {n} files" for step, n in drift if n]


def gtin_in_cache_not_stored(holes, by_id):
    """Ids of the records the sweep found a barcode for in the cache that still have no gtin."""
    return sorted(i for i in holes if i in by_id and not by_id[i].get("gtin"))


def check_spans(tools, environ=None):
    """A recorder of the checks as spans (hobbydex-tools docs/observability.md, Traces): each check() call ends the
    span "check <name>" that began where the previous one ended (the work between two checks is the next check's),
    under the span TRACEPARENT names (the audit job's "python audit" part). None without TRACEPARENT or tools/otel.py:
    then nothing is recorded."""
    e = os.environ if environ is None else environ
    m = re.fullmatch(r"[0-9a-f]{2}-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}", (e.get("TRACEPARENT") or "").strip())
    path = os.path.join(tools, "tools", "otel.py")
    if not m or not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("otel", path)
    otel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(otel)
    import secrets, time
    trace, parent = m.group(1), m.group(2)
    last = [time.time()]

    def record(name, count):
        now = time.time()
        otel.span(trace, secrets.token_hex(8), parent, f"check {name}", last[0], now, {"check": name, "count": count},
                  service="hobbydex-audit")
        last[0] = now
    record.otel = otel   # the module that sends them (tests read what it was given)
    return record


def load_tools(tools):
    """The modules and cache files of hobbydex-tools the Python checks read (None when absent)."""
    out = {"cache": None, "near": None, "english_table": None}
    english = os.path.join(tools, "tools", "data", "english_variants.toml")
    if os.path.isfile(english):
        out["english_table"] = english
    out["doc_links"] = None   # the holds and pairs of tools/sync_doc_links.py: one definition for both
    dlp = os.path.join(tools, "tools", "sync_doc_links.py")
    if os.path.exists(dlp):
        spec = importlib.util.spec_from_file_location("sync_doc_links", dlp)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            out["doc_links"] = mod
        except Exception as e:
            print(f"note: sync_doc_links not loaded ({e})", file=sys.stderr)
    out["manual_mod"] = None
    out["manual_kind"] = None   # the kind a manual's file name states (tools/link_manual_numbers.py): None for safety sheets, press releases, gear tables
    lmn = os.path.join(tools, "tools", "link_manual_numbers.py")
    if os.path.exists(lmn):
        spec = importlib.util.spec_from_file_location("link_manual_numbers", lmn)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.join(tools, "tools"))
        try:
            spec.loader.exec_module(mod)
            out["manual_kind"] = mod.kind_from_name
            out["manual_mod"] = mod   # file_url: a cached copy's address by its name (the linker's rule)
        except Exception as e:  # the manual check counts every file without it
            print(f"note: link_manual_numbers not loaded ({e})", file=sys.stderr)
        finally:
            sys.path.remove(os.path.join(tools, "tools"))
    tdir = os.path.join(tools, "tools")
    os.environ.setdefault("HOBBYDEX_RC", RC)   # the tools' paths.py (translate_de imports it) reads the data checkout
    for mname in ("name_shop", "translate_de"):   # the shop-text cleaner and the German glossary the importers use
        mp = os.path.join(tdir, mname + ".py")
        if os.path.exists(mp):
            spec = importlib.util.spec_from_file_location(mname, mp)
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, tdir)
            try:
                spec.loader.exec_module(mod)
                out[mname] = mod
            except Exception as e:  # the checks are skipped without them
                print(f"note: {mname} not loaded ({e})", file=sys.stderr)
            finally:
                sys.path.remove(tdir)
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
    out["text_layer"] = os.path.join(tools, "cache", "notes", "tamiya", "text-layer-numbers.tsv")
    out["gtin_holes"] = load_gtin_holes(tools)
    out["linker_drift"] = load_linker_drift(tools)
    cache = os.path.realpath(os.path.join(tools, "cache"))   # the queue's paths are real paths
    if os.path.isdir(os.path.join(cache, "manuals")):
        out["cache"] = cache
    # the PDF an archive document's listing page links (RC Documents, Valkyrie: tools/archive_pdf.py resolve)
    out["archive_resolve"] = None
    ap = os.path.join(tools, "tools", "archive_pdf.py")
    if os.path.exists(ap):
        spec = importlib.util.spec_from_file_location("archive_pdf", ap)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.join(tools, "tools"))
        os.environ.setdefault("HOBBYDEX_RC", RC)   # the tools' paths.py reads the data checkout from it
        try:
            spec.loader.exec_module(mod)
            out["archive_resolve"] = mod.resolve
        except Exception as e:  # the archive documents then count no file
            print(f"note: archive_pdf not loaded ({e})", file=sys.stderr)
        finally:
            sys.path.remove(os.path.join(tools, "tools"))
    return out


def text_layer_numbers(path):
    """The numbers a maker text layer prints: the first column of cache/notes/<brand>/text-layer-numbers.tsv
    (written by tools/ocr_numbers.py --build-text). A missing file gives none."""
    if not path or not os.path.exists(path):
        return set()
    out = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or line.startswith("number\t") or not line.strip():
                continue
            out.add(line.split("\t")[0])
    return out


def reviewed_distinct(path):
    """The Tamiya numbers reviewed as two different parts (data/reviewed-distinct.toml: a [[reviewed]] table per
    number, with its name, manual and page). A missing file gives none."""
    if not os.path.exists(path):
        return set()
    with open(path, "rb") as fh:
        return {r["number"] for r in tomllib.load(fh).get("reviewed", [])}


def usa_spare_reviewed(path):
    """The (part, Tamiya USA page) pairs checked by eye (data/usa-spare-reviewed.toml: a [[reviewed]] table per pair
    with its verdict and evidence). A missing file gives none."""
    if not os.path.exists(path):
        return set()
    with open(path, "rb") as fh:
        return {(r["part"], r["usa"]) for r in tomllib.load(fh).get("reviewed", [])}


def both_reviewed(a, b, reviewed):
    """Both numbers of a pair are reviewed as two different parts (reviewed_distinct): not a misread of each other."""
    return str(a["number"]) in reviewed and str(b["number"]) in reviewed


def printed_pair(a, b, printed):
    """Both numbers of a twin pair are printed in a maker text layer: two parts, not one misread number."""
    return str(a["number"]) in printed and str(b["number"]) in printed


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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tools", default=os.path.join(RC, "..", "hobbydex-tools"))
    ap.add_argument("--site", default=os.path.join(RC, "..", "hobbydex"), help="the site checkout (unused here: spec-no-bag-drawing, which reads its hardware drawings, is the Rust audit's; the daily job passes it to both)")
    ap.add_argument("--list", metavar="CHECK", help="every id one check flags")
    ap.add_argument("--json", metavar="FILE", help="write the full result as JSON")
    ap.add_argument("--examples", type=int, default=5)
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="backslashreplace")
    os.chdir(RC)
    tools = load_tools(os.path.abspath(args.tools))   # before the records: the classifier's workers fork from a small heap
    db = load(RC)
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
    spans = check_spans(os.path.abspath(args.tools))

    def check(name, fix, items, count=None, **extra):
        """items: a list of records (or ids) flagged; count defaults to len(items)."""
        ids = [x if isinstance(x, str) else x["id"] for x in items]
        recs = [{"id": i, "url": url_for(by_id.get(i, {"id": i}))} for i in sorted(set(ids))]
        results[name] = {"fix": fix, "count": len(set(ids)) if count is None else count, "examples": recs[:args.examples], "all": sorted(set(ids)), **extra}
        if spans:
            spans(name, results[name]["count"])

    # 6. downloaded manuals (hobbydex-tools cache/manuals) not linked to a release
    if tools["cache"]:
        # cache/manuals/** and cache/notes/<brand>/pdf/**; paths are relative to cache/
        pdf_dirs = [os.path.join(tools["cache"], "manuals")]
        notes = os.path.join(tools["cache"], "notes")
        if os.path.isdir(notes):
            pdf_dirs += [os.path.join(notes, b, "pdf") for b in sorted(os.listdir(notes)) if os.path.isdir(os.path.join(notes, b, "pdf"))]
        cached = []
        for top in pdf_dirs:
            for dp, _, fs in walk(top):
                for fn in fs:
                    if fn.lower().endswith(".pdf"):
                        cached.append(os.path.relpath(os.path.join(dp, fn), tools["cache"]))
        # a doc is linked when a release or a part lists it, or when it lists a kit (a maker's manual of the platform:
        # docs/schema.md "kits")
        on_part = {dd for p in parts for dd in p.get("documents", [])}
        linked_docs = set(doc_rels) | on_part | {d["id"] for d in docs.values() if d.get("kits")}
        # the crawl queue maps each cached file to the URL it came from
        url_of = {}
        crawl = os.environ.get("HOBBYDEX_CRAWL_DB") or os.path.join(tools["cache"], "crawl.db")   # the daily audit's copy
        if os.path.exists(crawl):
            import sqlite3
            con = sqlite3.connect("file:%s?mode=ro" % crawl, uri=True)
            for path, url in con.execute("select path, url from queue where kind='pdf'"):
                url_of.setdefault(os.path.relpath(path, tools["cache"]) if path.startswith(tools["cache"]) else path, url)
            con.close()
        # a copy cached under another item's number has no crawl row of its own: its address is the row of its name
        # (tools/link_manual_numbers.py file_url), so a document linked through one copy links every copy
        lmn = tools["manual_mod"]
        urls_by_name = lmn.queue_urls_by_name(tools["cache"]) if lmn and hasattr(lmn, "file_url") else {}
        # a record's file name and its URL's file name match a cached copy whatever the case: the maker's own copy of a
        # manual is named "BD8_Manual_English.pdf" on the CDN and "bd8-manual-english.pdf" in the cache
        by_name = collections.defaultdict(list)
        by_url = collections.defaultdict(list)       # the full address, as before
        by_url_name = collections.defaultdict(list)  # the address's file name, the same brand only
        by_slug = collections.defaultdict(list)      # (brand, file name in letters and digits only): the cache writes
        # "dp-yd4-160612.pdf" for the maker's "dp_yd4_160612.pdf"
        for d in docs.values():
            if d.get("file"):
                by_name[os.path.basename(d["file"]).lower()].append(d)
                by_slug[d.get("brand"), name_slug(d["file"])].append(d)
            if d.get("url"):
                by_url[d["url"]].append(d)
                by_url_name[os.path.basename(urllib.parse.urlsplit(d["url"]).path).lower()].append(d)
                by_slug[d.get("brand"), name_slug(urllib.parse.urlsplit(d["url"]).path)].append(d)
        # a linked archive document (no file of its own) is linked to the PDF its listing page gives it
        arch_by_path = archive_files({i: d for i, d in docs.items() if i in linked_docs}, tools["archive_resolve"])
        unlinked = []
        linked_files = []    # cached files a linked document matches (by name or address): their copies count as linked
        via_archive = 0      # cached files a linked archive document's listing page gives as its file
        not_manuals = 0      # the name says it is a safety sheet, battery notice, press release or product sheet
        not_rc = 0           # a static kit, paint or tool of Tamiya that no release or part of the data has (tamiya_static_non_rc)
        kind_unknown = 0     # the name states no manual kind and says nothing else: still a gap, counted apart
        tamiya_numbers = {str(x.get("number")) for x in rels + parts if x.get("brand") == "brand/tamiya" and x.get("number")}
        truncated = truncated_no_full = 0   # PDFs the crawl set aside as cut short (tools/crawl.py truncated_aside)
        archive_maker_held = 0   # RC Scrapyard scans of a release that lists the maker's manual (the maker wins)
        maker_held = {(r["brand"].split("/", 1)[1], str(r["number"]).upper()) for r in rels
                      if r.get("number") and str(r.get("brand", "")).startswith("brand/")
                      and any(docs.get(d, {}).get("kind") == "manual" and str(docs.get(d, {}).get("publisher", "")).startswith("brand/")
                              for d in r.get("documents", []))}
        for rel_path in cached:
            full = truncated_full(rel_path)
            if full:
                truncated += 1
                if not os.path.isfile(os.path.join(tools["cache"], full)):
                    truncated_no_full += 1
                continue
            name = os.path.basename(rel_path)
            url = url_of.get(rel_path) or (lmn.file_url(os.path.join(tools["cache"], rel_path), {}, urls_by_name)
                                           if lmn and hasattr(lmn, "file_url") else None)
            # a URL's file name counts within the cached file's brand only: "manual.pdf" is a name of many makers
            mine = "brand/" + rel_path.split("/")[1]
            same_brand_url = [d for d in by_url_name.get(os.path.basename(urllib.parse.urlsplit(url).path).lower(), [])
                              if d.get("brand") == mine] if url else []
            ds = by_name.get(name.lower(), []) + (by_url.get(url, []) if url else []) + same_brand_url
            if len(name_slug(name)) >= 8:
                ds = ds + [d for d in by_slug.get((mine, name_slug(name)), []) if d not in ds]
            arch = arch_by_path.get(os.path.realpath(os.path.join(tools["cache"], rel_path)), [])
            if arch:
                via_archive += 1
                ds = ds + [d for d in arch if d not in ds]
            if not ds and archive_copy_of_maker_manual(rel_path, maker_held):
                archive_maker_held += 1
                continue
            stem = re.sub(r"(?i)\.pdf$", "", name)
            if not any(d["id"] in linked_docs for d in ds):
                # the linker leaves a file with no kind word alone; only a file named as a non-manual is not a gap
                if not ds and tamiya_static_non_rc(rel_path, tamiya_numbers):
                    not_rc += 1
                    continue
                if not ds and tools["manual_kind"] and tools["manual_kind"](stem) is None:
                    if not_manual_name(stem):
                        not_manuals += 1
                        continue
                    kind_unknown += 1
                unlinked.append(rel_path)
            else:
                linked_files.append(rel_path)
        # a byte-identical copy (same brand, size and checksum) of a linked document's file is linked too: the cache keeps
        # copies under other names ("b6d-2016-thielke-jc-spring.pdf" next to "90012-B6D_2016_Thielke_JC_Spring.pdf")
        n_before = len(unlinked)
        unlinked = drop_copies_of_linked(tools["cache"], unlinked, linked_files)
        copies = n_before - len(unlinked)
        check("manual-unlinked", "add the cached manual as a document (file, page, url) and list it in its release's documents; a document listed by a part or matched by its URL counts as linked, and so does the PDF a linked archive document's listing page gives",
              [{"id": u} for u in unlinked], count=len(unlinked), _unlinked_ids=unlinked[:5],
              detail=f"{kind_unknown} of them name no manual kind (kind unknown: read the cover or the name); "
                     f"{not_manuals} cached PDFs named as safety sheets, notices, press releases or product sheets are left out; "
                     f"{not_rc} cached Tamiya manuals of static kits, paints and tools (not RC: no Tamiya release or part has the number) are left out; "
                     f"{copies} byte-identical copies of a linked document's file (same brand, size and checksum) count as linked; "
                     f"{via_archive} cached PDFs are the file a linked archive document's listing page gives (counted as linked); "
                     f"{truncated} PDFs the crawl set aside as cut short (.truncated-<date>.pdf) are left out, {truncated_no_full} of "
                     f"them with no complete copy cached (fetch again); {archive_maker_held} RC Scrapyard scans of a release that "
                     f"lists the maker's manual are left out (the maker wins)")
        # keep the list ids as paths; url points at the brand
        res = results["manual-unlinked"]
        res["examples"] = [{"id": u, "url": SITE + "/rc/brands/" + u.split("/")[1] + "/"} for u in unlinked[:args.examples]]
    else:
        results["manual-unlinked"] = {"fix": "hobbydex-tools cache not found (--tools)", "count": None, "examples": [], "all": []}

    # 10. parts with a cached maker product page but no maker link, and maker links to pages the crawl has as 404
    # (hobbydex-tools tools/link_maker_pages.py --dry-run reports both per brand; the daily derive step links or prunes them)
    lmp = os.path.join(os.path.abspath(args.tools), "tools", "link_maker_pages.py")
    if os.path.exists(lmp):
        with tempfile.NamedTemporaryFile("r", suffix=".tsv") as sample:
            env = dict(os.environ, HOBBYDEX_RC=RC, SAMPLE_OUT=sample.name)
            run = run_child([sys.executable, "-I", lmp, "--dry-run"], cwd=os.path.abspath(args.tools), env=env)
            if run is None:   # the child timed out: no counts, and the check says so
                timed_out = "child timed out (tools/link_maker_pages.py --dry-run)"
                results["maker-page-unlinked"] = {"fix": timed_out, "count": None, "examples": [], "all": []}
                results["maker-link-page-gone"] = {"fix": timed_out, "count": None, "examples": [], "all": []}
            else:
                unlinked, pruned, rows = {}, {}, []
                for line in run.stdout.splitlines():
                    m = re.match(r"(\S+): parts \d+, linked (\d+)", line)
                    if m and int(m[2]):
                        unlinked[m[1]] = int(m[2])
                    m = re.match(r"(\S+): links (?:removed \(page gone\)|marked gone) (\d+)", line)
                    if m:
                        pruned[m[1]] = int(m[2])
                rows = [r.rstrip("\n").split("\t") for r in sample]
                flagged = [{"id": r[1], "url": r[4]} for r in rows]
                results["maker-page-unlinked"] = {
                    "fix": "run tools/link_maker_pages.py in hobbydex-tools (the daily derive step does it); a cached 200 page that names the part gives it the link",
                    "count": sum(unlinked.values()), "examples": flagged[:args.examples],
                    "all": sorted({r["id"] for r in flagged}), "per_brand": sorted(unlinked.items(), key=lambda x: -x[1])}
                results["maker-link-page-gone"] = {
                    "fix": "the crawl has the page as 404 on a recheck; the daily derive step marks the link gone (tools/link_maker_pages.py) and an archive link follows once a capture is cached",
                    "count": sum(pruned.values()), "examples": [], "all": [], "per_brand": sorted(pruned.items(), key=lambda x: -x[1])}
    else:
        results["maker-page-unlinked"] = {"fix": "hobbydex-tools link_maker_pages.py not found (--tools)", "count": None, "examples": [], "all": []}

    # 9b. barcodes the cache states for a record that has no gtin (tools/gtin_sweep.py in hobbydex-tools finds them)
    if tools["gtin_holes"] is not None:
        miss = gtin_in_cache_not_stored(tools["gtin_holes"], by_id)
        check("gtin-in-cache-not-stored", "rerun tools/link_gtin.py in hobbydex-tools (a barcode a cached page states for exactly this number); if it does not take it, the importer misses that page format: fix the class (tools/gtin_sweep.py report writes the file it lists)",
              miss)
        results["gtin-in-cache-not-stored"]["examples"] = [{"id": i, "url": url_for(by_id[i]), "gtin": tools["gtin_holes"][i][0], "file": tools["gtin_holes"][i][2]} for i in miss[:args.examples]]
    else:
        results["gtin-in-cache-not-stored"] = {"fix": GTIN_HOLES_MISSING, "count": None, "examples": [], "all": []}

    # 9c. a wired linker that would change data (the daily derive runs each one twice; the second run must change nothing)
    if tools["linker_drift"] is not None:
        drift = linkers_that_would_change(tools["linker_drift"])
        check("linker-would-change", "a linker in hobbydex-tools tools/derive_fields.py changed data on its second run over the same data (cache/notes/linker-drift.tsv): it is not idempotent; fix it to write only empty fields, or take it out of the derive",
              drift)
        results["linker-would-change"]["examples"] = [{"id": d, "url": ""} for d in drift[:args.examples]]
    else:
        results["linker-would-change"] = {"fix": "hobbydex-tools cache/notes/linker-drift.tsv not found (written by the daily derive)", "count": None, "examples": [], "all": []}

    # multi-item-whole-part, name-count-no-pack-qty, name-callout-or-count, colour-word-no-color, hw-no-material,
    # derive-not-landed, tmp-inodes, hw-size-no-spec and its five hw-size-* sub-classes, cached-manual-no-record,
    # art-missing-photo, pack-photo-disagrees, pack-wrong-photo, pack-photo-brand-below-bar, classifier-drift,
    # with-fasteners-category, ocr-kind-vs-dealer, spec-no-bag-drawing, hw-photo-unread and video-gallery-unattached are
    # counted by the Rust audit only
    # (hobbydex-tools rust/hobbydex-audit, checks::PYTHON_RETIRED): the daily job publishes its records for them
    # 19. release lists a document that does not list the release back
    # both sides: a release lists a document that does not list it, or a document lists a release that does not list it
    rel_by_id = {r["id"]: r for r in rels}
    one_sided = [r["id"] for r in rels for d in r.get("documents", []) if d in docs and r["id"] not in (docs[d].get("releases") or [])]
    one_sided += [rid for d in docs.values() for rid in (d.get("releases") or []) if rid in rel_by_id and d["id"] not in (rel_by_id[rid].get("documents") or [])]
    if tools["doc_links"]:   # the pairs sync_doc_links.py would sync: its held documents (catalogues, shared pages, dealer listings) are not gaps
        dl = tools["doc_links"]
        held = dl.holds_for(rel_by_id, docs)
        one_sided = sorted({p[1] for p in dl.pairs(rel_by_id, docs) if p[2] not in held})
    check("doc-not-back-linked", "run tools/sync_doc_links.py --write in hobbydex-tools (adds the missing side; catalogues, shared shop pages and dealer listings it holds are not gaps)",
          one_sided)

    # 24. never-link hosts and dealer doc references
    banned, scrap, local, dealer, foreign = [], [], [], [], []
    swaps = english_swaps(tools["english_table"]) if tools["english_table"] else None   # None: the table is not there
    if swaps is None:
        swaps = {}
    gone = gone_urls(tools["cache"], swaps)
    unavailable = english_unavailable(english_state(tools["cache"], swaps))
    for path in sorted({d["_path"] for k in db for d in db[k]}):
        with open(os.path.join(RC, path), encoding="utf-8") as f:
            text = f.read()
        if BANNED_HOSTS.search(TAMICO_DEALER_LINK.sub("", text)) and not path.startswith(TAMICO_OWNER_DOCS):
            banned.append(path)
        if tools["english_table"] and has_foreign_link(text, swaps, gone, unavailable):
            foreign.append(path)
        if SCRAP_IMG.search(text):
            scrap.append(path)
        if "doc/tamiya/tamico-dealer-parts" in text and not path.endswith("documents/tamiya/tamico-dealer-parts.toml"):   # the document itself is not a reference
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
    if tools["english_table"]:
        check("non-english-link", "switch the link to the maker's English address once the maker has it (tools/link_language_variants.py in hobbydex-tools; the hosts are in tools/english_variants.toml); a link the maker never translated is listed here until its host rule is narrowed (a link whose English address the crawl found gone, failed, answers with an error page, or names none of the record's item numbers is not listed)",
              [{"id": p} for p in foreign], count=len(foreign))
    else:
        results["non-english-link"] = {"fix": ENGLISH_MISSING, "count": None, "examples": [], "all": []}

    # 26d. spec links the part's category or name does not carry (spec_mismatches): a bearing on a clip, a motor on a rebuild kit
    mism = spec_mismatches(parts)
    check("spec-mismatch", "remove the spec link (or fix the part's category or name, then link the spec its name gives): the link's family is not the part's kind; see the linker in the rows' notes",
          sorted({m[0] for m in mism}), count=len({m[0] for m in mism}), rows=[{"id": i, "field": f, "spec": sp, "why": w} for i, f, sp, w in mism][:200])

    usa_tsv = os.path.join(args.tools, "cache", "notes", "tamiya", "tamiya-usa-spares.tsv")
    usa_rows = []
    if os.path.exists(usa_tsv):
        with open(usa_tsv, encoding="utf-8") as fh:
            usa_rows = [{"id": row["part"], "reason": row["reason"], "usa": row["usa_names"], "url": row["usa_urls"]}
                        for row in csv.DictReader(fh, delimiter="\t")]
    reviewed_usa = usa_spare_reviewed(os.path.join(RC, "data", "usa-spare-reviewed.toml"))   # checked by eye: leaves the class
    usa_rows = [r for r in usa_rows if (r["id"], r["url"]) not in reviewed_usa]
    check("tamiya-usa-spare-mismatch", "a Tamiya USA spare page that names another part (name or size differs) or several pages: check the two names in cache/notes/tamiya/tamiya-usa-spares.tsv and link by hand or leave unlinked; pairs checked by eye are in data/usa-spare-reviewed.toml",
          usa_rows, count=len(usa_rows))
    tsv = os.path.join(args.tools, "cache", "notes", "tamiya", "tamico-spares.tsv")
    conflicts = []
    if os.path.exists(tsv):
        with open(tsv, encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                if row["status"].startswith("conflict"):
                    conflicts.append({"id": row["part"]})
    check("tamico-pack-conflict", "no pack_qty from the dealers: the dealers' counts differ or the part's name states another count; set the count from the part's own source or leave it unset (tools/link_tamico_spares.py lists the rows)",
          conflicts, count=len(conflicts))

    # 29-38. hardware bags, names, release boxes and the /tmp inodes
    brand_of = lambda x: x.get("brand", "").split("/")[-1]
    per_brand = lambda items: collections.Counter(brand_of(x) for x in items).most_common()

    no_pack = [p for p in parts if p.get("category") in HW and "pack_qty" not in p and not p.get("includes") and sold_in_packs(p)]
    fillable = [p for p in no_pack if not count_unstated(p, brands)]
    unstated = [p for p in no_pack if count_unstated(p, brands)]
    check("hw-no-pack-count", "set pack_qty from the maker's listing (the count in the bag), or list the bag's specs in includes; only hardware sold in packs (sold_in_packs): a single item needs no count",
          fillable, per_brand=per_brand(fillable))
    check("hw-pack-count-unstated", "nothing to fill: the maker states only a minimum count or none (informational; pack_counts = false in the brand's data marks it)",
          unstated, per_brand=per_brand(unstated), info=True)

    # a Tamiya "Hex Head" screw is a hexagon head with a JIS cross recess (spec head hex), never a socket cap
    tamiya_hex = [p for p in parts if p.get("brand") == "brand/tamiya" and p.get("category") == "screw" and re.search(r"\bhex head\b", p.get("name", ""), re.I)
                  and any("socket-cap" in e.get("spec", "") for e in p.get("equivalent_to", []))]
    check("tamiya-hex-head-socket", "link the Tamiya hex head screw to its spec/screw/*-hex-jis* (head hex, JIS cross recess), not to a socket cap",
          tamiya_hex)

    # a hardware kit's pack_qty is the sum of its includes qty (hobbydex-tools packqty.from_includes)
    def kit_sum(p):
        """The sum of the includes qty of a hardware kit, or None when a row has no integer qty."""
        rows = p.get("includes") or []
        qtys = [r.get("qty") for r in rows]
        return sum(qtys) if rows and all(type(q) is int and q > 0 for q in qtys) else None
    kits_hw = [p for p in parts if p.get("category") in HW and p.get("includes")]
    no_qty = [p for p in kits_hw if kit_sum(p) is None and p.get("includes_qty") != "unstated"]   # unstated: the source lists the items without counts (schema includes_qty)
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
    # a gear's pack_qty that is its pitch (tools#590): the pitch belongs in pitch_dp, the count in the maker's listing
    pitch_count = [(p, gear_pitch_as_count(p)) for p in parts]
    pitch_count = [(p, why) for p, why in pitch_count if why]
    check("pack-qty-is-pitch", "the count is the pitch: set pack_qty from the maker's listing or the bag (the pitch stays in pitch_dp), or unset it; a gear set whose name carries a count is not read",
          [p for p, _ in pitch_count])
    results["pack-qty-is-pitch"]["examples"] = [{"id": f"{p['id']} ({why})", "url": url_for(p)} for p, why in pitch_count[:args.examples]]
    ns = tools.get("name_shop")
    shop = [p for p in parts if ns is not None and ns.has_shop_text(p.get("name", "") or "")]
    check("name-shop-text", "strip the shop's price, stock or button text from the name (tools/name_shop.py clean; the maker's name is what is left)",
          shop, per_brand=per_brand(shop))

    # names with German words left (German makers' manuals and listings, German dealers; tools/translate_de.py and its
    # glossary give them English on write): a word missing from the glossary, or a name no importer rewrote since
    gw = getattr(tools.get("translate_de"), "german_words", None)   # None: a tools checkout older than the check
    german_de = german_names(parts + rels, gw) if gw is not None else []
    check("name-german", "give the name English: the maker's English name for the number (its English page; Tamiya: "
          "tools/name_numbered_parts.py tamiya --apply), else the missing words in hobbydex-tools tools/glossary_de.toml "
          "and tools/translate_de.py --brand <brand> (the German stays as name_de); a German proper name goes in its keep_phrases",
          [x for x, _ in german_de], per_brand=per_brand([x for x, _ in german_de]))
    results["name-german"]["examples"] = [{"id": f"{x['id']} ({x.get('name')!r}: {', '.join(w)})", "url": url_for(x)}
                                          for x, w in german_de[:args.examples]]

    near = tools["near"] or near_local
    by_name = collections.defaultdict(list)   # (brand, name) of OCR-named parts -> parts
    for p in parts:
        if p.get("name_source") == "ocr" and p.get("number"):
            by_name[(brand_of(p), p["name"].strip().lower())].append(p)
    # pairs confirmed as two parts (data/confirmed-distinct.toml: each number printed in a manual) are not twins,
    # nor are pairs whose both numbers a maker text layer prints (the text-layer index, tools/ocr_numbers.py), nor
    # pairs whose both numbers are reviewed as two parts (data/reviewed-distinct.toml)
    confirmed = set()
    cd = os.path.join(RC, "data", "confirmed-distinct.toml")
    if os.path.exists(cd):
        with open(cd, "rb") as fh:
            confirmed = {frozenset(p["parts"]) for p in tomllib.load(fh).get("pair", [])}
    printed = text_layer_numbers(tools["text_layer"])
    reviewed = reviewed_distinct(os.path.join(RC, "data", "reviewed-distinct.toml"))   # both numbers reviewed: two parts
    twins = []
    for group in by_name.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if near(str(a["number"]), str(b["number"])) and frozenset((a["id"], b["id"])) not in confirmed \
                        and not printed_pair(a, b, printed) \
                        and not both_reviewed(a, b, reviewed):
                    twins.append((a, b))
    check("ocr-number-twins", "settle the number: the scan's digit may be misread (5/6, 3/8, 0/8, 1/7); check the maker's page and fold the wrong one into the right one",
          [x["id"] for pair in twins for x in pair], count=len(twins), per_brand=per_brand([a for a, _ in twins]))
    results["ocr-number-twins"]["examples"] = [{"id": f"{a['id']} ~ {b['id']}", "url": url_for(a)} for a, b in twins[:args.examples]]

    # a plug names its connector in equivalent_to (a connector-spec row); a lead lists its plugs in connectors
    wire = [p for p in parts if p.get("category") == "wire" and PLUG.search(p.get("name", "")) and not p.get("connectors")
            and not any(str(e.get("spec", "")).startswith("spec/connector/") for e in p.get("equivalent_to", []) if isinstance(e, dict))]
    check("wire-plug-no-connectors", "set connectors to the plugs the lead carries (from the name or the maker's page)", wire, per_brand=per_brand(wire))

    # servo plugs: a part whose name gives only Futaba (or a Futaba servo) linked to the JR plug, or only JR to Futaba
    def servo_plugs(p):
        eq = {str(e.get("spec", "")) for e in p.get("equivalent_to", []) if isinstance(e, dict)}
        names = set(p.get("connectors", [])) | ({p["connector"]} if isinstance(p.get("connector"), str) else set())
        return ({"JR"} if "spec/connector/servo-jr" in eq or "JR" in names else set()) | ({"Futaba"} if "spec/connector/servo-futaba" in eq or "Futaba" in names else set())
    def servo_named(p):
        n = p.get("name", "")
        fut = bool(re.search(r"futaba|\bJ[- ]?plug", n, re.I)) or (p.get("brand") == "brand/futaba" and p.get("category") == "servo")
        jr = bool(re.search(r"\bJR\b|hitec|universal", n, re.I))
        return "Futaba" if fut and not jr else "JR" if jr and not fut else None
    crossed = [p for p in parts if (want := servo_named(p)) and (got := servo_plugs(p)) and want not in got]
    check("servo-plug-crossed", "link the servo plug the name gives: Futaba (J, with the lip) or JR (bevelled corners); they mate but are two specs", crossed, per_brand=per_brand(crossed))

    bat = [p for p in parts if p.get("category") in ("battery", "esc") and not p.get("connector")]
    check("battery-esc-no-connector", "set connector to the plug the pack or ESC uses (from the maker's page or manual)", bat, per_brand=per_brand(bat))

    # a battery whose name states the JST-XH balance lead, and no balance_connector (tools/link_part_connectors.py --balance)
    bal_name = re.compile(r"\bbalanc\w*[^,;|()]{0,30}\bjst[- ]?xhr?\b|\bjst[- ]?xhr?\b[^,;|()]{0,30}\bbalanc\w*", re.I)
    bal = [p for p in parts if p.get("category") == "battery" and not p.get("balance_connector") and bal_name.search(p.get("name", ""))]
    check("battery-balance-name-no-connector", "set balance_connector = \"JST-XH\" when the maker states it (tools/link_part_connectors.py --balance)", bal, per_brand=per_brand(bal))
    # a battery accessory (tape, lid, clasp, cup, strap ...) or a device named with its battery is filed as battery by mistake (tools/classify_parts.py)
    acc = re.compile(r"\b(tapes?|lids?|clasp|cups?|straps?|holders?|trays?|covers?|clamps?|plates?|mounts?|boosters?)\b", re.I)
    bat_acc = [p for p in parts if p.get("category") == "battery" and acc.search(p.get("name", ""))
               and not re.search(r"lipo|li-?po|nimh|li-?ion|\bpack\b|\d{3,5} ?mah", p.get("name", ""), re.I)]
    check("battery-accessory-name", "set the category an accessory belongs to (tape, lid, clasp, cup, strap: chassis or body; a device with its battery: that device) (tools/classify_parts.py)", bat_acc, per_brand=per_brand(bat_acc))

    # Horizon-owned brands: parts with no maker link (tools/link_horizon_pages.py links the item's page; a part Horizon does not list stays unlinked)
    hz = [p for p in parts if p.get("brand") in horizon and not any(l.get("kind") not in ("dealer", "fan-site") for l in p.get("links", []))]
    hz_brands = collections.Counter(p["brand"].split("/")[-1] for p in hz)
    gone_items = horizon_gone_items(os.path.abspath(args.tools))
    hz_nopage = [p for p in hz if horizon_no_page(p, docs, gone_items)]
    hz_nopage_ids = {p["id"] for p in hz_nopage}
    hz = [p for p in hz if p["id"] not in hz_nopage_ids]
    hz_brands = collections.Counter(p["brand"].split("/")[-1] for p in hz)
    check("horizon-part-no-maker-link", "run tools/link_horizon_pages.py (queues the item's Horizon page first; a part Horizon lists nowhere stays unlinked)",
          hz, per_brand=hz_brands.most_common())
    check("horizon-part-no-maker-page", "no maker page exists: the part is named only by exploded views, parts lists or manuals, and its Horizon item page answers 404 (informational)",
          hz_nopage, count=len(hz_nopage), per_brand=collections.Counter(p["brand"].split("/")[-1] for p in hz_nopage).most_common(), info=True)

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

    # electronics fields the schema defines for a category: a field fewer than 5% of that category's parts carry (motor_type on motors: 0 of 2,533)
    ELEC_FIELDS = {
        "motor": "motor_type kv turns lipo_cells diameter_mm length_mm shaft_mm weight_g sensored mount_holes motor_connector waterproof scales",
        "esc": "motor_type bec_v bec_a motor_limit_t motor_limit_kv nimh_cells programming resistance_mohm lipo_cells current_a peak_current_a "
               "dimensions_mm weight_g sensored motor_connector receiver_connector waterproof scales",
        "servo": "connector size_class spline_teeth torque_kgcm speed_s voltage_range gear_material motor rotation_deg bearings bearing_kind "
                 "dead_band_us frequency_hz dimensions_mm weight_g waterproof scales",
        "battery": "chemistry cells capacity_mah nominal_v c_rating connector balance_connector case dimensions_mm weight_g scales",
    }
    by_cat = collections.defaultdict(list)
    for p in parts:
        by_cat[p.get("category")].append(p)
    rare = []   # (category, field, with, of)
    for cat, fields in ELEC_FIELDS.items():
        ps = by_cat.get(cat, [])
        for f in fields.split():
            n_with = sum(1 for p in ps if p.get(f) not in (None, "", []))
            if ps and 20 * n_with < len(ps):
                rare.append((cat, f, n_with, len(ps)))
    check("electronics-field-rare", "fill the field from the maker's own wording (product page, spec table or manual), per the schema's electronics rules; a field the maker does not state stays empty (one line per category and field below)",
          [], count=len(rare))
    results["electronics-field-rare"]["all"] = [f"{cat} {f}: {n} of {of} parts ({100 * n / of:.1f}%)" for cat, f, n, of in rare]
    results["electronics-field-rare"]["examples"] = []   # the rows are printed in full under the summary line

    # kits no release names, with a page of the maker's site that names the car (tools/parts_only_leads.py in hobbydex-tools writes the leads)
    leads_tsv = os.path.join(os.path.abspath(args.tools), "cache", "notes", "parts-only-leads.tsv")
    open_leads = set()
    if os.path.exists(leads_tsv):
        with open(leads_tsv, encoding="utf-8") as fh:
            for ln in list(fh)[1:]:
                kid = ln.split("\t", 1)[0]
                if kid in kits and not rels_of_kit.get(kid):
                    open_leads.add(kid)
    check("parts-only-lead", "a page of the maker's site names this car (cache/notes/parts-only-leads.tsv: kit, brand, url, why): have the brand's importer read the page and add the release, with its manual and parts list",
          sorted(open_leads))
    ranked = sorted((n for n in results if results[n]["count"] and not results[n].get("info")), key=lambda n: -results[n]["count"])
    info = [n for n in results if results[n]["count"] and results[n].get("info")]
    skipped = [n for n in results if results[n]["count"] is None]
    if args.list:
        res = results.get(args.list, {})
        kit_of = res.get("kit_of", {})
        for i in res.get("all", []):
            print(f"{i}\t{kit_of[i]}" if kit_of else i)
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
        if n == "electronics-field-rare":
            for row in r["all"]:
                print(f"{'':34} {'':>7}    {row}")
    for n in info:
        print(f"{n:34} {results[n]['count']:>7}  (informational) per brand: " + ", ".join(f"{b} {c}" for b, c in results[n]["per_brand"][:15]))
        print(f"{'':34} {'':>7}    fix: {results[n]['fix']}")
    for n in [n for n in results if results[n]["count"] == 0 and results[n].get("detail")]:
        print(f"{n:34} {'ok':>7}  {results[n]['detail']}")
    for n in skipped:
        print(f"{n:34} {'skipped':>7}  {results[n]['fix']}")
    if args.json:
        out = {n: {k: v for k, v in r.items() if k != "all"} | {"all": r.get("all", [])} for n, r in results.items()}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    os.nice(19)   # a run from a terminal yields the CPU to the owner's other work
    main()
