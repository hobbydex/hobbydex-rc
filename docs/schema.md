# Data schema (v0, draft)

One TOML file per entity under `data/`. IDs are `<kind>/<brand>/<key>` and are
the identity; the file path is derived from the id by `tools/layout.py`, the
only place that knows the layout. The validator in `tools/validate.py`
enforces placement, required fields, references and enums. Consumers never
read the tree directly; they read the export (`tools/export.py`).

| Kind | Path | Required |
|---|---|---|
| brand | `data/brands/<brand>.toml` | id, name, status |
| kit | `data/kits/<brand>/<slug>.toml` | id, brand, name, category |
| release | `data/releases/<brand>/<number-or-slug>.toml` | id, kit, brand, name, status (`kind` and `year` optional: left out when no source states them) |
| part | `data/parts/<brand>/<prefix>/<number>.toml` | id, brand, number (unless the brand has `item_numbers = false`), name |
| doc | `data/documents/<brand>/<slug>.toml` | id, kind, title |
| spec | `data/specs/<category>/<slug>.toml` | id, category |
| category | `data/categories/<slug>.toml` | id, name |
| shop | `data/shops/<country>/<slug>.toml` | id, name, status (not used yet) |
| company | `data/companies/<slug>.toml` | id, name |
| make | `data/makes/<slug>.toml` | id, name, country, notes |

`<prefix>` is the first two characters of the part number, upper-cased
(`part/gens-ace/Gens-EC5-P` -> `data/parts/gens-ace/GE/Gens-EC5-P.toml`), so
that no directory holds more than a few hundred files (GitHub lists at most
1000). The file name keeps the number as written. No two paths may differ only
in case: a checkout on a case-insensitive filesystem (macOS, Windows) cannot
hold both, so `Ge/` next to `GE/` is not allowed, and neither are two part
numbers of one brand that differ only in case (`SG-M3x8` and `SG-M3X8` are one
part: keep one spelling and list the other id in `former_ids`). validate.py
checks both. Changing the layout later means editing `layout.py` and moving
files; ids do not change.


## Ids are permanent

Every record's `id` is also its address: the site builds the page URL from
it (`part/traxxas/6890` -> hobbydex.com/rc/parts/traxxas/6890/), and people,
forums and search engines link to those pages. So:

- An id is never reused for something else.
- When a record's id has to change (a renamed kit slug, a part number
  corrected after an OCR misread, two records merged), the record keeps the
  old id in `former_ids = ["part/tamiya/19805186"]`. The site serves a
  redirect at every former id.
- A record removed with no successor (a misread number that was never a real
  part) goes in data/retired.toml with a `reason` and, when there is one, a
  `replaced_by`.

A kit or release that changes id takes its art file along (art/ follows the
id, see "Art" below); the validator reports art left at the old name as an
orphan.

The validator rejects a former or retired id that is live again or claimed
twice, and CI runs tools/check_ids.py, which fails a change that drops an id
without either trace.

## brand

```toml
id = "brand/xray"
name = "XRAY"
legal_name = "XRAY Model Racing Cars"   # optional
country = "SK"                           # ISO 3166-1 alpha-2
website = "https://www.teamxray.com"
website_fallback = "https://www.rochobbies.com"   # optional: a second site of the maker, used when the first has no page for a part
youtube = ["https://www.youtube.com/@XRAYracing"]   # optional: the maker's official channels, its own first
kind = "manufacturer"                    # manufacturer | aftermarket | designer | retailer
status = "active"                        # active | dormant | gone
launched = "1993"                        # optional: when the brand launched, ISO date at the source's precision
launched_source = "https://..."          # required with launched: the page URL or doc/ id that states it
ended = "2016-06"                        # only for a gone brand: when it stopped
ended_source = "https://..."             # required with ended
notes = "..."
```

`website_fallback` (optional): a second web address of the maker, used for product links only when `website` has no page for the part (ROC Hobby: fmshobby.com first, rochobbies.com as fallback). Its pages link only where a structured product SKU names the part (tools/link_maker_pages.py, mode structured).

