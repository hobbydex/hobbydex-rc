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
| release | `data/releases/<brand>/<number-or-slug>.toml` | id, kit, brand, name, kind, status (`year` optional: left out when unknown) |
| part | `data/parts/<brand>/<prefix>/<number>.toml` | id, brand, number (unless the brand has `item_numbers = false`), name |
| doc | `data/documents/<brand>/<slug>.toml` | id, kind, title |
| spec | `data/specs/<category>/<slug>.toml` | id, category |
| category | `data/categories/<slug>.toml` | id, name |
| shop | `data/shops/<country>/<slug>.toml` | id, name, status (not used yet) |

`<prefix>` is the first two characters of the part number, so that no directory
holds more than a few hundred files (GitHub lists at most 1000). Changing the
layout later means editing `layout.py` and moving files; ids do not change.


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
kind = "manufacturer"                    # manufacturer | aftermarket | designer | retailer
status = "active"                        # active | dormant | gone
notes = "..."
```

`item_numbers = false` marks a maker that prints no item numbers (Acer
Racing): its parts leave out `number`, and the id's last segment is a slug
from the source (the store's product handle) instead. The site then shows no
number and builds the part URL from that slug. Left out, it means true and
every part of the brand needs a `number`.

## kit

A model line, independent of year or edition. `category` is the kit type:
buggy | truggy | stadium-truck | short-course | monster | desert-truck |
truck | race-truck | crawler | touring | formula | pan-car | rally |
street-basher | drift | drag | lowrider | oval | speed-run | kart | motorcycle |
tank | construction | trailer | boat, or car for a car that fits none of
them. trailer is a standalone trailer or dolly, with no `drive` or `power`
(a truck sold with its trailer stays truck). drag is a straight-line drag
racer (no prep drag cars, drag trucks); lowrider a
hopping lowrider on hydraulics or servo-lifted suspension. `scale` as "1/10".
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

## release

One sold product: a yearly edition, a Carpet or Dirt version, an RTR, a
re-release. Keyed by manufacturer item number when there is one, otherwise by a
slug (`xb4-2013`, `xb8e-2021`). `kind` is kit | rtr | arr. `status` is
announced | released | discontinued.

`color` (optional) is the colour the release is sold in, in plain words from the same palette as a part's `color` ("red"; two or three colours as "blue/black", "green/black/white"), read from the name's colour clause by link_release_colours.py; left out when the name names none.

`category` (optional) overrides the kit's type for this release, where a car on a shared chassis is another type than the chassis kit: Tamiya's race trucks are releases of the TT-01 Type-E kit (a touring car) with category "race-truck".

`year` is the calendar year the release came out, only from a dated source. `model_year` is the year in the maker's edition name when the maker names editions by model year (XRAY's XB2'26 is on sale from late 2025): it is not a release year, and a release can be on sale before its model year.

`requires` (a release that is not a car on its own: a conversion or upgrade kit): the cars it needs, as kit or release ids, any one of which completes it, from the maker's wording ("a 1RC Racing 1/18 Sprint Car (1RC1095, 1RC1096 or 1RC1097) is required"). A release id when the maker names item numbers, else the kit. The site shows "Needs" on the release and, on the base kit and release, the conversion kits made for it.

`surface` (race kits only): the track surface the maker built this version for, as a list of carpet | astro | clay | dirt | asphalt | high-grip, when the maker sells surface-specific versions or says what the car is for ("Carpet Edition", "for clay tracks"). Set only from the maker's own wording, never guessed from the car type; on a kit when the whole line is for one surface.

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

`year` is the year the release came out. Leave it out when it is unknown: a
document's date (a later scan, a reprinted manual) or the day a shop was read
is not a release year. The site shows such releases as year unknown and leaves
them out of the by-date lists.

`released`: the release date as precise as a source states it, `YYYY-MM-DD`
or `YYYY-MM` (Tamiya's monthly new-items list gives the month; a full date
from another source in that month is kept). It must agree with `year`. Never
a document's date. For an announced release it is the planned date.

`released_source`: set only when the date comes from a fan site rather than
the maker; `"TamiyaBase"` for a Tamiya release dated from TamiyaBase (its
owner allowed it) when Tamiya's own pages give no first-release day, with the
model's TamiyaBase link in `links` (kind `fan-site`). The maker's own date
wins when both exist.

## part

A branded, numbered product. `number` is exactly as the manufacturer prints it,
including variant suffixes (`368014-S`, `362280-K`). `name` is the description
from the newest source, verbatim apart from trademark glyphs and quote
normalisation; the trailing pack count `(10)` is moved into `pack_qty`. Older
differing descriptions go to `former_names` so a rename or a spec change
(`PIN 2x10` to `PIN 2x9.8` under the same number) stays visible.

```toml
id = "part/xray/362250"
brand = "brand/xray"
number = "362250"
name = "COMPOSITE STEERING BLOCK - MEDIUM - V2"
pack_qty = 2
former_names = ["COMPOSITE STEERING BLOCK"]
```

A part of a brand with `item_numbers = false` has no `number`: never put a
store handle or SKU there to fill it. Its id keeps a slug
(`part/acer-racing/bandit-ball-bearing-kit`), which also names its file.

Optional, generated when the source states it: `released`, the date the
brand lists the part as released, `YYYY-MM-DD` or `YYYY-MM` (HUDY's product
list gives a day per item, Tamiya's monthly new-items list a month),
and `applies_to`, the models the
brand lists the part for, verbatim (TLR writes "Description (pack): 22X-4 2.0").

`category`: what kind of part it is, one of the categories in `data/categories` (see category below): `ball-end`, `battery`, `bearing`, `body`, `bumper-guard`, `charger`, `chassis`, `decal`, `differential`, `drivetrain`, `electronics`, `engine-fuel`, `gear`, `glue`, `manual`, `motor`, `nut`, `o-ring-seal`, `oil-grease`, `paint`, `parts-tree`, `pin-clip`, `pinion`, `screw`, `servo`, `shock`, `shock-spring`, `spur-gear`, `steering`, `suspension`, `tire`, `tool`, `washer-shim`, `wheel`, `wing`. It is derived
from the name by a classifier and recomputed when the rules improve; set
`category_source = "curated"` to fix a category by hand. Parts named only by
number have none.

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
`thread_type` (machine | self-tapping), for shocks `shock_part` (complete | body |
shaft | piston | cap | rebuild-kit | rod-end | spring-cup), `length_mm`, `bore_mm`
and `shaft_mm` (shaft diameter), `name_source` (`ocr`: the name was read by OCR from a scanned document and not checked yet; `manufacturer`: corrected from the manufacturer's own product page), `range` (colour versions of one part share a range ending in `-colours`, e.g. "team-corally/c-00180-1055-colours" for a body in clear and four painted colours, set by tools/link_colour_variants.py; tools/link_part_colours.py then gives each version its `color` in plain words when the name states one colour of the part itself ("(blue-anodized)" -> "blue"); otherwise a shared id such as "rc4wd/540-crawler-brushed-motor" for the
parts of one product range that differ only in wind, kV or a similar rating;
the site lists the other versions on each part page), for ball studs and ball cups `ball_mm` (the ball
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

`documents`: the part's own documents, such as a radio's user manual. Radios
and receivers also carry `channels` and `protocol` (AFHDS 3, ANT, DSMR) and
`weight_g`; their model code is the part number (FS-NB4+, so a number may
contain `+`).

`radio_unit` says what a radio part is: `transmitter` (the transmitter as the
maker lists it, with no receiver named as part of it), `receiver` (a
receiver, also an ESC or a car's control board with a receiver built in) or
`set` (a transmitter sold with its receiver under one number). On a
transmitter or a set, `dimensions_mm` and `weight_g` are the transmitter's;
on a receiver they are the receiver's. A set lists its receiver in
`includes` when the receiver is a part of its own; when it is not, the
receiver's size and weight go in `notes` as "Receiver: 35 x 21 x 12 mm,
11 g". The field is left out where the maker does not make clear what the
part is. tools/validate.py checks the values and that the part is in
category electronics.

`gtin`: the product barcode (UPC-A, EAN-13 or another GTIN) as a string of
digits, as printed by the brand; the validator checks length and check digit.
Releases can carry a `gtin` too, the barcode on the kit's box.

`links`: pages about this part, release or kit elsewhere, as `{ site, url }`
(https only); the site shows them as buttons next to the web search.
`kind = "fan-site"` marks a link to a fan or community site (such as
TamiyaBase): it is a courtesy link for readers, not a source for any value in
Hobbydex, and the site shows it apart from the brand's own pages.

```toml
links = [{ site = "TamiyaBase", url = "https://www.tamiyabase.com/parts/13934-10004255", kind = "fan-site" }]
```

Planned: `numbers` (aliases such as Tamiya's 7-digit spare number, 8-digit SKU
and X-number for one part).

`rebrand_of`: the part this one is the same product as under another brand
(a radio HobbyKing sold as Turnigy), with a `source` or `notes`. Recorded once,
on the rebranded part; the site shows it from both sides.

```toml
rebrand_of = [{ part = "part/flysky/FS-GT5", source = "doc/community/2026-10-10-turnigy-gt5-is-flysky-gt5" }]
```

`name_de`: the brand's German name, kept when `name` is an English translation of it (ScaleART kit names, translated with a fixed glossary).

`name_ja`: the brand's Japanese name, kept when the English `name` is a
translation (Yokomo publishes Japanese-only parts lists).

`related`: other parts of the same brand this part goes with, as the brand's
name or page says: `[{ part, relation }]` with relation requires (needs the
other part: Tekno "requires TKR9057B"), fits (made to fit that part: Corally
"fits part C-00180-022"), use-with, for (an accessory made for it: HUDY
"Ejector for 106000"), replaces or same-colour (a paint the brand's own colour
matching list gives as the same colour in another range, though the shade
may differ slightly: Tamiya LP-1 Black, X-1 Black and TS-14 Black; recorded
on each of the paints). Others are recorded on the citing part; the site
shows it from both sides. tools/link_part_refs.py reads them from names.

`supersedes`: the part this one replaces, when the brand has replaced it with
an upgraded version (`supersedes = "part/team-corally/C-00180-194"` on
C-00180-714). The site shows it on both parts.

## spec

A generic, brand-independent specification. Category-specific fields; for
screws: `thread`, `length_mm`, `head` (countersunk | socket-cap | button |
pan | ...), `drive` (hex | torx | phillips | jis | slot; jis is the JIS B 1012 cross recess Tamiya uses, which takes a JIS driver, not a Phillips one), `standards`. No material:
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

Oils: `base` (silicone) and `viscosity_cst`; id `spec/oil/silicone-350cst`.

Pinions: the meshing geometry, `teeth` and either `pitch_dp` (diametral
pitch, 48) or `module` (0.5, 1); id `spec/pinion/48dp-20t` or
`spec/pinion/mod0.5-20t`. The bore is on the part (`bore_mm`), with the
material, because one geometry is sold for several shaft sizes and brands
often leave the bore out.

Spur gears carry `teeth` and either `pitch_dp` or `module` on the part
itself, read from the name. They get no generic spec: spurs of one
pitch and tooth count mesh the same pinions but mount differently.

Chargers are parts with category charger and, when stated, `power_w`.

Batteries: the electrical group, `chemistry` (lipo | lihv | life | nimh),
`cells`, `capacity_mah` and `nominal_v`; id `spec/battery/lipo-2s-5000mah`.
Whether a pack fits a car depends on the part's `c_rating`, `case` (hard |
soft | shorty), `dimensions_mm` ([length, width, height]), `weight_g` and
`connector` (XT60, EC5, Deans, ...), so those stay on the part.

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
`fits` and carry no `motor_can_mm`. Category electronics (or chassis for a
fan mount), set by tools/link_heatsinks.py in hobbydex-tools.

```toml
name = "Alu Dual Motor Fan Mount Dia 42mm (2x30mm / 2x40mm)"
category = "chassis"
motor_can_mm = 42
```

ESCs are parts with category electronics and, when stated, `current_a` and
`peak_current_a` (continuous and burst amps), `lipo_cells`, `dimensions_mm`,
`weight_g` and `sensored` (true when the ESC has a sensor port and runs
sensored motors, false when it is sensorless only). A motor and ESC combo lists its components with `includes`.

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

```toml
name = "1/10 Jeep Gladiator Rubicon Hard Body Kit"
category = "body"
scale = "1/10"
wheelbase_mm = 313
width_mm = 193
```

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
king, roll and spring pins and grooved or threaded pins get no pin spec.

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

```toml
id = "spec/washer/3x6x0.5"
category = "washer"
name = "3x6x0.5mm shim"
bore_mm = 3
outer_mm = 6
thickness_mm = 0.5
```

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

## category

`data/categories/<slug>.toml`: the part categories. A part's `category` must be
one of them. `name` is the label; `summary` is a one-line description for the
category overview (a few words, no full stop); `description` is the longer text
shown on the category's own page; `spec_type` names the generic spec type the
category's parts link to; `key_fields` are the properties that matter when
choosing such a part, in display order, each read from the part itself or from
its linked spec (`from = "part" | "spec"`), with an optional `unit` and
`format` ("cells": a [min, max] LiPo range shown as 1-3S; "range": a [min, max] shown as 4000-45000). `compare_only = true`
keeps a field out of the parts table and shows it only when parts are
compared side by side.

```toml
id = "category/servo"
name = "Servos"
spec_type = "servo"
key_fields = [
  { field = "size_class", label = "Size", from = "spec" },
  { field = "torque_kgcm", label = "Torque", from = "part", unit = "kg·cm" },
]
```

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
setup_sheet | product_page. Two links: `page` is the maker's own web page
where the document is listed (the support or downloads page, stable and
readable), `url` the file itself as the maker serves it, which may be a CDN
(Tamiya's CloudFront) or the maker's own Drive or Dropbox share (Redcat,
Absima). Give `page` whenever the maker has one; a file uploaded by someone
else (a forum, a fan site, a shop's own copy) is never the `url`. The site
links the page first and the file as "PDF". A setup_sheet is a maker's setup sheet (blank
or a driver's setup for a track) or a setup reference chart (gear ratios,
toe angles), linked to the releases of the car it is for.

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
```

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
Releases of one body (colour, kit/RTR and equipment variants) each carry
the same file.

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
