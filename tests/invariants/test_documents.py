"""Documents: one record per product page and per video, and the fields every document needs."""
from rules import NON_ENGLISH, OWN_LANGUAGE_FILES, placeholder_title



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


def test_doc_placeholder_title(ratchet, db):
    """A document title is not only item numbers and does not repeat one ("Tamiya 43501 43501"): the importer's
    placeholder; the name comes from a maker page (title_source), or the number stays once."""
    rows = db.execute("""SELECT id, json_extract(data, '$.title') FROM records WHERE kind = 'doc'
        AND json_extract(data, '$.title') REGEXP '\\d'""")
    ratchet("doc-placeholder-title", [(d, f"title {t!r}") for d, t in rows if placeholder_title(t)])


def test_horizon_doc_no_page(ratchet):
    """A document of a Horizon Hobby brand names the maker page that lists it (page). A product_page or owner_report
    is itself the page, a video has none, and a catalog is a site-level record."""
    ratchet("horizon-doc-no-page", """SELECT d.id AS record, 'no page' AS problem FROM records d
        JOIN records b ON b.id = json_extract(d.data, '$.brand') AND b.kind = 'brand'
        WHERE d.kind = 'doc' AND json_extract(b.data, '$.owner') = 'company/horizon-hobby'
          AND NOT truthy(json_extract(d.data, '$.page'))
          AND coalesce(json_extract(d.data, '$.kind'), '') NOT IN ('product_page', 'owner_report', 'video', 'catalog')""")


def test_no_shorts_address(hard):
    """No YouTube Short enters the data (owner, 2026-11-18: "No short should enter our database"): no record names a
    youtube.com/shorts/ address (a video document's url, an announced_source or seen_by_source, any field). Whether a
    watch?v= video is a Short is decided by the tools (import_brand_videos.short_signal: the watch page, the channel's
    Shorts and long-form playlists), which never write one; length alone never makes a Short (decision 2026-10-28)."""
    hard("""SELECT id AS record, 'names a YouTube Shorts address' AS problem FROM records
        WHERE data LIKE '%youtube.com/shorts/%'""", name="video-shorts-url")


def test_video_has_date(hard):
    """Every video document has the date the video was published (from the channel page)."""
    hard("""SELECT id AS record, 'video with no date' AS problem FROM records WHERE kind = 'doc'
        AND json_extract(data, '$.kind') = 'video' AND NOT truthy(json_extract(data, '$.date'))""", name="video-no-date")


def test_title_language(ratchet):
    """A document title is English: one with Dutch, French, Spanish or German words is renamed from an English source
    copy (never translated on a guess). A maker's file in its own language (manual, setup sheet ...) keeps its
    printed name."""
    ratchet("title-language", f"""SELECT id AS record, 'title ' || json_extract(data, '$.title') AS problem
        FROM records WHERE kind = 'doc' AND coalesce(json_extract(data, '$.kind'), '') NOT IN {OWN_LANGUAGE_FILES!r}
          AND json_extract(data, '$.title') REGEXP '{NON_ENGLISH}'""")
