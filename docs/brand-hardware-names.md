# Brand hardware names

What a screw's name abbreviation means, per brand, and the spec head and
drive it links to. The table is the same one tools/hardware_codes.py uses
(hobbydex-tools), so the linkers and this page cannot disagree; regenerate
with `python3 -I tools/hardware_codes.py --markdown`.

Status: `stated` means a document of the brand (cached manual, parts list,
product page, or a decision recorded in hobbydex-tools docs/decisions.md)
says it. `inferred` means no cached document states it: the meaning rests on
the shape, the part-number family or the brand's usage, as the source says.
A name with no code in this table gets no head from the code, and so no
spec link; the linkers never guess one.

## XRAY and HUDY

XRAY does not publish a legend of its hardware codes. The meanings come from
its manuals and parts lists, where the same screw appears under a code and a
spelled-out name, or where the manual text names the screw beside the code:

- SB is a set screw (headless): the XB8E 2026 manual says "Setscrew is
  preassembled" beside SB M3x4 and "Loosen the 3x5mm setscrew" beside SB M3x5.
- SFH is flat head, countersunk: part 903305 "HEX SCREW SFH M3x5" is the same
  part as 903305-T "HUDY TITANIUM FLAT HEAD SCREW M3x5".
- SH and "SOCKET HEAD CAP" name the same hex socket cap screws (902312 and
  908312 are the same size in the same lists); SCH is written for it in the
  XB8E 2026 manual.
- FLANGED SH and FLANGED SHF are flanged socket heads (911xxx). The XRAY page
  prod_id=4987 states the black colour; that page is not in the cache yet.
- Part numbers 901xxx are SB, 902xxx SH, 903xxx SFH, 908xxx socket head cap
  or, with a -T suffix, the Hudy super-low head (centering diameter).

WASHER S (e.g. "WASHER S 3x6x0.2") is a washer series; no document states
what the S means, so the washer linker reads the dimensions only.

## Tamiya

The screw convention is the one recorded in hobbydex-tools docs/decisions.md:
a plain Screw is a pan head with a JIS cross recess, Tapping Screw is a
self-tapping pan head, Countersunk is countersunk, Binding Head is truss,
Cap Screw is socket cap, Grub is set. Tamiya's hex screws name their drive.

## Traxxas

