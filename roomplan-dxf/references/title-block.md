# Sheet furniture: frames, title block, north arrow

`lib/dxf-emit.py` draws annotation groups around the plan when a title-block
payload is present (i.e. whenever `--no-frame` is not given):

| group | layer | colour | contents |
|---|---|---|---|
| sheet frames + title-block borders | `FRAME` | 8 | one frame rectangle per story, title-block outline, row separators, column divider |
| all sheet text | `TITLE` | 7 | 6 rows x 2 cells per sheet and the `N`/`N?` label |
| north symbol | `NORTH` | 7 | one circle + shaft + filled arrow head per sheet |

Plan geometry is copied verbatim (only translated when sheets are laid out side
by side); the sheet furniture is added **after** it and never moves, rotates or
re-labels a single room entity. Unit, transform and layer conventions of the
scan are untouched (`$INSUNITS = 6`, metres).

## Proportions

All sizes are fractions of the plan bounding box (`span` = its largest side):

| element | size | notes |
|---|---|---|
| frame margin | 5 % of `span` | around the plan |
| title block width | 40 % of the frame width | right-aligned to the frame |
| title block height | `rows x 1.6 x text height` (6 rows) | content driven, so the text always has room |
| text height | 1.6 % of `span` | nominal; reduced per cell when a value is too long |
| north circle radius | 5 % of `span` | centre 2.2 r from the frame's top-right corner |
| gap between story frames | 8 % of the widest frame width | horizontal, left-to-right order |

The title block is **not** placed over the plan: the frame is extended
downwards by one title-block height and upwards by a north-symbol strip, so
both strips are reserved space. This keeps a wide plan from colliding with its
own title block.

## One frame per story

| stories | result |
|---|---|
| 1 | one frame, one title block, one north arrow (unchanged behaviour) |
| **2+** | **one frame per story, side by side**, each with its own title block, its own "Kat" row and its own north arrow |
| 2+ with `--no-frame` | one common drawing, **no** furniture, entities overlapping, warning `roomplan.stories-not-separated` |

Layout rule for 2+ stories: sheets are placed left to right in ascending story
number; the horizontal gap between two frames is **8 % of the widest frame
width** (`FRAME_GAP_RATIO`); all sheets share one bottom line. Entities are
grouped by their `S<n>_*` layer and each frame contains only its own story's
entities — nothing is scaled, rotated or re-projected, the per-story geometry is
only translated.

The per-story information (story, label, entityCount, placed bbox, frame) is in
`manifest.stories` and `manifest.sheetFurniture.sheets`, and the layout in
`manifest.sheetLayout` (`mode: "per-story-sheets"`, `gapRatio: 0.08`,
`storiesSeparated: true`).

## Title block rows

| cell | source |
|---|---|
| Projekt | `--project`, else `meta.json` `name`, else the directory/file name |
| **Kat** | story of that sheet: `0` = Prizemlje, `1` = `1. kat`, `2` = `2. kat`, negative = Podrum (`Podrum (2)` for a second basement level) |
| Lokacija | `--place` → free text; else `--place-lookup` result; else `--geo` → `lat, lon` (4 decimals); else `location withheld` |
| Mjerilo | `--scale`, default `NTS` |
| Datum / list | scan date (`meta.json` `createdAt`) or today, plus `--sheet` (default `A-01`) |
| Nacrtao | `by <author>`; `--author`, default `ARCHIFEST` |

The scale is **text**. It defaults to `NTS` because a scan has no known plot
scale: the drawing is a model-space plan, not a paper layout, and printing it
at an assumed scale would be wrong. Passing `--scale 1:100` only *labels* the
sheet; nothing is rescaled, and the converter does not verify that the label
fits the paper.

The provenance/source note is **not drawn** on the sheet: it stays in the
manifest (`sourceNote`) so it cannot collide with the title block. The drawing
carries only project, story, location, scale, date/sheet and author.

### Text must stay inside its cell

Every cell text is fitted in this order (`fit_text()` in `dxf-emit.py`):

1. **nominal height, full text** — used when it fits;
2. **reduced height, full text** — down to 55 % of nominal (`MIN_TEXT_HEIGHT_RATIO`);
3. **truncation with `…`** — last resort, at the reduced height, keeping as
   many characters as fit.

The width estimate is `0.6 x text height` per character (`CHAR_WIDTH_RATIO`),
the same factor the self-test uses, and cell padding is `0.3 x text height`
on each side. A value is therefore **always one line** — a long project name is
never wrapped and never reaches the next cell: it is shrunk, and then
ellipsised (`Stambena zgrada s poslovnim prostorom u pri…`). Every drawn cell is
reported in the manifest with `cellX0/cellX1`, `textHeight`, `insert` and
`truncated`, so the rule is machine-checkable; the self-test asserts that no
cell text exceeds its cell (+5 % tolerance).

## North arrow

The arrow is drawn for every run. `degreesClockwiseFromDrawingUp` is a
**bearing in degrees clockwise from the drawing's up direction** (sheet +Y):
0 points up, 90 points right.

**Default formula (north-flip ON):**

```
sheetBearing = (alignmentOffset - heading) mod 360      // = 360 - heading + offset
```

