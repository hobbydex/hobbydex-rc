"""Where an entity lives in data/, derived from its id. The single place that
knows the file layout: the validator checks against it, importers write with it.

    part/xray/362250      -> data/parts/xray/36/362250.toml
    release/xray/320020   -> data/releases/xray/320020.toml
    brand/xray            -> data/brands/xray.toml

Parts get a prefix directory (the first PART_PREFIX characters of the number)
so no directory holds more than a few hundred files.
"""
DIRS = {"brand": "brands", "kit": "kits", "release": "releases", "part": "parts",
        "spec": "specs", "doc": "documents", "shop": "shops"}
PART_PREFIX = 2

def path_for(entity_id, root="data"):
    kind, _, rest = entity_id.partition("/")
    if kind not in DIRS:
        raise ValueError(f"unknown entity kind in id {entity_id!r}")
    if kind == "part":
        brand, _, number = rest.partition("/")
        if not brand or not number:
            raise ValueError(f"part id needs brand and number: {entity_id!r}")
        return f"{root}/{DIRS[kind]}/{brand}/{number[:PART_PREFIX]}/{number}.toml"
    return f"{root}/{DIRS[kind]}/{rest}.toml"
