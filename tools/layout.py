"""Where an entity lives in data/, derived from its id. The single place that
knows the file layout: the validator checks against it, importers write with it.

    part/xray/362250      -> data/parts/xray/36/362250.toml
    release/xray/320020   -> data/releases/xray/320020.toml
    brand/xray            -> data/brands/xray.toml
    category/servo        -> data/categories/servo.toml
    standard/iso-4762     -> data/standards/iso-4762.toml
    company/horizon-hobby -> data/companies/horizon-hobby.toml

Kits and releases may have art: our own traced outline, one SVG per id.

    kit/tamiya/blitzer-beetle -> art/kits/tamiya/blitzer-beetle.svg
    release/tamiya/58502      -> art/releases/tamiya/58502.svg

Parts get a prefix directory (the first PART_PREFIX characters of the number,
upper-cased) so no directory holds more than a few hundred files. Upper-cased
so that numbers starting GE and Ge share one directory: a checkout on a
case-insensitive filesystem (macOS, Windows) cannot hold both GE/ and Ge/. The
file name keeps the number as written; two numbers of one brand may not differ
only in case (validate.py checks).

    part/gens-ace/Gens-EC5-P -> data/parts/gens-ace/GE/Gens-EC5-P.toml
"""
DIRS = {"brand": "brands", "kit": "kits", "release": "releases", "part": "parts",
        "spec": "specs", "doc": "documents", "shop": "shops", "category": "categories",
        "standard": "standards", "company": "companies"}
PART_PREFIX = 2
ART_KINDS = ("kit", "release")

def path_for(entity_id, root="data"):
    kind, _, rest = entity_id.partition("/")
    if kind not in DIRS:
        raise ValueError(f"unknown entity kind in id {entity_id!r}")
    if kind == "part":
        brand, _, number = rest.partition("/")
        if not brand or not number:
            raise ValueError(f"part id needs brand and number: {entity_id!r}")
        return f"{root}/{DIRS[kind]}/{brand}/{number[:PART_PREFIX].upper()}/{number}.toml"
    return f"{root}/{DIRS[kind]}/{rest}.toml"

def art_path(entity_id, root="art"):
    """The art file of a kit or release id (whether or not it exists)."""
    kind, _, rest = entity_id.partition("/")
    if kind not in ART_KINDS:
        raise ValueError(f"no art for entity kind in id {entity_id!r}")
    return f"{root}/{DIRS[kind]}/{rest}.svg"
