# hobbydex-rc

Open RC parts database: kits, releases, parts, generic hardware specs and the
relations between them, as plain TOML files. The data is maintained by the
Hobbydex project itself, not crowdsourced: see [CONTRIBUTING.md](CONTRIBUTING.md).

Status: early. The schema is a draft that grows with the data; see
`docs/schema.md`.

## Layout

```
data/
  brands/<brand>.toml
  kits/<brand>/<slug>.toml
  releases/<brand>/<number-or-slug>.toml   # includes generated `contains`
  parts/<brand>/<prefix>/<number>.toml     # prefix: first two characters of the number, upper-cased
  documents/<brand>/<slug>.toml            # manuals and parts lists used as sources
art/
  kits/<brand>/<slug>.svg                  # outline of a kit
  releases/<brand>/<number-or-slug>.svg    # outline of one release, when it differs from its kit
docs/        schema and conventions
tools/       layout (id -> path), validator and JSON export (Python 3.11+, no dependencies)
work/        local only, not committed: downloaded manuals, scratch notes
```

## Working with the data

```
python3 -I tools/validate.py
```

`tools/export.py` writes the JSON export the website is built from.
`tools/audit.py` lists what is still missing (parts named only by number,
OCR-read names, screws and bearings without a spec link, kits without
scale or power), per brand; `--list <check>` prints the entities, a
to-do list.

Parts and release contents are generated from manufacturer documents by
importers that are kept out of this repository; each generated row names its
source document, so it can be checked against the manufacturer's own parts
list.

## Art

`art/` holds our own outlines of kits and releases, traced from the maker's
photos into a flat silhouette: one path on a 48x24 canvas, front of the car
to the left, no colour. The site fills it in the release's colours (or the
page's text colour), so the same file serves light and dark mode. The
validator checks the format and that every file belongs to a kit or release.

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
familiar than YAML for hand editing; the records come through tools, and
the validator catches the rest.

## Thanks

The records are read from manufacturers' manuals, parts lists and product
pages by importers built on open source. Thank you to the people behind:

- [Python](https://www.python.org) - the validator, the export and every importer (TOML is read with the standard library)
- [Tesseract](https://github.com/tesseract-ocr/tesseract) - reading scanned manuals and parts cards, in English and Japanese
- [Poppler](https://poppler.freedesktop.org) - pdftotext, pdftoppm, pdftohtml and pdfinfo, which turn manuals into text and page images
- [Pillow](https://python-pillow.org) and [NumPy](https://numpy.org) - cropping and measuring scanned pages
- [ImageMagick](https://imagemagick.org) - image conversion
- [SQLite](https://sqlite.org) - the queue that keeps every site's requests slow and polite

The website is thanked separately in [hobbydex](https://github.com/hobbydex/hobbydex#thanks).

## License

- Data under `data/` is released under [CC0 1.0](data/LICENSE): public
  domain, no conditions. If you use it, a link back to hobbydex.com helps the
  project and the people who maintain it, and lets corrections find their way
  home.
- Code (`tools/`, workflows) is under the [MIT License](LICENSE).

The data stays open source. The project writes every record itself (no
direct modifications from outside), so each record keeps a clear
attribution path: written by the project from a named manufacturer
source.
