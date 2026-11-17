# Data invariants

`tests/invariants` holds the constraints a database would enforce on the data: one record per key (a product page,
a video), no entry twice in a record's list, references that resolve, fields that may not be empty. Each one is a
test; it passes when it finds no offending record.

```sh
python3 -m pip install pytest pytest-xdist     # once
python3 -m pytest tests/invariants -n auto      # on any checkout of this repository
```

The data tree is parsed once per run into an SQLite snapshot (`tests/invariants/snapshot.py`, about 30 s with four
processes); every test worker opens that file read-only, so each check is one query. `records(id, kind, path, data)`
holds every record file, `data` the record as JSON (`json_extract`, `json_each`); the tables `docs`, `links`,
`list_values` (the plain string lists) and `list_rows` (fits, contains and includes rows) are built from it with
their indexes. `norm_url(u)` compares pages without scheme, `www.`, fragment or trailing slash; `video_id(u)` gives
the YouTube id of a URL.

CI runs the suite on every push and pull request and once a day on main (`.github/workflows/invariants.yml`).

## Two kinds

- **hard** (`hard(sql)`): any offending record fails the run. Duplicates, broken references and missing required
  fields: the data holds none, and a change may not bring one in.
- **ratchet** (`ratchet(name, sql)`): a known gap (product pages still split per release, kits with no scale). Its
  count is kept in `tests/invariants/baseline.toml`; the run fails when the count is higher than the baseline. A
  change that fixes some lowers the baseline in the same change (`--update-baselines` writes the lower counts); the
  daily run lists the baselines that can go down. With `blocking=False` a higher count is a warning only (part-misc:
  importers still add parts no source categorises).

## Adding an invariant

A class of data bug we fix gets an invariant, so it cannot come back.

1. Write the query: it returns the offending rows as `record` (the record id) and `problem` (one line that says what
   is wrong). Join on indexed columns (`records.id`, `records.kind`, `records.path`, `docs.nurl`, `links.owner`,
   ...); never scan a table once per row. If the query needs a list the snapshot does not have yet, add it to
   `TABLES` in snapshot.py with its index.
2. Add a test function to the file of its entity (`test_documents.py`, `test_lists.py`, `test_records.py`), its
   docstring the one-line rule that the failure prints:

   ```python
   def test_doc_has_kind(hard):
       """Every document has a kind."""
       hard("""SELECT id AS record, 'no kind' AS problem FROM records
           WHERE kind = 'doc' AND json_extract(data, '$.kind') IS NULL""")
   ```

3. Run it. No hit: keep it hard. Hits that the same change cannot fix: make it a ratchet and put its count in
   baseline.toml.

Budget: the whole run takes about a minute on the full tree; it warns over 120 s and fails over 300 s.
`--durations=5` names the slow tests.
