# hobbydex-rc

Open RC parts database: kits, releases, parts, generic hardware specs and the
relations between them, as plain TOML files reviewed through pull requests.

Status: early. The schema is a draft that grows with the data; see
`docs/schema.md`.

## Layout

```
data/
  brands/<brand>.toml
  kits/<brand>/<slug>.toml
  releases/<brand>/<number-or-slug>.toml   # includes generated `contains`
  parts/<brand>/<prefix>/<number>.toml     # prefix: first two characters of the number
  documents/<brand>/<slug>.toml            # manuals and parts lists used as sources
docs/        schema and conventions
tools/       layout (id -> path), validator and JSON export (Python 3.11+, no dependencies)
work/        local only, not committed: downloaded manuals, scratch notes
```

## Working with the data

```
python3 -I tools/validate.py
```

`tools/export.py` writes the JSON export the website is built from.

Parts and release contents are generated from manufacturer documents by
importers that are kept out of this repository; each generated row names its
source document, so it can be checked against the manufacturer's own parts
list.

## Principles

Facts, not copies: part numbers, names, dimensions and fitment with a source,
never manual pages, product text or images. No prices or stock.

## Why TOML

The records are TOML rather than YAML on purpose. TOML has no implicit typing:
a part number such as `0225039`, a version such as `1.10` or a brand called
`NO` stays the string it was written as, where YAML would silently turn it
into an integer, a float or a boolean, and a validator can't recover what was
lost. Mistakes fail at parse time instead of surviving as corrupted data.
That matters here because importers and agents write most of the records.
Python reads TOML without any dependency. The cost is that TOML is less
familiar than YAML for hand editing; most contributions are expected to come
through tools, and the validator catches the rest.

## License

- Data under `data/` is released under [CC0 1.0](data/LICENSE): public
  domain, no conditions. If you use it, a link back to hobbydex.com helps the
  project and the people who maintain it, and lets corrections find their way
  home.
- Code (`tools/`, workflows) is under the [MIT License](LICENSE).

Contributions are accepted under the same terms.