`heading` is `orientation.orientation_degrees` from the scan or, failing that,
`headingDegrees` from `meta.json`. `alignmentOffset` is the rotation the
architectural-alignment matrix applies when the model frame is projected onto
the sheet (`atan2(m[0], -m[2]) - 90`).

`--no-north-flip` restores the previous formula,
`(180 - heading + alignmentOffset) mod 360`, which was **exactly 180° wrong**
on the real drawing this package was checked against: that scan (heading
42.352°, alignment offset 27.629°) produced **165.3°**, and the operator
confirmed on the drawing that the arrow must read **345.3°**. The 180° flip is
recorded in the manifest as `northArrow.flip180` and
`roomplan.north-flip-applied`, so the assumption is never silent and can be
reverted with one flag.

Behavioural contract:

- the arrow head always carries `N` when a bearing exists; `N?` only when no
  orientation value exists at all (drawn pointing up by convention);
- the arrow uses the heading **with or without `--geo`**: orientation is not a
  location, and `--geo` only governs coordinates;
- with 2+ stories every sheet gets its own arrow, all with the same bearing.

### Why the earlier 180° error was plausible

The vendor artefacts are ambiguous by construction: the vendor draws the `N`
letter at the **tail** of the needle, so measuring "where N is" and "where the
head points" differ by exactly 180°. On the vendor DXF checked here the head
points ~3.8° (essentially straight up) while the `N` letter sits ~183.8° away,
and the vendor rotates its own sheet so that north is up — so that sheet cannot
disambiguate the two formulas for our project at all. The operator's check on
the actual drawing is the authoritative evidence, which is why the flip is the
default and the legacy form is kept behind `--no-north-flip`.

Residual risk: the heading is project metadata, it carries no confidence value,
and an error of a few degrees cannot be excluded. The arrow is therefore
**always** marked `approx` in the manifest when it comes from `meta.json`, and
`roomplan.north-direction-approximate` is emitted. Do not read bearings off the
sheet for surveying.

## Location: `--place` and `--place-lookup`

`meta.json` carries no place name, so the `Lokacija` cell is resolved in this
order, and nothing else is ever attempted:

1. `--place "<text>"` — free text typed by the operator, highest priority,
   never geocoded, never verified (`roomplan.place-from-cli`);
2. `--place-lookup` — **one** reverse geocode of the scan coordinates through
   the **local Apple** helper `apple-location geocode --lat … --lng … --compact`
   (CoreLocation/MapKit); the result is `name`/`street` + `locality`
   (`roomplan.place-lookup-applied`, which states that the coordinates were
   sent to the Apple geocoder);
3. `--geo` → `lat, lon` (4 decimals);
4. `location withheld`.

**Public package: `--place-lookup` is opt-in (OFF by default).** The local
skill build enables it by default whenever coordinates exist and offers
`--no-place-lookup` to switch it off — that difference is deliberate and is
documented in each package. Either way:

- no third-party geocoding service is contacted, ever;
- a missing helper, a timeout or an unparsable answer yields
  `roomplan.place-lookup-unavailable` / `-failed` / `-no-coordinates` and falls
  back to coordinates or `location withheld` — a lookup can never abort a
  conversion (exit code stays 0);
- `apple-location` only exists in the Apple/iOS environment; on plain Linux
  the feature reports `unavailable` and the title block falls back.

## Manifest fields

```json
{
  "titleBlock": {"project": "...", "story": 0, "storyLabel": "Prizemlje",
                 "author": "ARCHIFEST", "drawnBy": "by ARCHIFEST",
                 "scaleText": "NTS", "date": "2026-08-06", "sheet": "A-01",
                 "locationText": "location withheld", "locationSource": "withheld",
                 "sourceNote": "...", "frame": true},
  "northArrow": {"label": "N", "described": "approx", "basis": "meta.headingDegrees",
                 "sourceHeadingDegrees": 42.35, "alignmentBearingOffsetDegrees": 27.6288,
                 "degreesClockwiseFromDrawingUp": 345.28, "source": "meta.json",
                 "flip180": true,
                 "formula": "sheetBearing = (alignmentBearingOffset - heading) mod 360",
                 "confidence": null, "approximate": true, "reasons": ["..."]},
  "stories": [{"story": 0, "label": "Prizemlje", "entityCount": 33,
               "bbox": [0.43, 0.0, 7.33, 8.6], "bboxSource": "sheet",
               "frame": [...], "layers": ["S0_DOOR", "..."]}],
  "sheetLayout": {"mode": "per-story-sheets", "sheetCount": 2, "gapRatio": 0.08,
                  "gap": 0.623, "storiesSeparated": true},
  "placeLookup": null,
  "sheetFurniture": {"frameBounds": [...], "titleBlockBounds": {...},
                     "northArrow": {"tip": [...]},
                     "sheets": [{"story": 0, "frame": [...], "bbox": [...],
                                 "titleBlock": {"cells": [{"key": "Projekt",
                                   "drawn": "...", "cellX0": 1.0, "cellX1": 2.0,
                                   "textHeight": 0.11, "insert": [1.03, -1.2],
                                   "truncated": false}]},
                                 "northArrow": {"...": "..."}}]}
}
```

`entityCount` counts geometry **and** sheet furniture; `geometryEntityCount`
counts only the scanned plan. With `--no-frame` the two are equal and
`titleBlock` is `null`.
