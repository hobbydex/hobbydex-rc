"""Per-host English addresses of maker links, read by tools/link_language_variants.py in hobbydex-tools
and by the audit (non-english-link).

how = "swap": the address prefix `from` becomes `to` (a home page counts as `from` with its slash).
how = "hreflang": the cached page's <link hreflang="en"> alternate is the English address.
how = "suffix": a manual named for its language (-fr, -de, _DE) takes the -en twin, switched only when that address is cached.
A host listed here has an English version; a link with none (or whose English page is gone) stays.
"""

HOSTS = [
    {"host": "rc.kyosho.com", "how": "swap", "from": "https://rc.kyosho.com/ja/", "to": "https://rc.kyosho.com/en/"},
    {"host": "www.kopropo.co.jp", "how": "swap", "from": "https://www.kopropo.co.jp/", "to": "https://www.kopropo.co.jp/en/"},
    {"host": "www.os-engines.co.jp", "how": "swap", "from": "https://www.os-engines.co.jp/", "to": "https://www.os-engines.co.jp/english/"},
    {"host": "d7z22c0gz59ng.cloudfront.net", "how": "swap", "from": "https://d7z22c0gz59ng.cloudfront.net/cms/japan/download/rcmanual/", "to": "https://www.tamiya.com/cms/english/rc/rcmanual/"},
    {"host": "tamico.de", "how": "hreflang"},
    {"host": "www.scaleart-shop.de", "how": "swap", "from": "https://www.scaleart-shop.de/products/", "to": "https://scaleart-shop.de/en-de/products/"},
    {"host": "www.rc-race-shop.de", "how": "hreflang"},
    {"host": "www.lrp.cc", "how": "swap", "from": "https://www.lrp.cc/de/produkt/", "to": "https://www.lrp.cc/en/product/"},
    {"host": "www.horizonhobby.com", "how": "suffix"},   # a -fr/-de/-DE manual switches to its -en twin when that file is cached
    {"host": "traxxas.com", "how": "suffix"},
]