`youtube`: a list of the maker's YouTube channels as `https://www.youtube.com/@<handle>`, the brand's own channel first. Only official channels, the ones the maker's own site links (home page, footer, about page); never a fan's, a shop's or a racer's channel. A channel shared by a parent company (Horizon Hobby's, for ARRMA, Axial, Losi...) follows the brand's own. Filled by tools/link_brand_youtube.py.

A date we keep but doubt gets `<field>_doubt` next to it, a short reason (`launched_doubt = "uncited on Wikipedia"`, `released_doubt = "year from the catalogue edition"`): for `launched` and `ended` on a brand, `released`, `year` and `announced` on a release. The site marks such a date with "?" and shows the reason. Not for `seen_by`, which is a bound, not a claim.

`launched` and `ended`: when the brand started and when it died, as ISO date strings at the precision the source gives ("2016", "2016-06", "2016-06-01"), each with `<field>_source` (the URL of the page, or the `doc/` id of the document, that states it). Never guessed from the oldest or newest product. `ended` goes with status `gone` and is required for it. Every release and part of a gone brand has status `discontinued`.

`owner`: the company that owns the brand, a `company/` id, set only when a
page of the brand (about, imprint, footer, copyright line, "a division of")
or of the owning company states it. `owner_source` is that page's URL, or the
`doc/` id of a document of the brand that states it (a manual's "ARRMA ...
are trademarks or registered trademarks of Horizon Hobby, LLC"); it is
required with `owner`. `owner_since` (a year) only when a source states it.
Only a company with an identity of its own gets a record: a group,
distributor or retailer that owns the brand, or the maker of several brands
here. A maker that is its own company (Kyosho, Tamiya), or whose legal entity
owns nothing else (RC4WD's MNA, Inc.), gets no owner: its `legal_name` says
it. `legal_name` stays the legal entity as the brand's own site writes it.

```toml
owner = "company/horizon-hobby"
owner_source = "doc/arrma/ara2304-manual-ml"
```

`item_numbers = false` marks a maker that prints no item numbers (Acer
Racing): its parts leave out `number`, and the id's last segment is a slug
from the source (the store's product handle) instead. The site then shows no
number and builds the part URL from that slug. Left out, it means true and
every part of the brand needs a `number`.

## company

A company that owns one or more brands. It is not a brand itself: it has no
kits or parts of its own; its brands point at it with `owner`, and the site
lists them as sister brands. One record per owning company, so several brands
share it.

```toml
id = "company/horizon-hobby"
name = "Horizon Hobby"
legal_name = "Horizon Hobby, LLC"      # optional
country = "US"                         # ISO 3166-1 alpha-2
website = "https://www.horizonhobby.com"
status = "active"                      # optional: active | dormant | gone
brand = "brand/..."                    # optional: the brand that carries the company's own range (company/associated-electrics: brand/team-associated)
parent = "company/..."                 # optional: the company that owns this one, with a source in notes
notes = "..."
```

## kit

A model line, independent of year or edition. `category` is the kit type:
buggy | truggy | stadium-truck | short-course | monster | desert-truck |
truck | tractor-truck | race-truck | crawler | touring | gt | on-road | formula | pan-car | rally |
street-basher | drift | drag | lowrider | oval | speed-run | kart | motorcycle |
tank | construction | trailer | boat, or car for a car that fits none of
them. gt is a GT-body racing car on a buggy-style chassis (1/8 GT class).
on-road is an on-road racer with independent suspension that is not a touring
car (1/8 nitro or electric on-road). Scale is never in the type name; it is
its own field. trailer is a standalone trailer or dolly, with no `drive` or `power`
(a rigid truck sold with its trailer stays truck). tractor-truck is a semi tractor unit (Sattelzugmaschine, tractor unit or tractor truck by the maker's name, or a hauler with a fifth wheel and no body, such as Tamiya's hauler series), with or without a trailer it is sold with (Arocs Sattelzug mit Kippauflieger); rigid bodies (tippers, dump trucks, hook lifts, cranes, Unimog) are truck. Race trucks stay race-truck. drag is a straight-line drag
racer (no prep drag cars, drag trucks); lowrider a
hopping lowrider on hydraulics or servo-lifted suspension. `scale` as "1/10". `name` does not repeat the brand: the site prints the brand in front, so "Hosim 16207 RTR" is stored as "16207 RTR" (validate.py checks it).
`drive`: 2wd | 4wd | 6wd | 8wd (driven wheels), fwd (front-wheel drive) or
tracks for a tracked vehicle (tanks, tracked excavators, dozers and loaders,
tracked conversions sold as their own kit). A half-track (tracks at the rear,
skis or wheels in front) is tracks too, with a short note in `notes`. Track
conversion sets for a wheeled car stay parts and do not change the kit.

```toml
id = "kit/xray/xb2"
brand = "brand/xray"
name = "XB2"
category = "buggy"
scale = "1/10"
drive = "2wd"        # 2wd | 4wd | 6wd | 8wd | fwd | tracks
power = "electric"   # electric | nitro | petrol
```

`power` is left out on a kit sold both ways: when its releases include both electric and nitro or gas ones (HPI WR8, Savage X, Baja 5B), each release shows its own power and the kit shows none.

Optional on a kit: `rebrand_of`, the kits this one is the same car as under
another name, and `same_platform_as`, kits that share a chassis platform without
being the same car. Each entry names the kit, `parts` (interchangeable |
partly | unknown) and a `source` document or `notes` saying where the claim
comes from. The relation is recorded once, on the rebranded kit; the site
shows it from both sides.

```toml
rebrand_of = [
  { kit = "kit/ftx/vantage", parts = "interchangeable", notes = "Same car sold by HobbyKing under its Quanum brand" },
]
```

`supersedes` (optional, on the newer kit): the kit this platform replaces, a kit id of the same brand, one predecessor per kit. Two sources: the maker says so (cited in `notes`), or the kits are numbered generations of one line with the same category, scale and drive: `<line><n>` is replaced by the next number of that line that exists (BD7 -> BD8; BD5 -> BD7 when there is no BD6). Variant suffixes (BD10LC, TA07 PRO) are a line of their own and take no link. Numbers that are model codes rather than generations take none. The releases stay on the kit they were sold for; the site shows "Replaces" and "Replaced by" on the platform page.

```toml
supersedes = "kit/yokomo/bd7"
```

A model the maker publishes with its own manual and parts list is its own
platform: its own kit file, linked to the platform it follows with
`same_platform_as` and, on the newer release, `supersedes`. The same chassis
in another box (RTR or kit, colour, limited edition, team kit or factory-lite
trim) is a release of that platform, not a kit of its own.

## release

One sold product: a yearly edition, a Carpet or Dirt version, an RTR, a
re-release. Keyed by manufacturer item number when there is one, otherwise by a
slug (`xb4-2013`, `xb8e-2021`). `status` is
announced | released | discontinued. `name` does not repeat the brand: the site prints the brand in front, so "Hosim 16207 RTR" is stored as "16207 RTR" (validate.py checks it).

`kind` (optional: left out when no source states the build) is the build the buyer gets, one of kit | rtr | arr | roller | print:

- `kit`: built by the buyer; the electronics are usually bought separately.
- `rtr` (ready to run): built and complete, radio included, often battery and charger.
- `arr` (almost ready to run): built, without radio and sometimes without battery. PNP (plug and play) is `arr`.
- `roller`: a built chassis without electronics (and usually without body), as some makers sell it (Axial, Element, Losi, Team Associated "roller" or "rolling chassis").
- `print` (3D print): the maker sells files you print yourself (a printable set, 3D Sets); the buyer supplies the printer, and the electronics, screws and tyres are usually bought separately. A hardware set sold for a printed car stays its own part or release.

tools/validate.py rejects any other value.

`power` (optional: left out when nothing states it) is the power system the buyer gets with the release: brushed | brushless | nitro | gas | none. Electric releases are brushed or brushless by the motor in the box (an RTR, or a kit or roller that includes its motor); nitro is a glow-plug engine, gas a petrol engine, none a release sold without motor or engine (a roller). A kit sold without its motor has no `power` unless the maker's name says which system it is built for or its kit is a nitro or petrol car (the engine class is the car's). `power_source` (required with `power`, and only with it) names what states it: the id of a motor, ESC or engine part among the release's `contains` rows with role kit (`part/hpi/161065`, from its `motor_type`, `fuel` or `engine_class`); the id of a document of the release whose title says brushed or brushless (HPI's "Flux ... RTR setup" sheet); `name` for the maker's own wording in the release name ("Brushless", "VXL", "BLX", "Flux", "Nitro", "Gas"); `kit` when the kit's `power` is nitro (nitro) or petrol (gas); `kind` for a roller (power none); `curated` for a value set by hand, which tools/link_release_power.py never changes. Where two releases differ only by power system the names stay as the maker has them; the site prints the system next to the kind. Set by tools/link_release_power.py; tools/validate.py checks the values.

```toml
power = "brushless"
power_source = "part/hpi/161065"
```

`color` (optional) is the colour the release is sold in, in plain words from the same palette as a part's `color` ("red"; two or three colours as "blue/black", "green/black/white"), read from the name's colour clause by link_release_colours.py; left out when the name names none. `color_source = "owner"` marks a colour the name does not give and the owner states (the owner's word for a release whose name and page name no colour); it needs `color` and is never set on a colour read from the name.

`range` (optional) groups the versions of one car that differ only in colour or livery, as it does for a part's colour versions: releases sharing a range have the same brand, kit and kind, and the range is `<brand slug>/<slug>-colours`, e.g. "hpi/vectr4-ford-escort-rs-cosworth-colours" on HPI 161300 and 161301. The site treats them as colourways (one row on the home page, a switch on each release page) even where the item numbers carry no colour code. Set by tools/link_release_ranges.py, only where the names are equal up to a short colour or livery clause and the item numbers are close; at least two releases hold a range. `livery` (optional, only with a `range`) is the livery or variant name that sets a version apart ("Rally Sanremo", "Warsteiner"), as the name states it; the site prints it as a text label next to the swatch, or alone where no `color` is known. `color` is set from the clause when it names a colour ("Imperial Blue" -> "blue"), never from a livery.

`scale` (optional) overrides the kit's scale for this release, in the kit's "1/10" format. Set only where the release's scale differs from its kit's and a source states it (Tamiya's CW-01 Lunch Box is 1/12 while the 1/10 Montero Wheelie and Unimog sit on the same chassis); the release's own product page or manual title is the source, and the release notes say which (for Tamiya's Tamtech and Quick Drive series, TamiyaBase's model page gives the scale and the notes say so). Left out when it matches the kit.

```toml
scale = "1/12"
```

`series` (optional): the maker's car line that runs across chassis and editions, as a string ("Lunch Box": the CW-01 and SW-01 Lunch Box, its Evo. and Red, Gold and Blue editions). Set only when the maker's own release names show the same car (the series name appears in the names) on more than one platform, never for a generic word. Releases of one brand with the same `series` form the group; the site links them from each release ("Lunch Box series") and from the platform page.

```toml
series = "Lunch Box"
```

`category` (optional) overrides the kit's type for this release, where a car on a shared chassis is another type than the chassis kit: Tamiya's race trucks are releases of the TT-01 Type-E kit (a touring car) with category "race-truck". race-truck is the on-road racing semi truck (tractor-unit body, Tamiya TT-01 race trucks); an off-road "race truck" or "TT" by name is a truggy.

`year` is the calendar year the release came out, only from a dated source. `model_year` is the year in the maker's edition name when the maker names editions by model year (XRAY's XB2'26 is on sale from late 2025): it is not a release year, and a release can be on sale before its model year.

`requires` (a release that is not a car on its own: a conversion or upgrade kit): the cars it needs, as kit or release ids, any one of which completes it, from the maker's wording ("a 1RC Racing 1/18 Sprint Car (1RC1095, 1RC1096 or 1RC1097) is required"). A release id when the maker names item numbers, else the kit. The site shows "Needs" on the release and, on the base kit and release, the conversion kits made for it.

`surface` (race kits only): the track surface the maker built this version for, as a list of carpet | astro | clay | dirt | asphalt | high-grip, when the maker sells surface-specific versions or says what the car is for ("Carpet Edition", "for clay tracks"). Set only from the maker's own wording, never guessed from the car type; on a kit when the whole line is for one surface.

`depicts` (optional): the real vehicle the release depicts, for scale replicas of real makes (Tamiya's Porsche 911, Traxxas's TRX-4 Ford Bronco, ScaleArt's Mercedes-Benz Arocs). `model` is required. `make` is one of the curated makes in tools/validate.py `VEHICLE_MAKES` (add a make there first), spelled as the make spells itself, and may be left out when several makers built the vehicle (Tamiya's M4 Sherman, KV-1 and Centurion tanks: `depicts = { model = "M4 Sherman" }`); aliases are folded into it ("VW" is Volkswagen, "Chevy" Chevrolet, "Mercedes-AMG GT3" is Mercedes-Benz "AMG GT3"). `model` is the model as the RC maker names it, lightly normalised (no chassis code, colour, race number, kit or RTR wording, and no trailing RC, except where RC is the model's own name as in Toyota's Celica GT-Four RC). The model names the car, so sponsor, driver, team and event names are dropped ("Impreza WRX STI Team Arai" is "Impreza WRX STI", "Impreza WRC Monte Carlo" is "Impreza WRC"). Racing classes and tuners stay ("WRX STI GRC", "Ballade Sports Mugen CR-X PRO", "Zakspeed Capri Turbo"), as do the car's version words (GT3, Evo, R32, Type R, AMG, NISMO, Abarth, Rally), Mini's edition "Cooper Monte-Carlo", and a word that is unclear. A model that only dropped words would leave empty is kept for a decision by hand. Make is not changed ("Abarth" stays under Fiat). `year` only when the name states it ("1979 Ford Bronco"), never a re-release year. `licensed = true` only where the RC maker says so itself: a trademark sign on the make or model in its own product name, or "licensed model" on its page; left out otherwise, which does not mean unlicensed. Names only: no logos. Read from release names by link_vehicles; fictional cars (Tamiya's Clod Buster, Lunch Box, Hornet) have none.

```toml
depicts = { make = "Porsche", model = "911 Carrera RSR 2.8", year = 1973 }
```

The same field is allowed on a body shell (a part of category `body`) whose name names a real car ("Toyota Alphard MK1 Body"), never on body posts, mounts, decals or other body parts. It is not a part's `vehicle`, which is the vehicle type a tyre or wheel is for.

`documents` lists the docs that describe this release. `contains` lists the
parts the release's documents associate with it. It is generated by an importer
from the documents it names and should not be edited by hand while the importer
owns it.

```toml
contains = [
  { part = "part/xray/303122", role = "kit", source = "doc/xray/xb2-2026-part-list" },
]
```

`role`:

- `kit`: ticked for this edition in the manufacturer's parts list, so it is in the box.
- `option`: listed as an option or upgrade for this release.
- `listed`: appears in the release's parts list without a kit or option mark
  (tools, consumables, related products, or lists that have no such marks).

Rows read from a build manual also carry `qty`, the number of pieces the car
uses (summed over the steps that use the part), and `step`, the manual's
reference ("Bag 4 - Step 2"). Rows read from a parts list have neither.

`needs` (optional) lists what a buyer must get separately to complete the release: paints for a Tamiya kit, the radio, servo, ESC, motor, battery, charger, pinion, tyres or body for another maker's kit. It is not `contains` (what is in the box) and not `requires` (another kit or release this one needs). Each entry has exactly one of `part` (an existing part id, when the item is a part the data holds) or `item` (a generic word from the fixed list: radio, receiver, servo, esc, motor, engine, battery, charger, pinion, tyres, wheels, body, paint, glue, fuel, glow-starter, tools), plus `source` (the doc that names the need, from the maker's wording) and optionally `qty` (an int of 1 or more, when more than one is needed) and `note` (a short string).

```toml
needs = [
  { part = "part/tamiya/85001", source = "doc/tamiya/58661-product-page" },
  { item = "radio", source = "doc/kyosho/xxx", qty = 1 },
]
```

`year` is the year the release came out. Leave it out when it is unknown: a
document's date (a later scan, a reprinted manual) or the day a shop was read
is not a release year. The site shows such releases as year unknown and leaves
them out of the by-date lists.

`supersedes` (optional, on the newer release): the release this one replaces, a release id. Two sources. A yearly edition of one kit whose name differs from the previous one only by the year marker and keeps the same variant (XRAY's XB8'22 -> XB8'23, X4'24 Alu Flex -> X4'25 Alu Flex, XB4C'25 -> XB4C'26) takes the directly previous year of that variant, or the nearest earlier one when a year is missing; EU and US twins of one year are not successors of each other, and releases that are different bodies or editions of one kit (Tamiya's TT-02 bodies) take none. A version marker works the same way, within one kit: names that differ only by a version marker and keep the same variant (SO1.0 -> SO2.0 -> SO3.0, YZ-2 DTM -> DTM2 -> DTM3, YZ-2 CAL2 -> CAL3 -> CAL3.1, DEX410R -> DEX410Rv3). A marker is a decimal (3.1), V<n>, Ver.<n>, Mk <roman> or Gen <n>, or a number glued to a line of two or more letters (DTM2, TKI3); a name without one is version 1. Evo, Pro, SE and R are variants, not versions, and a letter after the item number (SOR-020D, SOR-030LM) is a variant too: a release takes a predecessor only of its own variant. A -1 revision is neither: releases of one version are not linked to each other. The predecessor is the nearest lower version, and it is left unlinked when two releases share that version or the newer one is dated before it. The other source is the maker saying so: "Replaced by" on its product page, cited in `notes` with the page's prod_id. One predecessor per release. The site shows "Replaced by" on the older release and "Replaces" on the newer one. The maker's statement can also join releases of different kits (XRAY's T1 -> T1 EVO2).

```toml
supersedes = "release/xray/xb8-2022"
```

`related` (optional): links from a release to another release of the same brand, one row per link: `{ release, relation, source }`. The only relation so far is `rerelease-of`: the release is a re-release of the original (its first release), and `release` names that original, never a previous re-release of it (Tamiya's Grasshopper 58346 of 2005 and 47522 of 2025 both point to 58043 of 1984). Set only where the maker says so (its product page: "re-released and updated version of X, the original of which was first released in 1987"), else where TamiyaBase's model page names the original; a same name on the same kit alone counts only when it is unambiguous, with `source = "same name and platform"`. `source` names that page: a document id (`doc/tamiya/58742-product-page`) or the URL. The original must be the same brand and older (its date is earlier than the re-release's `released` or `year`). A colour or body variant that TamiyaBase lists as a reissue of a kit is linked too; factory-built RTR versions of a kit (TamiyaBase's 23xxx numbers) are not re-releases and take no link. The site shows "Re-release of <original> (<year>)" on the re-release and "Re-released as" on the original.

```toml
related = [{ release = "release/tamiya/58043", relation = "rerelease-of", source = "https://www.tamiyabase.com/tamiya-models/58346" }]
```

`released`: the release date as precise as a source states it, `YYYY-MM-DD`
or `YYYY-MM` (Tamiya's monthly new-items list gives the month; a full date
from another source in that month is kept). It must agree with `year`. Never
a document's date (a parts list's revision); the exception is a maker's
`news` post that announces the item as new or available (see doc). For
an announced release it is the planned date.

A manual's printed date is never `released`: a print month from a manual (Traxxas R00 code, Horizon "Created MM/YY") or a copyright year becomes `seen_by` (below). Traxxas owner's manuals print a code `YYMMDD <doc>-R00` (R00 is the first print; a later revision is a reprint and is never used); Horizon brands' manuals print `Created MM/YY`. The bound's `notes` line names the code or stamp. A print can precede the announcement, so an `announced` date keeps its place and the print month goes in `notes` only.

`released_source`: set only when the date comes from a fan site rather than
the maker; `"TamiyaBase"` for a Tamiya release dated from TamiyaBase (its
owner allowed it) when Tamiya's own pages give no first-release day, with the
model's TamiyaBase link in `links` (kind `fan-site`). The maker's own date
wins when both exist.

`announced` (optional, `YYYY`, `YYYY-MM` or `YYYY-MM-DD`, at the precision the source gives): the day the maker announced the release: its news, press or new-product page, or the earliest video the brand posts that shows the product (any video type; a video showing a model without colour applies to that model's releases). `announced_source` is required with `announced` and never without it: the https URL that day comes from, the maker's news or press post, product page or video, or a Big Squid RC post when no maker page gives the day (`links` then carries it as kind `press`, a courtesy link and the source of that day only, never of `released`). The maker's page is also among the release's documents. Precedence everywhere: `released` or `year` (a date a source states as the release), then `announced`, then `seen_by`. An announced date is not after `released` when both exist. An announced day is never after the release's `seen_by` bound (the car was on sale by then): a source dated later than the bound is not the announcement (audit `announced-after-seen-by`). The site shows an announced-only release as "announced Mar 2019" with no asterisk, and names the source next to it.

`announced_source` (with `announced`): the https URL of the page or video the day comes from, a maker's video (`https://www.youtube.com/watch?v=<id>`) or announcement page; the video is also among the release's documents. Set with every `announced` a maker source gives; the validator checks the form only.

`seen_by` (optional, `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; the importer writes `YYYY-MM`) is an upper bound for a release no source dates: the first Internet Archive capture of a maker page or file that names exactly this release (its item number in the URL, or its own product page). The release was on sale no later than that month. The maker's own page that names the release also gives it, when we saw that page on the maker's site before the capture: the earlier of the two counts, so `seen_by` is the month of whichever is earlier. It is not a release date: never set it on a release that has `released`, `year` or `announced`, and the site marks it as not the release date. The importer only sets it on releases with no date; when a real date (released, year or announced) is found later, `seen_by` and `seen_by_source` are removed in the same change, and the site shows the real date whenever one exists.

A capture of any page that shows the item (its number is on the page, a listing or a related-products block included) gives `seen_by` at the capture day: the earliest such capture wins, and a later date is never written over an earlier one (decisions, 2026-10-28).

`seen_by_source` (with `seen_by`, and only with it): the capture the month comes from, `https://web.archive.org/web/<14-digit timestamp>/<original URL>`; or, when the bound is the day a maker's own video from its channel's first 60 days was uploaded (back catalogue, not a launch), the video's `https://www.youtube.com/watch?v=<id>`; or, when the month is the day the maker's own Shopify shop published the product (its products.json `published_at`), the maker's product page `https://<host>/products/<handle>`; or, when the month is the earliest customer review on the maker's own product page (the review's JSON-LD datePublished: a review proves the product was on sale that day), the product page `https://<host>/products/<handle>`; or, when the month is the day we first saw the maker's own page that names the release (one of its links without kind, sources, the url of a product-page document or non-catalogue document pages), that page's https URL; or, when the bound is a manual's printed date (a copyright line, a print code, a Created stamp), the maker's page or file for that release's own manual, the `page` or `url` of the manual document in the release's `documents`. Or, when the bound is a printed year of a catalogue or manual document (no page or url of its own), the document's id `doc/...`, a `catalog` or `manual` document with `printed` = its printed year; the part's `seen_by` year is that year. or, when the bound is the `<lastmod>` day of the maker's product sitemap that lists the record's own page exactly (its link, source, product page or document page), that sitemap's https URL (`https://<host>/....xml`, a host of the brand or of the record's links; `seen_by` then carries the day, `YYYY-MM-DD`). Set both or neither, never together with `released` or `year`.

A manual's date is an on-sale bound, not a release year (decisions.md, 2026-10-20). A copyright year gives `seen_by` at year precision, a print month (Traxxas R00 code, Horizon "Created MM/YY") at month precision, and the release's `notes` say where it came from ("on sale by: the manual's copyright line (c) 2023"). The earliest bound wins: an earlier Wayback capture or shop date replaces a later `seen_by`, never the reverse. A release with `announced` keeps the announced date and gets no `seen_by`.

## part

A branded, numbered product. `number` is exactly as the manufacturer prints it,
including variant suffixes (`368014-S`, `362280-K`). `name` is the description
from the newest source, verbatim apart from trademark glyphs and quote
normalisation; the trailing pack count `(10)` is moved into `pack_qty`. Older
differing descriptions go to `former_names` so a rename or a spec change
(`PIN 2x10` to `PIN 2x9.8` under the same number) stays visible. `former_names` holds only the names a maker published: a product it renamed, on its own site or in its catalogue. A former name is a different name the maker published for the same part. It is not the part's current name again once a pack count (`(10)`, `x10`, `10pcs`), a part or set number (five or more digits), punctuation, the brand word in front (`HUDY PIN` for `Pin`) and a store's catalogue number of three to six digits in front (`1625 Parts Screws` for `1621 Parts Screws`) are removed, and it is not listed twice (case and spacing ignored); validate.py rejects both, and an importer's `former_names.store()` drops them (the pack count of a dropped entry becomes `pack_qty` when the part has none). A listing line such as `HEX SCREW SH M3x14 (10) 107841` is therefore never a former name. A name read by OCR from a manual or a scan is not one: it goes to `ocr_names`, and a manual's bag callout (`(BBS x10)`) is no name at all. `name` does not repeat the brand: the site prints the brand in front, so "Hosim 16207 RTR" is stored as "16207 RTR" (validate.py checks it).

```toml
id = "part/xray/362250"
brand = "brand/xray"
number = "362250"
name = "COMPOSITE STEERING BLOCK - MEDIUM - V2"
pack_qty = 2
former_names = ["COMPOSITE STEERING BLOCK"]
```

`ocr_names` (optional, a list of strings): the names OCR read from a manual or a scan for this part, kept only for the matching tools. The site never shows them and the search index does not hold them (`export.py` writes them with the rest of the record). A reading that has no letters, runs over 60 characters (several names in one) or is a single word is dropped (`former_names.ocr_clean()`). A reading that is the maker's own product page title for the part stays a former name.

`pack_qty_basis` (optional, only with `pack_qty`): where the count came from, written right after it. `name`: the maker's part name states it (`(10)`, `10pcs`). `page`: the maker's (or a dealer's) product page states it. `includes`: the sum of the part's `includes` quantities (a bearing kit). `manual`: the count is printed in the maker's manual or parts list, the document is among the part's documents/sources (a line with the part's number and the count, `(10)` or `10pcs`). `photo`: counted on one product photo, which does not always show the whole pack, so this is the weakest basis; the site says so. `photos`: two or more independent photos of the item number gave the same count. `owner`: checked by the project owner on the pack. A text basis (`name`, `page`, `includes`, `manual`) always wins over a photo count; a photo count that disagrees with a text count is never written (audit "pack-photo-disagrees"). A `pack_qty` with no basis was written before the basis existed and its source is not known (audit "pack-qty-no-basis").

A part of a brand with `item_numbers = false` has no `number`: never put a
store handle or SKU there to fill it. Its id keeps a slug
(`part/acer-racing/bandit-ball-bearing-kit`), which also names its file.

Optional, generated when the source states it: `released`, the date the
brand lists the part as released, `YYYY-MM-DD` or `YYYY-MM` (HUDY's product
list gives a day per item, Tamiya's monthly new-items list a month),
`announced` (`YYYY-MM-DD`) with `announced_source`, the https URL it comes
from, as for a release (the brand's news post, product page or video, or a
Big Squid RC post naming the part by its number or exact name), and `applies_to`, the models the
brand lists the part for, verbatim (TLR writes "Description (pack): 22X-4 2.0").
A brand that names the car only in the part's name (RW Racing: "Supalite Spurs
48DP for Xray 008/009 73T") gives the car's words from the name, "Xray 008/009".

`seen_by` (`YYYY-MM-DD`) with `seen_by_source`, as for a release (below): the
first day the maker had the part on its own pages, never a release date. It is
set on a part with no `released` or `announced`, from the day the maker's own
Shopify shop published the product (`seen_by_source` is its
`https://<host>/products/<handle>` page) or the day a maker page the part links
was first fetched (from 2026-10-27 on; `seen_by_source` is that page). Days on
which a shop published, or we first fetched, dozens of parts at once (a
migration or a first sweep) are not used. The site's Latest list shows it as
"seen by".

`category`: what kind of part it is, one of the categories in `data/categories` (see category below): `ball-end`, `battery`, `bearing`, `body`, `body-accessory`, `bumper-guard`, `charger`, `chassis`, `clip`, `cooling`, `decal`, `differential`, `drivetrain`, `electronics`, `engine-fuel`, `esc`, `gear`, `glue`, `hardware-set`, `light`, `manual`, `merchandise`, `misc`, `motor`, `nut`, `o-ring-seal`, `oil-grease`, `paint`, `parts-tree`, `pin`, `pinion`, `radio`, `rod-end`, `scale-accessory`, `screw`, `servo`, `shock`, `shock-spring`, `spur-gear`, `steering`, `suspension`, `tire`, `tool`, `turnbuckle`, `washer-shim`, `wheel`, `wing`, `wire`. It is derived
from the name by a classifier and recomputed when the rules improve; set
`category_source = "curated"` to fix a category by hand. The same mark is set on a category the maker states (a section of its parts list or a collection on its site, from the importer or tools/link_maker_sections.py) and the classifier keeps it. Every part has one. A part no rule places (its name is bare, a number, or unknown to the classifier) gets the fallback: `category = "misc"` with `category_source = "fallback"`, so it stays findable and a later rule or maker section replaces it (the replacement drops `category_source`). A fallback part can also be placed from the maker's own documents or from its photo: `category_source = "manual-section"` is a category taken from the section of a cached manual, parts list or exploded view that prints the part's number (tools/link_manual_sections.py; the section titles that map are a reviewed table); `category_source = "photo"` is a category a local vision model read from the part's product photo with high confidence (only after it agreed with known categories on a calibration set). A name rule or a curated mark replaces either; neither is ever set on a part that has a real category. `misc` also holds the named leftovers: springs other than shock springs, retracts, tape, velcro, silicone tubing and adjusters whose purpose the name states.

```toml
name = "Shock Spring, Internal, 1.6lb"
category = "shock-spring"
```

Optional, hand-curated (the importer preserves them when it regenerates the
file): `material` (steel | stainless | titanium | aluminium | brass | bronze | plastic |
carbon | ceramic | carbide | unknown; carbon is carbon fibre, which brands also
call graphite; plastic covers composite, nylon and POM; for a bearing, the
balls: ceramic is a hybrid bearing), `material_grade` (the alloy as named:
"7075-T6", "6061"; tools/link_material.py reads both from names and leaves
a name with two materials unset), `seal` and `lubricant` for bearings (see below), `strength_class` ("12.9", "A2-70"), `finish` ("black oxide"),
`thread_type` (machine | self-tapping), for self-tapping screws `point` (cone | flat | rounded | blunt: the shape of the end; flat as ISO 7049-F, cut off flat after the thread, as on Tamiya's tapping screws in its product photos; blunt is a longer taper to a flat end; drawings use cone when it is not set), for shocks `shock_part` (complete | body |
shaft | piston | cap | rebuild-kit | rod-end | spring-cup), `length_mm`, `bore_mm`
and `shaft_mm` (shaft diameter), `name_source` (`ocr`: the name was read by OCR from a scanned document and not checked yet; `manufacturer`: corrected from the manufacturer's own product page; `manual`: copied from a maker's manual as printed, read by eye; `dealer`: taken from a dealer's or importer's product page because the maker's own pages do not name the number, with a link of kind `dealer`; `owner`: the owner's correction of a dealer's name, a thickness or a car the dealer's name states wrongly, which no import replaces), `range` (colour versions of one part share a range ending in `-colours`, e.g. "team-corally/c-00180-1055-colours" for a body in clear and four painted colours, set by tools/link_colour_variants.py; tools/link_part_colours.py then gives each version its `color` in plain words when the name states one colour of the part itself ("(blue-anodized)" -> "blue"); otherwise a shared id such as "rc4wd/540-crawler-brushed-motor" for the
parts of one product range that differ only in wind, kV or a similar rating;
the site lists the other versions on each part page), for ball studs, rod ends and ball cups `ball_mm` (the ball
diameter both must share) and for balls `ball_type` (stud: has its own thread |
nut: threaded inside, on a separate screw | through-hole: bored through, a screw
passes through it | set-screw: has its own set screw that clamps it on an
anti-roll bar wire or link bar), and `equivalent_to`:

```toml
material = "steel"
equivalent_to = [
  { spec = "spec/screw/m3x10-countersunk-hex", match = "functional", source = "doc/xray/xb2-2026-part-list", notes = "..." },
]
```

A part is only `equivalent_to` a spec of its own kind: a bearing spec for a part in category bearing, a screw spec for a screw, a nut spec for a nut, a washer spec for a washer, shim or spacer, and so on (wheel-hex specs also for wheels, tyres, hubs and axles that carry the hex). A part that comes with bearings, screws or a battery (a clutch bell with its bearings, a screw kit with washers, a battery with a charger) lists them in `includes` instead. tools/validate.py checks this.

`match` is exact (same standard, stated by the brand), functional
(interchangeable in practice) or close (check before use). Geometry lives on
the spec; material, grade and finish live on the part, because that is what
differs between a kit screw and its replacement.

Bearings work the same way: the size is on the spec, the variant on the part.
A ceramic 5x10x4 and a steel one link to the same spec and differ in
`material`; `seal` is open | metal (shields, ZZ) | rubber (2RS) |
rubber-metal, `lubricant` is oil | grease.

```toml
name = "BALL-BEARING 13x19x4 RUBBER & STEEL SEALED - GREASE"
equivalent_to = [{ spec = "spec/bearing/13x19x4", match = "functional" }]
material = "steel"
seal = "rubber-metal"
lubricant = "grease"
```

Silicone oils link to `spec/oil/silicone-<cSt>cst` only when the brand states
the viscosity in cSt. The "wt" and "K" scales differ between brands, so a
brand's wt goes on the part as `viscosity_wt`, never on a spec. `volume_ml` is
the bottle size.
Brands that grade by their own number without a unit
(Tamiya #400) link with match "close" and say so in the notes. A set of
oils lists its bottles with `includes`, one row per spec:

```toml
name = "Silicone Damper Oil Soft Set (#200, #300, #400)"
includes = [{ spec = "spec/oil/silicone-200cst", qty = 1, notes = "Tamiya #200" }, ...]
```

```toml
name = "Oil, shock (30 wt, 350 cSt, 60cc) (silicone)"
equivalent_to = [{ spec = "spec/oil/silicone-350cst", match = "functional" }]
volume_ml = 60
viscosity_wt = 30
```

Glues (category `glue`: CA and tyre glue, epoxy, kickers, debonders,
threadlockers, glue tips and applicators) give their grade as `viscosity`
(thin | medium | thick, as the brand names it; a gel counts as thick) and
the bottle size as `volume_ml` when the brand states it in ml or fl oz.
Parts sold "with threadlock" or "with glue" are not glues.

Paints (category `paint`) carry, as the brand states them: `paint_role`
(paint | clear: a clear coat | primer | thinner: also retarders |
cleaner | masking: tape, sheets and fluid for masking), `paint_type`
(polycarbonate: for clear bodies, sprayed on the inside | lacquer |
acrylic | enamel; for a thinner or cleaner, the paint it is made for),
`application` for paints, clear coats and primers (spray-can | airbrush:
ready to spray from an airbrush | brush | marker: a paint pen), or a list when
the brand names several (["airbrush", "brush"]), `finish` (gloss | flat |
semi-gloss | metallic | pearl | fluorescent | translucent | clear |
chrome | flake: glitter, lame or metal flake in the paint; only what the brand says, left out otherwise), `color` in plain
colour words ("white", "dark green", "purple/green"; the brand's own
colour name stays in `name`) and `volume_ml`, the can or bottle size.
`swatch` is an approximate colour as a lowercase hex value ("#e81c24"),
sampled from the middle of the colour chip on the manufacturer's own
colour chart. It is a guide, not a match: the chart is printed ink, and
screens and photos shift colours; metallic, pearl and fluorescent paints
are a flat sample of a chip that shines in real life.
Brushes and other painting tools are category `tool`. A kit whose
manual names a paint or a tool to use (Tamiya: "PS-1", "ITEM 74005")
lists it in `contains` with role `listed`, the manual as source and the
pages in the notes.

```toml
number = "86001"
name = "PS-1 White"
category = "paint"
paint_role = "paint"
paint_type = "polycarbonate"
application = "spray-can"
color = "white"
swatch = "#ffffff"
volume_ml = 100
```

`includes`: what a set holds, as parts or specs with a count, when the brand
lists the contents (a bearing set, a screw kit):

```toml
includes = [
  { spec = "spec/bearing/5x10x4", qty = 8, source = "doc/xray/..." },
  { part = "part/xray/940512", qty = 4 },
]
```

`fits`: the kits a part is sold for, from the brand's own fitment data (option
parts catalogs, matching lists, product pages). Distinct from `contains`,
which says what comes in a release's box.

```toml
fits = [
  { kit = "kit/tamiya/dt-03", type = "direct", source = "doc/tamiya/option-parts-matching-list-2025-10" },
  { kit = "kit/tamiya/tt-02", type = "modification", source = "doc/tamiya/option-parts-matching-list-2025-10", notes = "Matching list comment #2" },
]
```

`type` is direct (bolt-on), replaces (replaces a stock part) or modification
(needs changes or extra parts; see notes). A `replaces` row may name the stock
part it replaces, `replaces = "part/lc-racing/L6045"`; the site then shows the
upgrade on both parts.

A row may narrow the kit to the releases the maker lists the part for, with
`releases`: a per-car set (a bearing or screw kit sold for one car, such as
"Tamiya TT-02 2020 Ford GT Mk II (#58689) Screw Kit") fits that car, not
every car built on the chassis. Every id must be a release of the row's kit.
A row without `releases` fits every release of the kit.

```toml
fits = [
  { kit = "kit/tamiya/tt-02", releases = ["release/tamiya/58689"], type = "direct", source = "doc/rcscrewz/store", notes = "Listed for the Tamiya TT-02 2020 Ford GT Mk II (#58689)" },
]
```

When the maker lists the part for a car that is none of the kit's releases
(a car not in the data yet), the row says which car with `car`, the car as
the maker names it, in place of `releases`; the part then fits that car only,
not the other releases of the kit:

```toml
fits = [
  { kit = "kit/tamiya/tt-02", car = "Ferrari 458 Challenge XB", type = "direct", source = "doc/fast-eddy/store", notes = "Listed for the Ferrari 458 Challenge XB TT-02" },
]
```

A row with neither fits the whole kit: a set that names only the chassis
("Tamiya TT-02 Chassis Bearing Kit"). The site lists a per-car set on a
release page only when its row names that release or neither field; the
others go into one collapsed line of sets made for other cars of the kit.

tools/link_car_kits.py in hobbydex-tools sets both from the set's name: an
item number of a release first, then the car's name against the names of
the kit's releases (the XB and the kit of one car, and its colour editions,
all match; shop shorthand such as "Sub" or "Alpha Romeo" is read as the
maker). `car` is set only for the shops that sell a set per car (Fast
Eddy, RCScrewZ, Avid RC, Acer Racing ...) on kits sold under many bodies
(Tamiya's chassis, platforms such as the SCX24 or Fazer Mk2); elsewhere the
kit is the car.

`documents`: the part's own documents, such as a radio's user manual (a list of `doc/` ids). A part has no singular `source` field: the site does not read it, so tools/validate.py rejects it; the docs the part came from go in `documents`. Radios
and receivers also carry `channels` and `protocol` (AFHDS 3, ANT, DSMR) and
`weight_g`; their model code is the part number (FS-NB4+, so a number may
contain `+`).

`radio_unit` says what a radio part is: `transmitter` (the transmitter as the
maker lists it, with no receiver named as part of it), `receiver` (a
receiver, also an ESC or a car's control board with a receiver built in),
`set` (a transmitter sold with its receiver under one number) or `gyro` (a
steering gyro or gyro module, sold on its own or built into a receiver only
when the name says the receiver part is secondary; a receiver with a built-in
gyro stays `receiver`; a gyro mount, plate, case or cable is not a gyro and
has no `radio_unit`). On a transmitter or a set, `dimensions_mm` and
`weight_g` are the transmitter's; on a receiver they are the receiver's. A set lists its receiver in
`includes` when the receiver is a part of its own; when it is not, the
receiver's size and weight go in `notes` as "Receiver: 35 x 21 x 12 mm,
11 g". The field is left out where the maker does not make clear what the
part is. tools/validate.py checks the values and that the part is in
category radio, or esc for an ESC with a receiver.

`gtin`: the product barcode (UPC-A, EAN-13 or another GTIN) as a string of
digits, as printed by the brand; the validator checks length and check digit.
Releases can carry a `gtin` too, the barcode on the kit's box.

`links`: pages about this part, release or kit elsewhere, as `{ site, url }`
(https only); the site shows them as buttons next to the web search.
`kind = "press"` marks a news or press site's post about the release or part (Big Squid RC); see `announced`.
`kind = "dealer"` marks a retailer's or distributor's product page for this release or part, when the maker has none for it. It is a shop's page, never the maker's: the site shows it as "Dealer page: <host>", never as the product page. A release or part keeps a dealer link only when it has no maker product page (a maker link or a `product_page` document of the maker); a release has one, a part one per shop, each its own product page on the shop; tools/validate.py fails a release or part with a dealer link beside a maker link or product page. A shop's listing page that names several releases is a document of kind `catalog`, never a release's link.
`kind = "maker"` marks a page of the brand's own shop or site that is not its product page (the Tamiya USA spare page of an 8-digit Tamiya spare, `{ site = "Tamiya USA", url = "https://www.tamiyausa.com/shop/7-digit-spare-parts/...", kind = "maker" }`); the site shows it as a maker page. A part with a maker-kind link keeps its dealer links (user, 2026-10-24), and tools/validate.py counts only a link with no kind as the maker product link for the dealer rule.
`kind = "archive"` marks a Wayback Machine capture, `https://web.archive.org/web/<14-digit timestamp>/<original URL>`, of the maker's product page when that page is gone: the brand's own site is gone (a defunct maker such as Team Durango, or Hot Bodies' old hotbodiesonline.com pages for HB Racing parts the current site does not have), or the part's own page now answers 404 or 410. A part whose maker page is live links that page (no kind), never a capture of it. The site shows an archive link as "archived page".
`gone` (optional, `"YYYY-MM-DD"`) on a link: the day the page answered 404 or 410 on a recheck. The link is kept, not removed, so the record says where the page was; the site hides it, a maker product link marked gone no longer counts as the product page (the part may get a dealer or archive link), and tools/regression_check.py does not count marking a link gone as a regression. Set by tools/link_maker_pages.py in hobbydex-tools.
`kind = "fan-site"` marks a link to a fan or community site (such as
TamiyaBase): it is a courtesy link for readers, not a source for any value in
Hobbydex, and the site shows it apart from the brand's own pages.

```toml
links = [{ site = "TamiyaBase", url = "https://www.tamiyabase.com/parts/13934-10004255", kind = "fan-site" }]
```

`numbers`: the part's other numbers, when one part is printed or sold under
more than one (Tamiya's 7-digit spare number, 8-digit SKU and X-number). One
part is one record: it is keyed by the number the part is sold under, and a
record written earlier under another of its numbers is folded in, its id kept
in `former_ids`. No number of a brand may be a second part's `number` or
`numbers` (validate.py checks). ARRMA: the manuals print the maker's number
AR + 6 digits; Horizon sells it as ARA + the same digits (ARA330550 is
AR330550), or, for older parts, under a store number such as ARAC9098 whose
page states the maker's number (AR330538) as "Manufacturer #".

```toml
id = "part/arrma/ARAC9098"
number = "ARAC9098"
name = "Front Shock Spring"
former_ids = ["part/arrma/AR330538"]
numbers = ["AR330538"]
```

`rebrand_of`: the part this one is the same product as under another brand
(a radio HobbyKing sold as Turnigy), with a `source` or `notes`. Recorded once,
on the rebranded part; the site shows it from both sides.

```toml
rebrand_of = [{ part = "part/flysky/FS-GT5", source = "doc/community/2026-10-10-turnigy-gt5-is-flysky-gt5" }]
```

`name_de`: the brand's German name, kept when `name` is an English translation of it (ScaleART kit names, translated with a fixed glossary).

`name_ja`: the brand's Japanese name, kept when the English `name` is a
translation (Yokomo, ABC Hobby, Wrap-Up Next, EXceed and O.S. Engines publish Japanese-only names;
tools/translate_ja.py gives them the English name, with a note).

`name_fr`: the brand's French name, kept when the English `name` is a
translation (T2M and Hobbytech publish French-only names; tools/translate_fr.py
gives them the English name from tools/data/translate_fr_names.tsv, with a note).

`related`: other parts of the same brand this part goes with, as the brand's
name or page says: `[{ part, relation }]` with relation requires (needs the
other part: Tekno "requires TKR9057B"), fits (made to fit that part: Corally
"fits part C-00180-022"), use-with, for (an accessory made for it: HUDY
"Ejector for 106000"), replaces or same-colour (a paint the brand's own colour
matching list gives as the same colour in another range, though the shade
may differ slightly: Tamiya LP-1 Black, X-1 Black and TS-14 Black; recorded
on each of the paints). Others are recorded on the citing part; the site
shows it from both sides. tools/link_part_refs.py reads them from names.
A wheel nut that states its hex (17, 23 or 24 mm) is `use-with` each wheel hex or axle of the same brand that shares a release with it and, where both state a size, the same size; the row sits on the nut only, and the site shows "Used with" on the other part.

`supersedes`: the part this one replaces, when the brand has replaced it with
an upgraded version (`supersedes = "part/team-corally/C-00180-194"` on
C-00180-714). The site shows it on both parts.

`status` (optional): `discontinued` or `available`, the same words a release uses for being out of production. Set only where the maker or a shop states it: a note such as "Discontinued: ..." or "Listed in KO Propo's Discontinued Products Table", the store's DISC.. marker, a Kyosho product page filed under discontinued or with a discontinued buy box, or a name carrying "(Discontinued)". Left out when not stated; age never decides it. tools/link_part_status.py sets it from those statements and reruns after the importers. A successor the maker names in the discontinued part's notes carries `supersedes` back to the old part, unless two old parts name it.

## spec

A generic, brand-independent specification. Category-specific fields; for
screws: `thread`, `length_mm`, `head` (countersunk | socket-cap | button |
pan | flanged-socket-cap | flanged-button | flanged-pan | low-head | set | truss | hex (a hexagon head, with no socket: Tamiya's hex head screws, whose drive is jis); the brand names each code in [brand-hardware-names.md](brand-hardware-names.md)), `drive` (hex | torx | phillips | jis | slot; jis is the JIS B 1012 cross recess Tamiya uses, which takes a JIS driver, not a Phillips one), `standards`. No material:
the same geometry exists in many materials.

```toml
id = "spec/screw/m3x10-countersunk-hex"
category = "screw"
name = "M3x10 countersunk screw, hex socket"
thread = "M3"
length_mm = 10
head = "countersunk"
drive = "hex"
standards = ["ISO 10642", "DIN 7991"]
```

Bearings: `type` (radial-ball | flanged | thrust), `bore_mm`, `outer_mm`, `width_mm`
and, for standard sizes, the ISO `designation` (MR105, 6700; flanged MF105,
F685). Ids are `spec/bearing/<bore>x<outer>x<width>`, flanged bearings
`spec/bearing/flanged-...`, thrust bearings `spec/bearing/thrust-...`. A
flanged bearing has a collar on its outer ring, so it does not replace a
plain one of the same size (and the other way round).

```toml
id = "spec/bearing/5x10x4"
category = "bearing"
name = "5x10x4mm ball bearing (MR105)"
type = "radial-ball"
bore_mm = 5
outer_mm = 10
width_mm = 4
designation = "MR105"
```

Inch bearings take the maker's R series (R168 for 1/4x3/8x1/8 in) when all three
sizes match it exactly; a size written in rounded millimetres is folded into the
exact spec (former_ids). A flanged bearing takes the flanged designation of its
series (MF105, F6700, FR168 for inch) only when a maker table confirms it.

A flanged bearing may give its collar: `flange_mm` (flange outer diameter, larger
than `outer_mm`), `flange_width_mm` (flange thickness) and `flange_source`, the
URL of the maker's catalogue page the figures come from. A size missing from the
catalogue gets none of the three.


Oils: `base` (silicone) and `viscosity_cst`; id `spec/oil/silicone-350cst`.

Pinions: the meshing geometry, `teeth` and either `pitch_dp` (diametral
pitch, 48) or `module` (0.5, 1); id `spec/pinion/48dp-20t` or
`spec/pinion/mod0.5-20t`. The bore is on the part (`bore_mm`), with the
material, because one geometry is sold for several shaft sizes and brands
often leave the bore out.

Spur gears carry `teeth` and either `pitch_dp` or `module` on the part
itself, read from the name. They get no generic spec: spurs of one
pitch and tooth count mesh the same pinions but mount differently.

`teeth` (an integer from 5 to 300) is the tooth count a part's name or page states, on spur gears and pinions (above), on pulleys (`19T pulley`) and on servo horns when the count is a tooth count. A servo horn's "25T" is usually its spline, which is `spline_teeth` (see Servos), so a horn names no `teeth` unless its maker gives a tooth count apart from the spline. A name with several counts (`13 to 35 teeth`, `72T/76T`) gets none.

`weight_g` (a number of grams above 0 and up to 50000, such as `69` or `4.2`) is set on any part whose source states its weight: "Weight 70g", "70 g", "(70g)", "Gewicht: 70 g", "Poids : 70 g". A weight the source gives in ounces is converted and rounded to whole grams. A figure that is a capacity or a load is never a weight: "70kg servo" is torque, "holds 5 kg" is a load. Parts of any category carry it; the radio, battery, servo, motor, ESC and engine sections above say what else their weight means.

Chargers are parts with category charger and, when stated, `power_w`.

Batteries: the electrical group, `chemistry` (lipo | lihv | life | nimh | liion),
`cells`, `capacity_mah` and `nominal_v`; id `spec/battery/lipo-2s-5000mah`.
The part's own `voltage` is the nominal volts its name or maker page states (7.4 for
"7.4V"), set by tools/name_fields.py; the spec's `nominal_v` is what a spec row is matched on.
Maker spec dumps in notes ("Battery Type Li-Po; Cells 2; ...", "Li-Ion pack, 7.4V") are read into
these fields when the part is written, and the note keeps only what no field takes.
Whether a pack fits a car depends on the part's `c_rating`, `case` (hard |
soft | shorty), `dimensions_mm` ([length, width, height]), `weight_g` and
`connector` (XT60, EC5, Deans, ...), so those stay on the part.
`balance_connector` is the balance lead, in the same plug vocabulary as
`connector` ("JST-XH" only, for now): the maker states it, and no cell count
alone sets it. Its pin count follows from `cells` (pins = cells + 1), so the
site links a pack with `cells = 3` and `balance_connector = "JST-XH"` to
`spec/connector/jst-xh-4`. A pack that states another balance plug (EHR, TP,
Hyperion) takes no value until a spec for it exists. A Traxxas iD pack takes
none either: its balance runs through the iD main plug, and no balance value
names that plug (user, 2026-10-24).
NiMH and Li-Ion packs have none (a maker's own statement of a lead still counts).
`balance_connector` is the battery's secondary plug, not its main `connector`
(the power plug): the site shows the two as separate rows, and a connector spec
lists a battery under its balance section, never as its main plug.
`balance_connector_basis` says where the value comes from: `"maker"` when the
maker's text names JST-XH, `"convention"` when nothing is stated and the pack is
a LiPo, LiHV or LiFe of 2S to 8S (the usual balance lead; the site says it is not
stated by the maker). Set by `tools/link_part_connectors.py --category battery
--balance`, which never changes a maker value and recomputes a convention value on every run (a maker statement of JST-XH relabels it "maker"; another plug or an exclusion clears it); a pack whose maker or name states
another balance system (EHR, G-Tech, TP, Hyperion, XHP), a Traxxas iD pack (its own page claims the iD plug and sells no iD charging port for it), a Spektrum
Smart pack, a 1S pack, a pack without `chemistry` or `cells`, and NiMH packs get
none. `chemistry` is set from the name when the name states it (LiPo, LiHV, LiFe, NiMH; tools/name_fields.py), so a pack without a stated chemistry gets none.

```toml
name = "1100mAh 3S 60C 11.4V(HV) Lipo Battery | XT30 Plug"
equivalent_to = [{ spec = "spec/battery/lihv-3s-1100mah", match = "functional" }]
c_rating = 60
connector = "XT30"
dimensions_mm = [61, 26, 21]
weight_g = 69
```

Servos: `size_class` (micro | mini | midi | standard | low-profile | jumbo |
wing) and `spline_teeth`; id `spec/servo/standard-25t`. Two servos of one
spec can still differ in case size and mounting holes, so the part keeps
`dimensions_mm`, `weight_g`, `torque_kgcm` and `speed_s` (seconds per 60
degrees) at `voltage`, `voltage_range`, `gear_material`, `motor` (brushless |
coreless | cored), `connector` and `rotation_deg` (the throw, when the brand states it).
Bearings and PWM: `bearings` (an int count of 1 to 10, when the maker states one: "2 ball bearings" and "dual bearings" both give 2),
`bearing_kind` ("ball" | "bushing", when the maker names it; it can be set without a count), `dead_band_us` (whole microseconds)
and `frequency_hz` (the PWM rate in hz: one figure, or `[low, high]` when the maker gives a range; a figure the maker gives only as
an upper limit is recorded as that figure). Each is set only from the maker's own statement; a field the maker does not state is left out.

Motors: the can and the shaft, which decide whether a motor drops into a
motor mount and takes the pinion: `motor_type` (brushed | brushless), `can`
(the industry's size name, a string), `diameter_mm` and `length_mm` (the can
rounded to whole millimetres) and `shaft_mm`; id
`spec/motor/<motor_type>-<can>-<shaft>mm`. Brushless cans are named
diameter then length, `3652` for 36 x 52 mm; the brand's own can number is
used when its name has one that fits the dimensions (QuicRun 3650SD at 36 x
52.8 mm is a 3650), otherwise the measured O.D. and length are rounded to
whole millimetres (35.8 x 51.5 mm is a 3652). Brushed motors keep their can
class from the name (540, 555) and have no `diameter_mm` or `length_mm` on
the spec.

```toml
id = "spec/motor/brushless-3652-3.175mm"
category = "motor"
name = "Brushless motor, 3652 can, 3.175 mm shaft"
motor_type = "brushless"
can = "3652"
diameter_mm = 36
length_mm = 52
shaft_mm = 3.175
```

The motor part keeps what differs between motors of one can: `kv`, `turns`
(13.5 for a 13.5T stock motor; with `winds` the number of parallel wires of each turn, 2 for LRP's "10x2T"), `lipo_cells` ([min, max] LiPo cells, also on
ESCs), the measured `diameter_mm`, `length_mm` and `shaft_mm`, and
`weight_g`, and `sensored` (true for a brushless motor with Hall sensors,
false for a sensorless one, as the maker states; a brushed motor has no
sensors and carries no field). Bearing sizes go in `notes` (a motor is not
a set, so no `includes`).

`motor_type` is set by tools/link_esc_props.py, for motors and ESCs alike, from the first source that gives one
clear answer: the name and notes (and a maker model code, such as Hobbywing's "BL", which is brushless), the part's
own manuals (text layer, else OCR), the brand's own product page (dealer pages are never read), and last the
`sensored` field, which implies brushless. Turns and kV never decide it.

`mount_holes` gives the motor's mounting holes on its shaft end, as the
maker states them: a list of hole patterns, each
`{ thread = "M3", count = 2, circle_mm = 25 }`. `circle_mm` is the
centre-to-centre distance of opposite holes, which is the bolt-circle
diameter when there are more than two; `count` is 2, 3, 4, 6, 8 or 12,
spaced evenly on that circle, and is left out when the maker gives the
thread and spacing but not how many holes (Tekin's "M3 @ 25.4mm"): the
site then draws the pattern dotted. A motor with two sets of holes (two at 25 mm and
two at 30 mm) lists both. Set it only from the maker's own drawing or
specification, never from the can size.

```toml
name = "XeRun V10 G5 13.5T"
kv = 4050
turns = 13.5
lipo_cells = [1, 3]
diameter_mm = 35.8
length_mm = 51.5
shaft_mm = 3.175
weight_g = 138
mount_holes = [{ thread = "M3", count = 2, circle_mm = 25 }]
notes = "Bearings (Hobbywing's specifications): front 4x9x4, rear 3x8x4"
equivalent_to = [{ spec = "spec/motor/brushless-3652-3.175mm", match = "functional", notes = "Derived from Hobbywing's dimensions (...)" }]
```

Motor heat sinks and motor fan mounts that clamp on the can fit any brand's
motor of that diameter: `motor_can_mm` gives the can diameter they take (36
for a 540 or 550 can and 36 mm brushless motors, 28 for 380, 42 for a 1/8
4268 or 4274, 40 for 4074, 56 ...). Set it only from the maker's own
wording, in the name, the product page or its spec table ("for 540 motors",
"Dia 42mm", "fits 36mm motors", "Motor Heatsink 4074"): "540" or "550" is
36, "380" is 28, a can number is its diameter (4074 is 40) and a stated mm
wins. Never from the car it comes with; a fan size ("30x30mm") or a heat
sink's height is not a can size. Heat sinks made for one car or motor
("TT-02 Aluminum Motor Heat Sink") and motor plates with fins fit through
`fits` and carry no `motor_can_mm`. Category cooling (or chassis for a
fan mount), set by tools/link_heatsinks.py in hobbydex-tools.

```toml
name = "Alu Dual Motor Fan Mount Dia 42mm (2x30mm / 2x40mm)"
category = "chassis"
motor_can_mm = 42
```

ESCs are parts with category esc and, when stated, `current_a` and
`peak_current_a` (continuous and burst amps), `lipo_cells`, `dimensions_mm`,
`weight_g` and `sensored` (true when the ESC has a sensor port and runs
sensored motors, false when it is sensorless only). A motor and ESC combo lists its components with `includes`.

ESC properties, all set only from the maker's own wording in the name or notes
(tools/link_esc_props.py fills them; a value a part already has is never
changed): `motor_type` (brushed | brushless | both, when the maker names
both, "Brushed/Brushless"; the sources are as for motors, above, and `sensored`
implies brushless); `bec_v` (the BEC output voltage: one figure, or a
list of two or more when the maker says it is switchable, "6.0/7.4 V
switchable" gives [6.0, 7.4]; a range such as "6.0-7.4 V" is not a list and
is left out); `bec_a` (the BEC's continuous current in A, "BEC 6V/3A" gives
3, "500 mA" gives 0.5); `motor_limit_t` (the lowest
motor turns the maker allows, "Motor limit 20T" gives 20, a limit that
depends on the cell count or a class of turns is left out) and
`motor_limit_kv` (an int kV limit the maker states without a cell count);
`nimh_cells` ([min, max] NiMH cells, like `lipo_cells`); `programming` (a
list of how the ESC is set up: card (program card), box (program box), app,
bluetooth, wifi, buttons, transmitter); and `resistance_mohm` (the internal
resistance in milliohms, "resistance 0.0014 ohm" gives 1.4). All are
ESC-only (category esc), except on a 2-in-1 motor (category motor, with its ESC built in: the Furitek UNITY, Spektrum Firma units), which keeps the ESC fields the maker states. Example:

```toml
name = "Viper Auto Sport 20, speed controller, waterproof"
category = "esc"
motor_type = "brushed"
bec_a = 1.5
waterproof = true
motor_limit_t = 20
nimh_cells = [4, 8]
```

`waterproof` (true when the maker says waterproof, false only for an explicit
"not waterproof") is set from the maker's wording on esc, motor, servo and
radio parts (receivers included), in the name, the notes or a spec table
row; an IP rating goes in `notes`, not in the field. Partly waterproof
("Partially WP") is left out.

`motor_connector` is the plug on an ESC's motor wires, or on a motor's
leads, in the same plug vocabulary as `connector` (bullets: "3.5mm bullet",
"4mm bullet" ...; the spec is spec/connector/bullet-<mm>mm). It is set on esc
and motor parts only, from the maker's spec table. A plug the maker names
that has no spec (6.5 mm bullets) takes no value.

`receiver_connector` is the servo plug on the lead that goes to the receiver
(the throttle lead of an ESC, the lead of a light controller): "JR", "Futaba"
or "JR/Futaba" (one plug sold for both radios), the servo plug names `connector`
uses, mapped to spec/connector/servo-jr and servo-futaba. It is set on esc and
light parts only, from the maker's wording on that lead ("the receiver lead is
the JR type"). The maker's programming cables (JR plugs at both ends), USB and
program-box interfaces, transmitters, telemetry and sensor leads are not the
receiver lead; a plug the maker does not name gives no value. tools/validate.py
checks the name and its spec.

`scales` (a list of scales, ["1/10", "1/12"]) is the vehicle scales the maker
designates an electronic part for ("Scale 1/16th, 1/18th" in the spec table,
or "Applications: 1/10 touring, 1/12 ..."). It is set on esc, motor, servo and
battery parts only, from the maker's wording. The single `scale` on other
parts keeps its meaning and is not converted to a list: `scale` is the one
scale a part is for, `scales` the list a maker names for an electronic part.

Engines (nitro and gas) are parts with category engine-fuel. A complete
engine carries, when the maker states them: `displacement_cc`,
`engine_class` (the class the maker names, ".12", ".21", ".28", as a string;
or the stated cubic inches cut to two decimals, 0.213 cu.in is ".21"; never
worked out from cc alone), `bore_mm` and `stroke_mm`, `output_hp` (in hp:
the stated hp, or stated PS converted at 1 PS = 0.98632 hp, rounded to
0.01) at `output_rpm` (the rpm the output is stated at), `rpm_range`
([min, max], the practical rpm range), `fuel` (nitro: glow fuel, for glow
plug engines | gasoline: petrol two-strokes of large scale cars) and
`weight_g`. Engine parts, exhausts and clutches in the same category carry
none of these. tools/link_engine_specs.py fills them from
the maker's product pages and the importers' notes.

```toml
name = "O.S.SPEED R2106"
category = "engine-fuel"
weight_g = 345
displacement_cc = 3.49
engine_class = ".21"
bore_mm = 16.08
stroke_mm = 17.2
output_hp = 2.76
output_rpm = 35000
rpm_range = [4000, 45000]
```

"Which kits use this screw" is derived: release -> contains -> part ->
equivalent_to -> spec. Specs are never linked from a release directly.

Bodies carry, when the brand states them, `wheelbase_mm` (the wheelbase
the body is made for, Killerbody's "Long Wheelbase: 313 mm") and
`width_mm` (the body's width), with `scale`. The chassis a body is made for
go into `fits` like any other part.

`chassis_source` (optional, a document id) on a body whose `scale` differs from the scale of the kit it fits: the maker's own
document names the chassis the body is made for (Tamiya's race truck bodies, 1/14, "can be used with TT-01 Type-E and TT-02 chassis",
doc/tamiya/spb-51606-manual). tools/check_body_scale.py leaves such a body out of its scale rows.

`width_mm` on a body is the body width; touring and on-road bodies are sold
by width class (190, 195, 200 mm), which is the number the name states
("Touring Car Body 190mm", "(200mm)"). A number marked as wheelbase (WB,
"260mm WB") is `wheelbase_mm`, never the width. `width_basis` (name | page
| manual | flyer | owner) says where a width came from when it was read from the
name; older widths have none.

Shells (category `body` and `wing`; `body-accessory` when the part is itself
a cut or lexan sheet) carry `thickness_mm`: the thickness of the polycarbonate
(lexan) in millimetres, 0.1 to 5, as the maker states it ("0.7mm", "Light
weight 0.5mm", "Polycarbonate 0.8 mm thick"). `thickness_basis` is `name`
(the part's name states it), `page` (the maker's product page, also when
the notes quote it), `manual`, `flyer` (the maker's printed flyer for the
item, as an owner's copy) or `owner`. Never read from a variant suffix
alone ("-07").

```toml
name = "1/10 Jeep Gladiator Rubicon Hard Body Kit"
category = "body"
scale = "1/10"
wheelbase_mm = 313
width_mm = 193
thickness_mm = 0.8
thickness_basis = "page"
```

Parts fixed to or holding a body (mirrors, door locks, body posts and
mounts, clips, pins, magnets, savers, light buckets without LEDs, grilles,
interiors, roof and bed racks, wipers, handles, antennas) are category
`body-accessory`, not `body`: the body category lists only shells. They
carry no body fields (`wheelbase_mm`, `width_mm`, `depicts`).

Tyres carry, when the brand states them: `compound` (the brand's name for
it, "Super Soft Long Wear"), `scale` ("1/8"), `vehicle` (buggy | truggy |
short-course | stadium-truck), `position` (front | rear | front-rear |
front-2wd | front-4wd), `wheel_size` (the rim diameter as written,
`2.2"`, `2.2"/3.0"`), `insert` (closed-cell) and `mounting` (unmounted:
tyres and inserts only | wheels-included: wheels in the box, to be mounted |
pre-mounted | pre-mounted-not-glued). A tyre on a wheel links to the wheel
hex spec like a wheel.

Shock springs carry, when the name states them: `rate` (the brand's word:
soft | medium | hard | super soft | super hard), `rate_n_mm` (XRAY's C=0.86),
`rate_lb_in` (3.95 lb), `wire_mm` and `free_length_mm` (a number, or a range
as written, "75-77"). Rates are kept as stated, never converted. A brand's
series of springs that differ only in those values shares a `range`
("team-corally/shock-spring-free-rate-wire-c-00180-springs"), set by
tools/link_spring_props.py.

Wheels carry the same `scale`, `vehicle`, `position` and `wheel_size`, and
when stated `beadlock` (true), `offset_mm` (as written, +2 or -0.75) and
`width_mm`, and `color` as named ("black/blue": a black wheel with blue
beadlock rings); a pre-mounted tyre carries its wheel's colour as
`wheel_color`. `vehicle` also takes monster, crawler, touring, on-road,
drift, rally, formula and pan-car. Short course wheels and tyres are
`2.2"/3.0"`. tools/link_wheel_props.py fills these from names; values an
importer read from the manufacturer's specs win.

```toml
name = "Reverb 1/8 Buggy Pre-Mounted Tires (White) (Super Soft - Long Wear) w/EVO Wheels"
compound = "Super Soft Long Wear"
scale = "1/8"
vehicle = "buggy"
position = "front-rear"
mounting = "pre-mounted"
```

### Pin specs

`spec/pin/<d>x<L>` (category "pin", `diameter_mm`, `length_mm`) is a plain
parallel pin, with standards ISO 2338 and ISO 8734 when the size is in
their tables (RC makers also use odd lengths such as 2x9.8): drive-shaft cross pins,
wheel hex drive pins, diff pins. Parts link with match "functional" (size
from the name; hardness and tolerance seldom stated). Hinge, pivot, body,
king, roll and spring pins and grooved pins get no pin spec.

Screw pins (a smooth pin with a head, hex socket or cross, and only a short
thread right under the head; the rest of the shank is smooth, as on a hinge
pin that screws in) use `spec/pin/<d>x<L>-screw` with `type = "screw"`,
`diameter_mm`, `length_mm` and `thread`, e.g. `spec/pin/3x25-screw` ("M3").
`thread` is the metric size of the diameter (M3 for 3 mm) for 2, 2.5, 3, 4, 5
and 6 mm pins, or the size the name states; other diameters get no thread.
Parts link with match "functional" from the size in their name, and only
when the name gives one size: sets and bags of mixed sizes, and screw pins
inside an assembly, get none. Screw pins are category pin.

### Washer specs

`spec/washer/<bore>x<outer>x<thickness>` (category "washer", `bore_mm`,
`outer_mm`, `thickness_mm`, in millimetres as the brands write them:
3x6x0.5, 5x8x0.2, 3x6x1) is a plain ring: a shim, washer or spacer
(a thick one is a tube, so 3x6x6 is a spacer). The name says shim under 1
mm, washer from 1 mm and spacer from 3 mm ("3x6x0.5mm shim", "3x6x1mm
washer", "3x6x6mm spacer"). `shape` is flat (the default, left out),
countersunk (a countersunk bore for a countersunk screw head) or conical
(cone or dish), only where the name says so; a countersunk or conical
washer does not replace a flat one, so it has its own spec with the shape
in the id (`spec/washer/countersunk-3x9x1`). No material: aluminium, steel,
brass and plastic shims of one size share the spec and differ in the
part's `material`. Parts in category washer-shim link with match
"functional" (size from the name). Sets of several sizes ("3x5 shim set
0.1/0.2/0.3mm") list one `includes` row per spec, with `qty` where the name
gives it. Lock, spring, serrated, wedge and flanged washers, flanged and
crush tubes and rubber or foam body-mount spacers get no washer spec.

A washer spec that a published standard fixes cites it in `standards` (`standards = ["DIN 125"]`, with a `data/standards` entry). A maker that cites no standard for its washer links it to the closest such spec with match "close": the closest by outer diameter, only within 0.3 mm, and the part's notes give the measured outer diameter and the manual it was measured from (doc/tamiya/56376-manual).

```toml
id = "spec/washer/3x6x0.5"
category = "washer"
name = "3x6x0.5mm shim"
bore_mm = 3
outer_mm = 6
thickness_mm = 0.5
```

### E-clip specs

`spec/eclip/<shaft>mm` (category "eclip", `shaft_mm`): an E-clip (E-ring, DIN
6799 type) named by the shaft it fits, as the RC makers name them ("3 mm
E-ring" on a 3 mm shaft). A part that states a thickness links to
`spec/eclip/<shaft>mm-<thickness>` (`thickness_mm`, and `outer_mm` where the
name gives one); a part that states none links to the standard spec. Bowed
(wave) E-rings are `spec/eclip/<shaft>mm-bowed` (`variant = "bowed"`). Parts
link with match "functional" (size from the name); thin and HD versions link
"close". A pack of several shafts lists one `includes` row per spec. A spec
whose shaft fits a DIN 6799 size (the size whose shaft range covers it, from
`data/standards/din-6799.toml`) carries `standards = ["DIN 6799"]`, `groove_mm`
(the DIN size, its nominal groove diameter), `din_outer_mm` and
`din_thickness_mm`. A thickness variant carries them only when its thickness
equals the DIN thickness; the others are non-standard and carry none. A name
that gives only a DIN size links to the spec of the smallest shaft that size fits.

```toml
id = "spec/eclip/3mm"
category = "eclip"
name = "3mm E-clip"
shaft_mm = 3
```

### Ball-end specs

`spec/ball-end/<ball>mm-<type>[-<thread>][-h<height>]` (category "ball-end"):
`ball_mm` (the ball diameter, 3 to 14 mm), `type` (stud | nut | through-hole |
set-screw) and, where the name states them, `thread` ("M3", a metric diameter
from M2 to M6) and `height_mm` (the ball's height from "H=8.7"). The type is
read as tools/link_ball_size.py reads it; a name with a stated thread that is
no nut, hole or set screw is a stud. The ball size is one size in the name:
"D=4.9" when the name gives it, otherwise the one size a ball word follows.
Length ("L=6") and the drive size ("2mm Hex") are not in the spec. Parts link
with match "functional" (set by tools/link_ball_end_specs.py). Turnbuckles,
links, rod ends, cups and sets are not ball ends.

```toml
id = "spec/ball-end/4.9mm-stud-m3"
category = "ball-end"
name = "4.9mm ball stud, M3 thread"
ball_mm = 4.9
type = "stud"
thread = "M3"
```

### O-ring specs

`spec/o-ring/<inner>x<cross>` (category "o-ring"): `inner_mm` (the inside
diameter) and `cross_mm` (the cross section), both as the maker writes them in
the name: "O-RING 10 x 1.5" is spec/o-ring/10x1.5. The cross section is always
thinner than the inside diameter. Parts link with match "functional"
(tools/link_oring_specs.py). X-rings, gaskets, bladders, boots and sets of
several sizes are not O-rings for this purpose.

```toml
id = "spec/o-ring/10x1.5"
category = "o-ring"
name = "10 x 1.5mm O-ring"
inner_mm = 10
cross_mm = 1.5
```

### Circlip specs

`spec/circlip/<shaft>mm[-<thickness>]` (category "circlip"): a C-clip, Seger
clip or circlip named by the shaft it fits (`shaft_mm`), with `thickness_mm`
when the name gives one ("Seger clip 12x1.0" is spec/circlip/12mm-1). Circlips
are a different standard from E-clips, so they have their own category and no
DIN 6799 fields. Parts link with match "functional", or "close" when the name
says thin or HD (tools/link_circlip_specs.py). Body clips are sized by their
post, not a shaft, and get no spec.

Size specs of the three kinds above are written only when the size occurs on
at least two parts; a size on one part stays unlinked until a second part
shows it.

### Connector specs

`spec/connector/<slug>` (category "connector"): one connector family and
size, as the makers name them: XT30, XT60, XT60H and XT90-S (anti-spark),
XT90, XT150, AS150 and QS8 (anti-spark), EC2, EC3, EC5, EC8, IC3 and IC5
(EC-compatible), Deans (T-plug), Traxxas iD, Traxxas high-current, Tamiya,
mini Tamiya, JST-RCY, JST-XH (`jst-xh`, and `jst-xh-3` to `jst-xh-9` for the
2S to 8S balance lead, pins = cells + 1), the two servo plugs (`servo-jr`
with two bevelled corners and `servo-futaba`, the Futaba J plug with a lip;
they plug into each other but are two shapes), bullets by diameter
(`bullet-4mm`, `bullet-3.5mm`) and `banana-4mm`. Fields: `family`, `pins`
(the contact count, when a family has one), `pitch_mm` (contact spacing),
`contact_mm` (pin or bullet diameter), `anti_spark` and `polarized`
(booleans), and `polarization` (how the housing keys, in words). A current is set
only from a source: `current_a` (continuous) and `burst_a` (when stated),
each with `<field>_source`, the maker's own page; the wire gauge the rating
depends on goes in `notes`.

A wire part is either the plug itself or a lead, and only the plug is
equivalent to a connector spec. A part that is just the plug (a plug or plug
pair, with or without a short tail of wire sold as "connector") has one
`equivalent_to` row per connector its name gives, match "functional" (or
"close" for XT30U). A lead, adapter, charge lead, extension, harness or any
other part that is not just a plug has no connector-spec row. It lists its
plugs in `connectors`, in the order its name gives them, using the plug names
of the battery `connector` field:

```toml
id = "part/beez2b/BEEC1056"
name = "XT60 Charge lead : TRX 2019 4S"
category = "wire"
connectors = ["XT60", "Traxxas iD"]
```

BEEC1056 is a lead, so it lists its two plugs (XT60, and Traxxas iD for
"TRX 2019") and is not equivalent to the XT60 spec; its plug pair from the
same maker, BEEC2034F "Connector : XT60 Female plug", is equivalent to
`spec/connector/xt60`. Plug names map to specs in tools/validate.py
(`PLUG_SPEC`), the same table as tools/link_connector_specs.py (`PLUG_NAME`).
A servo plug is named "JR" or "Futaba" as the name gives it; "JR/Futaba" is
one plug sold as fitting both (a charge lead or switch harness named for both
radios) and links to both specs.
tools/validate.py checks that each entry maps to an existing connector spec,
that `connectors` is only on wire parts, and that a part has not both
`connectors` and a connector-spec row.

A battery or ESC is not equivalent to its plug either: it names its plug in
`connector` (the site links that field to the spec) and has no `equivalent_to`
row to a connector spec.

```toml
id = "spec/connector/ec5"
category = "connector"
name = "EC5"
family = "EC"
pins = 2
anti_spark = false
polarized = true
current_a = 120
current_a_source = "https://www.horizonhobby.com/product/connector-ec5-device-2/EFLAEC501.html"
notes = "More than 120 A continuous with 10 AWG wire, as the maker states it."
```

A screw spec's head comes from the brand's code table (docs/brand-hardware-names.md):
the same words map the same way for every brand (see [brand-hardware-names.md](brand-hardware-names.md)). Flanged heads have no ISO standard for
a flanged socket cap, so their spec cites none.

### Nut specs

`spec/nut/<thread>-<type>[-thin|-regular]` (category "nut"): `thread`
("M3"; a fine thread as "M5x0.5"), `type` and, where a standard fixes
them, `across_flats_mm`, `height_mm` and `standards`. Types:

- `hex`: plain hex nut. `profile` regular (DIN 934 / ISO 4032) or thin
  (jam nut, DIN 439 B / ISO 4035); without `profile` the height is not stated.
- `nylon-lock`: nylon insert lock nut (nyloc, nylstop). `profile` thin is
  the low form DIN 985 / ISO 10511, regular the high form DIN 982 / ISO
  7040; without `profile` the height is not stated.
- `metal-lock`: all-metal prevailing-torque lock nut (deformed or oval top,
  "stover"), ISO 7042 / DIN 980.
- `lock`: a lock nut whose brand does not say how it locks. Never read as
  nylon without the brand's word for it.
- `flanged`, `flanged-lock` (locking kind not stated), `flanged-nylon-lock`,
  `serrated-flange` (the serrations bite and lock the nut),
  `serrated-flange-nylon-lock`.
- `dome` and `flanged-dome` (acorn or cap nut), `square`, `knurled` (thumb
  nut), `wing`, and `wheel` (a wheel nut whose name gives the thread but
  not its shape; a 17 mm hex is in the id: `m12x1-wheel-17mm`).

A big-bore wheel nut (1/8 and 1/5 scale: M12 or M12x1, a 17 mm or 24 mm
wrench hex) is a wheel nut in shape too: the hex sits outside the wheel, and
a long threaded collar protrudes from it into the wheel's hex bore, often
with a flange or serrations and sometimes a closed cap. Length and collar
dimensions are recorded only where the maker states them; none are invented.
Standard serrated flange and flanged lock nuts of smaller cars link to the
generic nut specs.

`profile` is only on hex and lock nuts. The across flats is on the spec
only where the ISO/DIN tables fix it for that type and size (M3: 5.5 mm,
M4: 7 mm); flanged nuts get none, because flange and hex vary between
brands. The notes name the standard and give the standard heights per
size. Parts link "functional" (thread and type from the name), or "exact"
when the brand cites the standard (Wedico's "STOPPMUTTER M3 DIN 985").
Special nuts (shock, servo saver, clutch, flywheel, diff, ball and
adjusting nuts, splined or brand-specific wheel nuts) get no nut spec.

```toml
id = "spec/nut/m3-nylon-lock-thin"
category = "nut"
name = "M3 thin nylon insert lock nut"
thread = "M3"
type = "nylon-lock"
profile = "thin"
across_flats_mm = 5.5
standards = ["DIN 985", "ISO 10511"]
```

### Wheel hex specs

`spec/wheel-hex/<size>mm` (category "wheel-hex", `hex_mm`) is the hex a wheel
mounts on. Wheels and wheel hexes link to it: match "exact" when the part's
name states the size ("WITH 12MM HEX"), "close" when the wheels of a release
take the size of that release's wheel hexes (the notes say which release).
Other mounts (pin drive, centre lock) are not modelled yet.

## Makes

`data/makes/<slug>.toml`: one record per real vehicle make that a release or
body shell depicts (`depicts.make`, below). The make list is curated in
`VEHICLE_MAKES` in tools/validate.py, and the validator requires one file per
entry. `name` is the make as it spells itself and must be an entry of that
list; `id` is `make/` and the site's slug of the name (`make/mercedes-benz`,
`make/land-rover`). The site's make page shows `notes` and `country`.

- `country`: ISO 3166-1 alpha-2 code of the make's home country, the country
  it is from (Ducati: IT, though Audi owns it).
- `notes`: one or two plain sentences on what the make is and builds. No
  founding years or other dates unless a source states them, and no marketing
  words. The validator rejects a year.

```toml
id = "make/bmw"
name = "BMW"
country = "DE"
notes = "German maker of cars and motorcycles, based in Munich."
```

## category

`data/categories/<slug>.toml`: the part categories. A part's `category` must be
one of them. `name` is the label; `summary` is a one-line description for the
category overview (a few words, no full stop); `description` is the longer text
shown on the category's own page; `spec_type` names the generic spec type the
category's parts link to; `key_fields` are the properties that matter when
choosing such a part, in display order, each read from the part itself or from
its linked spec (`from = "part" | "spec"`), with an optional `unit` and
`format` ("cells": a [min, max] LiPo range shown as 1-3S; "range": a [min, max] shown as 4000-45000; "volts": a voltage shown as 6 V, or a list of them as 6/7.4 V; "yesno": true or false). `compare_only = true`
keeps a field out of the parts table and shows it only when parts are
compared side by side.

`any_car = true` (optional) marks a category whose parts are not made for one
car: tools, radios, chargers, batteries, motors, ESCs, servos, wires, lights,
paint, engine parts and generic hardware (screws, nuts, bearings, pins, clips,
pinions). Such a part with no `fits` row and no release naming it is not
counted as unlinked: the audit check part-no-car-link and the Linked column of
the statistics page leave it out of the denominator. A part that names the model it is for (`applies_to`) is always counted, whatever its
category. A part of such a category
that does have a fits row or a release is linked as before. Leave the flag off
for a category whose parts belong to a car (arms, hubs, chassis plates, bodies,
wheels, tyres).

```toml
id = "category/servo"
name = "Servos"
spec_type = "servo"
key_fields = [
  { field = "size_class", label = "Size", from = "spec" },
  { field = "torque_kgcm", label = "Torque", from = "part", unit = "kg·cm" },
]
```

### Wire specs

`spec/wire/<n>awg` (category "wire"): one AWG gauge from 8 to 30 (`awg`), its
nominal solid round copper conductor (`conductor_mm`, the diameter,
`conductor_in`, the same in inches, and `cross_section_mm2`) from the AWG
formula of ASTM B258, which is defined in inches: 0.005 in x 92^((36 - n)/39)
(`standards = ["ASTM B258"]`, the standard's notes give the formula). Wire
parts with a gauge link to it with match "functional"; a lead with two gauges
links both. Only the gauge is in the spec: insulation and strands are the
part's own.

Part fields on wires (category wire; set by tools/link_wire_specs.py from the
maker's wording, never overwritten):
- `wire_awg`: the gauge (int, 4 to 32), or a list of two for a lead with two
  gauges ("12+14AWG").
- `insulation`: "silicone", "pvc" or "teflon", as the name says.
- `strands`: the strand count, when stated ("1000 strands").
- `length_mm`: the length the part is sold in. Inside brackets the first length
  wins, so a sensor cable "(200mm (7.9"))" is 200; a list of sizes without a
  bracketed one, or a sum "50+50mm", is no length.
- `color`: as on other parts (plain words; "red/black" for a pair, "fluorescent
  pink" with "fluorescence" in the name).

Heat shrink (category wire, name says heat shrink, shrink tube or
Schrumpfschlauch): `diameter_mm` (the supplied inner diameter; a list for an
assortment), `shrink_ratio` (the ratio as a number, 2:1 is 2), `flat_width_mm`
(a flat battery wrap, only when the name says flat) and `length_mm`. The site
shows "Shrinks to" as diameter / ratio, only when the ratio is stated.


## standard

`data/standards/<slug>.toml`: a published standard that specs cite in their
`standards` list, matched by `code`. `title` is the standard's own title,
`url` its public page (title, scope and edition; the text itself is sold),
`replaced_by` the standard that superseded a withdrawn one (DIN 912 -> ISO 4762).

```toml
id = "standard/din-912"
code = "DIN 912"
title = "Hexagon socket head cap screws"
replaced_by = "standard/iso-4762"
```

## doc

A manufacturer document used as a source. Only facts and the links; the PDF
itself is not stored in git (`file` is the name in the local `work/manuals/`
tree). `kind` is manual | part_list | exploded_view | supplement | catalog |
setup_sheet | product_page | news | video (see "Videos"). Two links: `page` is the maker's own web page
where the document is listed (the support or downloads page, stable and
readable), `url` the file itself as the maker serves it, which may be a CDN
(Tamiya's CloudFront) or the maker's own Drive or Dropbox share (Redcat,
Absima). Give `page` whenever the maker has one; a file uploaded by someone
else (a forum, a fan site, a shop's own copy) is never the `url`. The site
links the page first and the file as "PDF". `printed` (optional, `YYYY`, catalogue and manual documents with no `page` or `url` of their own): the year the document prints on its cover or copyright line. It bounds the `seen_by` of the parts it lists (`seen_by_source` is the document's id). The file is not linked from the parts. `gone` (optional, `YYYY-MM-DD`) is the date the file behind `url` was found no longer to exist (a Drive file deleted or trashed by the maker): `url` is then removed with it, the page stays, and the site shows no PDF. `manual_no` (optional) is the maker's manual number as the file prints it in its footer (Tamiya: "(11053802)"), kept per file because a reprint may print another number. A setup_sheet is a maker's setup sheet (blank
or a driver's setup for a track) or a setup reference chart (gear ratios,
toe angles), linked to the releases of the car it is for.

A `product_page` is the maker's own page for the release. A shop's page of the maker's product (a dealer, distributor or retailer) is a `catalog` document, never a `product_page`: a release that has no maker page may link that shop page as a release link of kind `dealer`.

A `news` document is one dated post or press release on the maker's own site
(news page, blog, newsroom) that announces releases as new or available:
`page` is the post, `date` the date the post states, `releases` the releases
it names. A release takes its `released` from the post's date (or the date
or month the post itself gives) only when the post says the item is new,
out or available; a "coming soon" or pre-order post dates an announced
release as planned, never a released one. A post on a news site that reprints
the maker's text is not a maker document.

```toml
id = "doc/traxxas/news-2024-03-12-new-slash"
brand = "brand/traxxas"
kind = "news"
title = "Traxxas news: the new Slash 2WD is here"
date = "2024-03-12"
publisher = "brand/traxxas"
page = "https://traxxas.com/news/..."
releases = ["release/traxxas/58076-74"]
```

```toml
id = "doc/xray/xb2-2026-part-list"
brand = "brand/xray"
kind = "part_list"
title = "XRAY XB2'26 spare parts list"
version = "25.01"
date = "2025-10-21"
publisher = "brand/xray"
page = "https://www.teamxray.com/teamxray/support/manuals/xb2-26"
url = "https://www.teamxray.com/downloads/xb2-26-part-list.pdf"
file = "xb2-2026-part-list.pdf"
releases = ["release/xray/320020", "release/xray/320021"]
```

## Videos

A maker's own video about a kit, release or part, from the maker's
official YouTube channel (never a fan's or a shop's channel), is a document
of kind `video` under the brand of what it shows. Only facts about the
video are kept: its title as the channel gives it, the channel's name, the
day it was published when a source states it, its length when known, and
its link. Nothing of the video is stored; the site shows YouTube's own
thumbnail from i.ytimg.com next to the link.

```toml
id = "doc/arrma/youtube-abcDEF12345"
brand = "brand/arrma"
kind = "video"
title = "ARRMA KRATON 6S BLX EXB RTR"
channel = "ARRMA RC"                      # the YouTube channel's name
date = "2024-05-02"                       # optional: when published
duration_s = 154                          # optional: the length in seconds
publisher = "brand/arrma"
url = "https://www.youtube.com/watch?v=abcDEF12345"
page = "https://www.horizonhobby.com/product/..."   # the maker's page that embeds it, when found there
releases = ["release/arrma/ara8707"]
kits = ["kit/arrma/kraton-6s"]            # a video of the whole kit (no one release named)
parts = ["part/arrma/ARA390290"]          # a video of a part
```

The id is `doc/<brand>/youtube-<video id>`, the `url` exactly
`https://www.youtube.com/watch?v=<video id>`. A video is linked only where
it is certain: from the maker's product page that embeds it (that page's
release), or from its title when the title names the kit or release
strictly (the matching of tools/car_releases.py: a TT-02 Type-S video only
on that release). A video that names no car is not kept.

## Owner reports

Knowledge that exists in no manufacturer document, such as two cars being the
same, parts that fit although no brand says so, or a known weak part, is
recorded as a document of kind `owner_report` under
`data/documents/community/`, and cited as the `source` like any manual. It
keeps who reported it, when, on what basis, and the statement in their words.

```toml
id = "doc/community/2026-10-09-quanum-vandal-is-ftx-vantage"
kind = "owner_report"
title = "Quanum Vandal is a rebranded FTX Vantage"
date = "2026-10-09"
reported_by = "francisdb"
statement = "The FTX Vantage and the Quanum Vandal are the same car; ..."
basis = "Owner of both cars"
```

## Art

A kit or release may have an outline of its own: a flat silhouette traced
from the maker's photos, drawn by us.

```
art/kits/<brand>/<slug>.svg         for kit/<brand>/<slug>
art/releases/<brand>/<key>.svg      for release/<brand>/<key>
art/parts/<brand>/<number>.svg      for part/<brand>/<number> of category body
```

A body part (category `body`, a shell or a painted body) may have art of its
own, the car it shows as an outline; no other part may. The file name is the
id's last part, as for kits and releases.

The file name is the id's last part exactly (same case). Each file is one line:

```
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 24"><path d="M..."/></svg>
```

One or more `<path>` elements with only a `d` that starts with an absolute
`M`; no fill, style, class, transform or title, at most 4 KB. The front of
the car faces left. The site sets the fill from the release's colours.

The export gives such a kit or release `art`: the path data of its file
(the `d` attributes joined with a space), to be drawn in a `0 0 48 24`
viewBox. The site draws a release with its own art, else the kit type's icon; it
never borrows the kit's or another release's, which may show another car.
A body part with art shows it on its part page.
Releases of one body (colour, kit/RTR and equipment variants) each carry
the same file.

## sources

`sources` (optional, on a kit, release or part): an inline table of the page each fact came from, when that page is not the record's main source: a fan site such as TamiyaBase, or a download page whose title gives a name. Keys are the record's own field names (`name`, `category`, `kind`, `kit`, `scale`, `drive` ...), each present on the record; values are https URLs. Dates are not keys: `released`, `announced`, `year`, `model_year`, `seen_by` and the brand's dates keep their own `*_source` fields. Set a key only for a value the page gave; the notes say where the rest came from.

```toml
sources = { name = "https://www.tamiyabase.com/downloads/download-categories/download/32-46xxx-quick-drive-qd-series-pdf/88122-manual-46015", kind = "https://www.tamiyabase.com/tamiya-models/46015" }
```

The site shows a small source note next to each sourced fact, labelled with the host ("TamiyaBase", else the maker's host) and linked to the URL.

## Conventions

- Brand attribution of HUDY items inside XRAY lists is a heuristic in the
  importer (name starts with HUDY, or number in the 1xxxxx/2xxxxx HUDY ranges).
- Dates are ISO `YYYY-MM-DD`. Document dates come from the PDF metadata.
- No prices, stock, images or copied text. (The outlines in art/ are our own
  drawings, not the maker's images.)

## Tools

Public, in `tools/`:

```
python3 -I tools/validate.py               # checks everything under data/ (runs in CI)
python3 -I tools/export.py [out.json]      # one JSON export for the website build
```

The importers that generate parts and release contents from manufacturer PDFs
are not published. They live with the downloaded manuals in the local `work/`
tree. Generated fields are identified by the `source` on each `contains` row
and by the document records, so a regenerated file can be checked against the
named document.
