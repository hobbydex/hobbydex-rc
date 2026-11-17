"""Documents: one record per product page and per video, and the fields every document needs."""


def test_doc_has_url_or_page(ratchet):
    """A document names where it is: a url or a page (a document with neither cannot be checked or linked)."""
    ratchet("doc-no-url-or-page", """SELECT id AS record, 'no url and no page' AS problem FROM records
        WHERE kind = 'doc' AND json_extract(data, '$.url') IS NULL AND json_extract(data, '$.page') IS NULL""")


def test_product_page_url_unique(ratchet):
    """One product_page document per page: documents of kind product_page whose url is the same page (scheme, www.,
    trailing slash and fragment ignored) are one document that lists every release, kit and part it shows; merge them
    (the other ids in former_ids) and keep every field. Files listed on one downloads page share its url, so other
    kinds are not held to this."""
    ratchet("product-page-url-unique", """SELECT min(id) AS record,
        count(*) || ' product_page documents share the url ' || nurl || ': ' || group_concat(id, ', ') AS problem
        FROM docs WHERE kind = 'product_page' AND nurl IS NOT NULL GROUP BY nurl HAVING count(*) > 1""")


def test_video_id_unique(hard):
    """One document per YouTube video: two documents that point to the same video id are one document (merge them,
    the other id in former_ids, and keep every field)."""
    hard("""SELECT min(id) AS record, count(*) || ' documents are the video ' || video || ': ' || group_concat(id, ', ') AS problem
        FROM docs WHERE video IS NOT NULL AND kind = 'video' GROUP BY video HAVING count(*) > 1""")