The cached parts lists write CS for a countersunk (flat head) screw with a
hex drive ("4859 CS 3x10 flathead (hex drive)"). BCS, CCS and SS are not
defined in the cached text; they are read as button cap, cap and set screw
(the brief's reading) and marked inferred until the exploded views are read.

## Kyosho

Kyosho's javelin spare-parts list (cache notes/kyosho/ocr) names its screws
in full: Button Screw (Hex/M3x10), Cap Screw (M2.6x8), Flat Head Screw
(Hex/M2.6x6), Round Screw, Bind Screw, Set Screw. Its item numbers carry the
kind: 1-S screws, 1-N nuts, 1-W washers (inferred from the number next to the
name). TP marks a self-tapping screw (inferred from the brief; not defined in
the cached text). Kyosho states "Hex" in its names; no cached Kyosho text
states a JIS or Phillips cross recess, so a Kyosho screw without "Hex" in
its name gets no drive.

## Flanged heads

A flange under the head is its own spec head: flanged-socket-cap,
flanged-button, flanged-pan (spec/screw/m3x12-flanged-socket-cap-hex). No ISO
standard is cited for a flanged socket cap; flanged heads cite none. Flanged
countersunk, flanged low-head and flanged set screws are not linked.

## Table

| brand | code | meaning | spec head | source | status |
|---|---|---|---|---|---|
| any | SFH, FHS, FH, flat head | flat head, countersunk (sunk into the part) | countersunk | XRAY: 903305 'HEX SCREW SFH M3x5' is 903305-T 'HUDY TITANIUM FLAT HEAD SCREW M3x5' (xb4-2026-part-list, xb8e-2026-part-list); 'HEX SCREW FLAT HEAD CAP FHS M4x10' (xb8e-2026 part list). XRAY 913203 '110 SFH M2x3' (xb2-2026-part-list) is the 110 degree countersink | stated |
| any | BH, BHCS, SBH, button head | button head (domed top) | button | Kyosho javelin parts list: 'Button Screw(Hex/M3x10)' (cache notes/kyosho/ocr/30618-javelin-spare-and-option-parts-4-R.txt); Redcat 'B-Head' | stated |
| any | SH, SCH, SHCS, CAP, cap head | socket head cap screw, hex socket | socket-cap | XRAY: 'HEX SCREW SOCKET HEAD CAP SCH M3x12' in xb8e-2026-manual; SH and SOCKET HEAD CAP name the same sizes (902312 vs 908312) | stated |
| any | LH, LHCS, low head | low head cap screw (flat top, DIN 7984) | low-head | XRAY/HUDY: 'Titanium Super-Low Head Screw Centering Dia' (HUDY 908xxx-T, xb4-2026-part-list) | stated |
| any | SB, set screw, grub | set screw (grub, headless) | set | XRAY: xb8e-2026-manual 'Setscrew is preassembled' beside SB M3x4, 'Tighten setscrew onto gear flat spot' beside SB M5x4, 'Loosen the 3x5mm setscrew' beside SB M3x5. Kyosho 'Set Screw Set'. Tamiya decision: Grub = set (docs/decisions.md) | stated |
| kyosho | TP Round Screw | pan head (round top) screw, Kyosho's name | pan | Kyosho javelin parts list 'TP Round Screw(M3x8)' (cache notes/kyosho/ocr/30618-javelin-spare-and-option-parts-4-R.txt) | stated |
| kyosho | Bind Screw | binding head (Tamiya: Binding Head = truss) | truss | Kyosho data names 'Bind Screw(M3x16)', 'TP Bind Screw(M2.6x8)'; the brief names it binding head; Tamiya decision maps Binding Head to truss | inferred |
| tamiya | Cap Screw | Tamiya: Cap Screw = socket cap | socket-cap | docs/decisions.md (Tamiya screw convention) | stated |
| tamiya | Binding Head | Tamiya: Binding Head = truss | truss | docs/decisions.md (Tamiya screw convention); Tamiya '2.6x5mm Truss Screw' | stated |
| tamiya | Screw (no hex, no screw pin) | Tamiya: a plain Screw = pan head, JIS cross recess | pan | docs/decisions.md (Tamiya screw convention) | stated |
| traxxas | CCS | cap screw (Traxxas CCS), head shape not drawn in cache | socket-cap | Traxxas parts lists '3x8mm CCS (stainless)'; the brief's reading cap/button/countersunk/set | inferred |
| traxxas | BCS | button cap screw (Traxxas BCS) | button | Traxxas parts lists '3x15mm BCS (with threadlock)'; the brief's reading; exploded views not read | inferred |
| traxxas | CS | countersunk (flat head), hex drive | countersunk | Traxxas parts list '4859 CS 3x10 flathead (hex drive)' beside 'Screws, 3x10mm countersunk machine (hex drive)' | stated |
| traxxas | SS | set screw (Traxxas SS), hex drive | set | Traxxas parts list '3x12 SS (hex drive)'; the brief's reading | inferred |
| xray | SFH (Hudy names) | Hudy 'Titanium Flat Head Screw' = XRAY SFH | countersunk | XRAY part list 903305-T (xb4-2026-part-list) | stated |
| any | flanged head (FLANGED SH, SHF, flanged cap/button) | flanged head: the plain head plus a flange under it; spec head flanged-socket-cap, flanged-button or flanged-pan; no ISO standard for a flanged socket cap | flanged-* | XRAY: 'HEX SCREW FLANGED SH M3x12' and 'FLANGED SHF M3x12' (xb8e-2026-part-list, 911312); user-confirmed XRAY page prod_id=4987 (black) | stated |

