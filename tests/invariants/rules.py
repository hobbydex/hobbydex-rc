"""The word rules and small helpers the invariants share: data-shape rules (what a name, title or date may look like),
nothing about fetching. Each pattern says which invariant reads it."""
import re

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

