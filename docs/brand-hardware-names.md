# Brand hardware names

What a screw's name abbreviation means, per brand, and the spec head and
drive it links to. The table is the same one tools/hardware_codes.py uses
(hobbydex-tools), so the linkers and this page cannot disagree; regenerate
with `python3 -I tools/hardware_codes.py --markdown`.

Status: `stated` means a document of the brand (manual, parts list,
product page, or a decision recorded in hobbydex-tools docs/decisions.md)
says it. `inferred` means no document states it: the meaning rests on
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
  prod_id=4987 states the black colour; that page is not yet read.
- Part numbers 901xxx are SB, 902xxx SH, 903xxx SFH, 908xxx socket head cap
  or, with a -T suffix, the Hudy super-low head (centering diameter).

WASHER S (e.g. "WASHER S 3x6x0.2") is a washer series; no document states
what the S means, so the washer linker reads the dimensions only.

## Tamiya

The screw convention is the one recorded in hobbydex-tools docs/decisions.md:
a plain Screw is a pan head with a JIS cross recess, Tapping Screw is a
self-tapping pan head, Countersunk is countersunk, Binding Head is truss,
Cap Screw is socket cap, Grub is set. Tamiya's hex screws name their drive,
except Hex Head: a Hex Head screw (the manual's "Hex head tapping screw") is a
hexagon head with a JIS cross recess, so spec head hex and drive jis. No ISO
standard is cited for it. The head is stated by the TT-02 manual; the cross
recess is Tamiya's JIS convention, not drawn in the manual's side view.

## Traxxas

The Traxxas parts lists write CS for a countersunk (flat head) screw with a
hex drive ("4859 CS 3x10 flathead (hex drive)"). BCS, CCS and SS are not
defined in any document we hold; they are read as button cap, cap and set screw
(read from usage) and marked inferred until the exploded views are read.

## Kyosho

Kyosho's Javelin spare-parts list names its screws
in full: Button Screw (Hex/M3x10), Cap Screw (M2.6x8), Flat Head Screw
(Hex/M2.6x6), Round Screw, Bind Screw, Set Screw. Its item numbers carry the
kind: 1-S screws, 1-N nuts, 1-W washers (inferred from the number next to the
name). TP marks a self-tapping screw (inferred from usage; not defined in
the documents). Kyosho states "Hex" in its names; no Kyosho document
states a JIS or Phillips cross recess, so a Kyosho screw without "Hex" in
its name gets no drive.

For any brand: a cap or button head is a hex socket by definition (ISO 4762,
ISO 7380), so a name that says Cap Screw, Cap Head, Socket Head, Button Head,
Button Screw or SH/SCH/SHCS/BH/BHCS/SBH, flanged or not, gets the hex drive
without the word "Hex" (Kyosho "Cap Screw(M2.6x8)"; XRAY "FLANGED SH"). Flat head, round, pan, bind and truss
names without a drive word get none.
A set screw (grub, SB; ISO 4026-4029) is a hex socket too. Where a brand row
states the drive (LC Racing TM and KM "hex socket"; Traxxas CS and SS "hex
drive"), the hex spec applies without the word.

## LC Racing

LC Racing writes the head as a code in front of the size, with no other
word: "TM2.6X8mm", "KM2.6X6mm". Its manuals spell the code out in the
parts legend of each step, beside a drawing of the screw:

- TM is a round head (button) screw with a hex socket: "Round Head Screw
  TM2.6x10mm" (BHC-1 V2 manual), "Round Head Screw TM3x10mm" (PTG-2TC
  and LC10B5 manuals), "Round Head Screw TM 3.0x18mm" (EMB-SC manual),
  each drawn with a domed head and a hex socket.
- KM is a countersunk (flat head) screw with a hex socket: "Countersunk
  Screw KM2.6x6mm" and the same in the other manuals, drawn with a
  countersunk head and a hex socket. One label disagrees: the LC10B5
  manual writes "LCSK19 KM M3x16" on page 32 beside a drawn round head,
  where page 23 writes "LCSK19 TM M3x16" and LC Racing names LCSK19
  "Round Head Screw M3x16mm"; the drawing and the name agree with TM.
- KB (HM6081, 1.4x10mm, the diff case screws) is drawn as a countersunk
  screw with a cross recess, and the 2021 EMB-1/TG manual calls it
  "Countersunk screw 1.4x10mm"; no document shows whether its thread is a
  machine or a tapping thread, so it has no row and no spec link.
- CM is drawn as a socket cap screw with a hex socket (Chinese label: cup
  head), but the BHC-1 V2 manual's English label for CM3.0x20mm reads
  "Button Head Screw": no row until a document settles it.

## Flanged heads

A flange under the head is its own spec head: flanged-socket-cap,
flanged-button, flanged-pan (spec/screw/m3x12-flanged-socket-cap-hex). No ISO
standard is cited for a flanged socket cap; flanged heads cite none. Flanged
countersunk, flanged low-head and flanged set screws are not linked.

A pan head ("Pan head", ISO 7045) is a pan head for any brand. Its drive is read
from the name only ("hexagonal" or "hex" is hex; "cross" or "phillips" is
phillips), so a plain "Pan head screw" gets no link. "Binding head" and
"binder head" (a typo in some lists) are the truss head.

A name with both a set screw and a round head ("Round Head Down Stop Set Screw")
keeps the head its part already links (set or button); a new part reads the
round head as a button head.

## Table

| brand | code | meaning | spec head | source | status |
|---|---|---|---|---|---|
| any | SFH, FHS, FH, flat head | flat head, countersunk (sunk into the part) | countersunk | XRAY: 903305 'HEX SCREW SFH M3x5' is 903305-T 'HUDY TITANIUM FLAT HEAD SCREW M3x5' (xb4-2026-part-list, xb8e-2026-part-list); 'HEX SCREW FLAT HEAD CAP FHS M4x10' (xb8e-2026 part list). XRAY 913203 '110 SFH M2x3' (xb2-2026-part-list) is the 110 degree countersink | stated |
| any | BH, BHCS, SBH, button head | button head (domed top) | button | Kyosho javelin parts list: 'Button Screw(Hex/M3x10)' (Javelin spare parts); Redcat 'B-Head' | stated |
| any | SH, SCH, SHCS, CAP, cap head | socket head cap screw, hex socket | socket-cap | XRAY: 'HEX SCREW SOCKET HEAD CAP SCH M3x12' in xb8e-2026-manual; SH and SOCKET HEAD CAP name the same sizes (902312 vs 908312) | stated |
| any | LH, LHCS, low head | low head cap screw (flat top, DIN 7984) | low-head | XRAY/HUDY: 'Titanium Super-Low Head Screw Centering Dia' (HUDY 908xxx-T, xb4-2026-part-list) | stated |
| any | SB, set screw, grub | set screw (grub, headless) | set | XRAY: xb8e-2026-manual 'Setscrew is preassembled' beside SB M3x4, 'Tighten setscrew onto gear flat spot' beside SB M5x4, 'Loosen the 3x5mm setscrew' beside SB M3x5. Kyosho 'Set Screw Set'. Tamiya decision: Grub = set (docs/decisions.md) | stated |
| any | pan head | pan head (round top) screw; the name's drive only, no drive is read from the head | pan | generic head name (ISO 7045 pan head); no brand row states a drive for it | inferred |
| any | binding head (binder typo) | binding head (Tamiya: Binding Head = truss) | truss | Tamiya decision maps Binding Head to truss (docs/decisions.md); Kyosho's 'Binding Head' note; 'BINDER HEAD' in an HPI name read as the same word | inferred |
| kyosho | TP Round Screw | pan head (round top) screw, Kyosho's name | pan | Kyosho javelin parts list 'TP Round Screw(M3x8)' (Javelin spare parts) | stated |
| kyosho | Bind Screw | binding head (Tamiya: Binding Head = truss) | truss | Kyosho data names 'Bind Screw(M3x16)', 'TP Bind Screw(M2.6x8)'; Kyosho calls it binding head; Tamiya decision maps Binding Head to truss | inferred |
| tamiya | Cap Screw | Tamiya: Cap Screw = socket cap | socket-cap | docs/decisions.md (Tamiya screw convention) | stated |
| tamiya | Binding Head | Tamiya: Binding Head = truss | truss | docs/decisions.md (Tamiya screw convention); Tamiya '2.6x5mm Truss Screw' | stated |
| tamiya | Screw (no hex, no screw pin) | Tamiya: a plain Screw = pan head, JIS cross recess | pan | docs/decisions.md (Tamiya screw convention) | stated |
| tamiya | Hex Head | Tamiya: Hex Head = hexagon head with a JIS cross recess (the manual's 'Hex head tapping screw') | hex | TT-02 manual 300058570, parts page 23: '3x10mm Hex Head Tapping Screw (MB2 x10)', the side view draws a hexagon head; the cross recess is not drawn there (Tamiya JIS convention; user, 2026-10-23) | inferred |
| traxxas | CCS | cap screw (Traxxas CCS), head shape not drawn in the exploded views | socket-cap | Traxxas parts lists '3x8mm CCS (stainless)'; read from usage cap/button/countersunk/set | inferred |
| traxxas | BCS | button cap screw (Traxxas BCS) | button | Traxxas parts lists '3x15mm BCS (with threadlock)'; read from usage; exploded views not read | inferred |
| traxxas | CS | countersunk (flat head), hex drive | countersunk | Traxxas parts list '4859 CS 3x10 flathead (hex drive)' beside 'Screws, 3x10mm countersunk machine (hex drive)' | stated |
| traxxas | SS | set screw (Traxxas SS), hex drive | set | Traxxas parts list '3x12 SS (hex drive)'; read from usage | inferred |
| xray | SFH (Hudy names) | Hudy 'Titanium Flat Head Screw' = XRAY SFH | countersunk | XRAY part list 903305-T (xb4-2026-part-list) | stated |
| lc-racing | TM | round head (button) screw, hex socket | button | BHC-1 V2 manual p14 legend 'Round Head Screw TM2.6x10mm' beside a drawn domed head with a hex socket; the same legend and drawing for TM2.0x4, TM2.6x8, TM3.0x6 (pp15-24), the 1/10 manuals, PTG-2TC and LC10B5 ('Round Head Screw TM3x10mm', 'LCSK04 TM M3x10') and the EMB-SC manual ('Round Head Screw TM 3.0x18mm'); the 2021 EMB-1/TG manual names the L6041 screws 'Round head screw 2.6x10mm' where the parts list has TM2.6X10mm | stated |
| lc-racing | KM | countersunk (flat head) screw, hex socket | countersunk | BHC-1 V2 manual p14 legend 'Countersunk Screw KM2.6x6mm' beside a drawn countersunk head with a hex socket; the same for KM2.6x8, KM2.0x8, KM2.6x14 (pp12-24), the 1/10 manuals, PTG-2TC and LC10B5 ('Countersunk Screw KM3x10mm', 'LCSK09 KM M3x10') and the EMB-SC manual ('Countersunk Screw KM 2.6x8mm'); the 2021 EMB-1/TG manual names KM2.0X4mm 'Countersunk screw 2.0x4mm' | stated |
| any | flanged head (FLANGED SH, SHF, flanged cap/button) | flanged head: the plain head plus a flange under it; spec head flanged-socket-cap, flanged-button or flanged-pan; no ISO standard for a flanged socket cap | flanged-* | XRAY: 'HEX SCREW FLANGED SH M3x12' and 'FLANGED SHF M3x12' (xb8e-2026-part-list, 911312); user-confirmed XRAY page prod_id=4987 (black) | stated |

