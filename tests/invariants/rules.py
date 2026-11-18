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
