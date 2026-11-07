# Sheet furniture: frame, title block, north arrow

`lib/dxf-emit.py` draws three annotation groups around the plan when a title
block payload is present (i.e. whenever `--no-frame` is not given):

| group | layer | colour | contents |
|---|---|---|---|
| sheet frame + title block borders | `FRAME` | 8 | frame rectangle, title-block outline, row separators, column divider |
| all sheet text | `TITLE` | 7 | 5 rows x 2 cells, the `N`/`N?` label, the source note |
| north symbol | `NORTH` | 7 | circle, shaft, filled arrow head |

Plan geometry is copied verbatim; the sheet furniture is added **after** it and
never moves, rotates or re-labels a single room entity. Unit, transform and
layer conventions of the scan are untouched (`$INSUNITS = 6`, metres).

## Proportions

All sizes are fractions of the plan bounding box (`span` = its largest side):

| element | size | notes |
|---|---|---|
| frame margin | 5 % of `span` | left/right/top of the plan |
| title block width | 40 % of the frame width | right-aligned to the frame |
| title block height | 8 % of the plan height nominal | grows to `rows x 1.6 x text height` so 5 rows stay legible (typically ~12–13 %) |
| text height | 1.6 % of `span` | inside the 1.5–2 % target |
| north circle radius | 5 % of `span` | centre 2.2 r from the frame's top-right corner |

The title block is **not** placed over the plan: the frame is extended
downwards by one title-block height, and upwards by a north-symbol strip, so
the two strips are reserved space. This keeps a wide plan from colliding with
its own title block — an earlier version drew it inside the plan bbox and
overlapped walls.

## Title block rows

| cell | source |
|---|---|
| Projekt | `--project`, else `meta.json` `name`, else the directory/file name |
| Lokacija | `--geo` → `lat, lon` (4 decimals), otherwise the literal `location withheld` |
| Mjerilo | `--scale`, default `NTS` |
| Datum / list | scan date (`meta.json` `createdAt`) or today, plus `--sheet` (default `A-01`) |
| Nacrtao | `by <author>`; `--author`, default `ARCHIFEST` |

The scale is **text**. It defaults to `NTS` because a scan has no known plot
scale: the drawing is a model-space plan, not a paper layout, and printing it
at an assumed scale would be wrong. Passing `--scale 1:100` only *labels* the
sheet; nothing is rescaled, and the converter does not verify that the label
fits the paper.

A one-line source note (`Source: … · DXF R2018, metres · title block scale is
textual, not a paper layout · not a measured survey`) is written at the
bottom-left of the frame in 0.62 x text height.

## North arrow

The arrow is drawn for every run. `northDegrees` is a **bearing in degrees
clockwise from the drawing's up direction** (sheet +Y): 0 points up, 90 points
right.

- `360 - …` labels: the arrow head always carries the `N` label when a bearing
  exists; `N?` is used only when no orientation value exists at all.
- The bearing is computed as `(180 - heading) + alignmentOffset`, where
  `heading` is `orientation.orientation_degrees` from the scan or, failing
  that, `headingDegrees` from `meta.json`. `alignmentOffset` is the rotation
  the architectural-alignment matrix applies when the model frame is projected
  onto the sheet (`atan2(m[0], -m[2]) - 90`).
- The arrow uses the heading **with or without `--geo`**: orientation is not a
  location, and `--geo` only governs coordinates.

### Verification of the rotation convention

The convention above was checked against the vendor's own output for a real
Polycam project (`meta.json headingDegrees = 193.7412°`):

| source | north bearing (model frame) |
|---|---|
| vendor PDF floorplan north symbol ("the north symbol points to true north") | 346.1° |
| vendor DXF `NORTH` layer — filled arrow head | 346.25° |
| vendor DXF `NORTH` layer — position of the `N` letter | 166.26° |
| this converter, formula `180 - heading` | 346.26° |

The vendor's arrow head and its letter are exactly 180° apart, so the letter
is drawn at the *tail* of the needle, not at its head. Two of the three vendor
artefacts agree with `180 - heading` to better than 0.2°; the sheet value
after the 7.97° alignment rotation is 354.2°, i.e. north points almost straight
up — consistent with the PDF symbol, which measures 354.1° on a 600 dpi
raster.

Residual risk: this is evidence from one vendor's artefacts, not a published
specification. The heading is project metadata, it carries no confidence value,
and an error of a few degrees cannot be excluded. The arrow is therefore
**always** marked `approx` in the manifest when it comes from `meta.json`, and
`roomplan.north-direction-approximate` is emitted. Do not read bearings off
the sheet for surveying.

## Manifest fields

```json
{
  "titleBlock": {"project": "...", "author": "ARCHIFEST", "drawnBy": "by ARCHIFEST",
                 "scaleText": "NTS", "date": "2026-08-06", "sheet": "A-01",
                 "locationText": "location withheld", "sourceNote": "...", "frame": true},
  "northArrow": {"label": "N", "described": "approx", "basis": "meta.headingDegrees",
                 "sourceHeadingDegrees": 193.74, "alignmentBearingOffsetDegrees": 7.9724,
                 "degreesClockwiseFromDrawingUp": 354.23, "source": "meta.json",
                 "confidence": null, "approximate": true, "reasons": ["..."]},
  "frame": true,
  "sheetFurniture": {"frameBounds": [...], "titleBlockBounds": {...}, "northArrow": {"tip": [...]}}
}
```

`entityCount` counts geometry **and** sheet furniture; `geometryEntityCount`
counts only the scanned plan. With `--no-frame` the two are equal and
`titleBlock` is `null`.
