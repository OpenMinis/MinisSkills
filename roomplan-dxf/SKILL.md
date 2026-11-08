---
name: roomplan-dxf
description: 'Convert RoomPlan or Polycam scans to audited DXF and quantities: room areas, ceilings from slopes, wall net/paint, handoff table.'
---

# RoomPlan scan to DXF

Convert an existing RoomPlan JSON file into a standard R2018 DXF plan. This package does not capture LiDAR, decrypt meshes, upload scans or write DWG.

## One flow

1. **Identify the dialect.** Raw Apple export (`walls`/`floors`/`doors`, optionally `rooms[]` or `captureSessions[]`) or optimized explicit v1 / positively validated unversioned legacy (`rooms[]` with numeric polygons; labels optional). Raw is Apple's own `CapturedRoom`/`CapturedStructure` encoding; “optimized” is a third-party post-processed export (commonly Polycam-style) whose field names are an observed contract, not an Apple schema. Do not guess from the filename; read the structure. See [formats](references/formats.md).
2. **Convert** from this package directory:

   ```sh
   node scripts/roomplan-to-dxf.js scan.json out/
   node scripts/roomplan-to-dxf.js "My scan project/" out/   # whole project directory
   ```

   Writes `out/scan.dxf` (R2018/AC1032, metres, `$INSUNITS = 6`) and `out/scan.roomplan.json`. The input is opened read-only. Existing outputs are refused; add `--force` only after confirming the destination.

   A **directory** is accepted too: the scan is taken from
   `optimized_roomplan.json`, `roomplan.json`, `data/scan.json` or `scan.json`
   (first match wins, losers are named in a warning) and `meta.json` /
   `data/meta.json` supplies the project name, date, and — only as a fallback
   when the scan has none — latitude/longitude and heading. Scan values always
   win; fallbacks are recorded as `sourceMetadata: "meta.json"` with
   `metadataFallbackFields` and warning codes. Outputs default to `<dir>/out`,
   so give an explicit output directory for read-only inputs.

   The DXF is a **sheet**, not just geometry: `--project`, `--author`
   (default `ARCHIFEST`), `--scale` (default `NTS`), `--sheet` (default
   `A-01`) fill the title block; `--no-frame` removes the frame, title block
   and north arrow. The scale is text only — nothing is rescaled and no paper
   scale is implied. Location prints `lat, lon` only with `--geo`, otherwise
   `location withheld` (order: `--place "<text>"` → `--place-lookup` → `--geo`
   coordinates → `location withheld`); the north arrow uses the scan
   orientation or the `meta.json` heading **without** `--geo` and is marked
   `approx` when it comes from metadata. Details:
   [references/title-block.md](references/title-block.md).

   **North bearing (default, flipped):** `(alignmentOffset - heading) mod 360`.
   The unflipped `180 - heading + offset` drew the arrow exactly 180° wrong on a
   real drawing (165.3° drawn vs. 345.3° expected, heading 42.352° with a
   27.629° alignment offset). The flip is the default and is recorded as
   `northArrow.flip180` + `roomplan.north-flip-applied`; add `--no-north-flip`
   to restore the legacy formula. Sanity check: heading 0° → 0°, heading 90° →
   270° at zero offset.

   **One frame per story.** A plan with more than one story is emitted as
   separate frames side by side — one bbox, frame, title block (`Kat` row:
   `0` = Prizemlje, `1` = `1. kat`, `2` = `2. kat`, negative = Podrum) and
   north arrow per floor, gap = 8 % of the widest frame width, each frame
   holding only its own `S<n>_*` entities. `--no-frame` keeps one common
   drawing and then warns `roomplan.stories-not-separated`.

   **Title-block text always fits its cell:** reduced height first (down to
   55 %), then truncated with `…`, always one line — check `truncated` and
   `textHeight` in `sheetFurniture.sheets[].titleBlock.cells` if a value looks
   cut.

   **Location lookup is opt-in here (OFF by default) and needs the local Apple
   `apple-location` helper** (present in the iOS/Minis environment; reported as
   `unavailable` elsewhere). It sends the coordinates to the Apple on-device
   geocoder once, never to a third-party service, and a failure only warns and
   falls back. The local skill build turns it on by default and offers
   `--no-place-lookup`.

   Add `--usdz` to also write `out/scan.usdz`, an untextured AR Quick Look model
   (ASCII `room.usda` in a STORE-only ZIP, metres, Y up). It needs no Apple SDK
   and no npm package, is independent of `--model`/`--report`/`--md`, and obeys
   the same overwrite/alias guards. See the USDZ section below.

   Add `--geo` only when the recipient needs the source location point: it
   copies existing metadata into `sourceGeo`, prints coordinates in the title
   block and adds a privacy warning; it does not georeference the drawing.
3. **Audit before trusting the result:**

   ```sh
   python3 -B scripts/inspect_dxf.py out/scan.dxf
   ```

   Expect exit 0, audit errors/fixes 0, `insunits` 6, and entity/layer counts matching the manifest. Compare bounds and room labels against the scan, not just counts. A clean audit proves file structure, not survey accuracy.
4. **DWG only if the recipient insists.** There is no reliable free DWG writer here. Use ODA File Converter outside this environment (see README) and keep the audited DXF as the source of truth. DWG is not required for the workflow.

## Optional normalized capture model

Add `--model --no-place-lookup` to write `<name>.capture.json`. It preserves source-space geometry separately from the unapplied alignment, dialect evidence, SHA256 provenance, known source attributes/sections and an explicit loss inventory. It is a subset, not a complete RoomPlan/mesh decode or a compatibility promise. Missing labels remain null; category/id provenance is retained. Unknown explicit versions still fail.

The document is `capture-v1` (SPEC §3): `units:"metres"`, `axes:{world:"y-up",plan:"x,-z"}`, `stories[]`, `source{sha256,bytes,dialect,dialectEvidence}`, `raw{opaque,excluded}`, rooms as `polygonXZ`+`declaredArea`, and a `provenance{status,coverage,reason}` on every surface, object and room. `report-v1` (§3) uses `totals{floorArea, ceilingArea, wallAreaGross, wallAreaNet, openingArea, wallLength, paintArea, livingArea, roomsWithoutArea, counts{...}}`, `elements[].id/area/roomRefs`, `warnings[{code,message,severity}]`, `assumptions[]`, plus the `statistics` (G-9) and `handoff` (G-10) blocks in the same file. Every number is `{value,status,coverage,included,expected,reason}`: `status` is provenance, `coverage` is completeness — never mix them.

Without `--geo`, recursive whitelisting omits location-like and unknown metadata. With `--model --geo`, a verbatim source tree is included and can expose private/opaque data. Keep it local. See [model-schema](references/model-schema.md). `--no-place-lookup` is supported explicitly in this public package too. Direction is retained with a reliability caveat.

## What the manifest tells you

`lossy` is always `true`. Read `warnings`, `storyAssignmentMethod`, `architecturalAlignment` and `sourceSHA256`. Expect:

- raw input has no room polygons or labels, only element geometry;
- raw stories are clustered per room by floor elevation (0.8 m tolerance) when the source has no distinct story values;
- walls without captured thickness become centrelines;
- doors and windows are centrelines at their transform origin;
- curved walls, non-uniform wall polygons and any mesh/ceiling data are not exported;
- `polygonCorners` is used for floors only;
- `stories[]` + `sheetLayout.storiesSeparated` tell you whether floors were
  separated into their own frames (they are not when `--no-frame` is used);
- `northArrow.flip180` records which bearing formula was used.

Coordinates are metres in the source frame. DXF applies a computed raw rotation or the source-provided optimized affine alignment; the source file is untouched. Keep scans and manifests local: optimized sources can carry `latLonAlt` and compass metadata into the manifest.

## Rules

- Never fabricate missing geometry, thickness, stories or rooms, and never
  re-enable the legacy `--no-north-flip` formula without saying so.
- Do not enable `--place-lookup` silently: it sends the scan coordinates to the
  Apple geocoder, and the result is a locality, not a verified address.
- Never overwrite a scan or an output without explicit permission.
- Report the exact dialect and the warnings you saw; do not present a DXF as measured, certified or fabrication-ready.
- Run the self-test after editing converter files (README).
- RoomPlan is an Apple framework and DXF is a CAD exchange format; this skill
  is independent and not affiliated with, endorsed or certified by Apple or
  Autodesk.

## Ceilings and heights (`--ceilings`, DEFAULT ON; `--no-ceilings` to disable)

Every room label carries its height — `Soba  12.40 m2  h 2.50` or
`Soba  19.80 m2  h 1.65-2.48`. When a capture has no room polygon at all (raw
Apple format) the label still exists, once per storey, at the centre of the
storey's bounding box: `Kat 0 — 33.34 m2 — h 1.65-2.48`. A height is never
invented and never printed as `0`; when it is unknown the `h` part is simply
absent.

**A slope is a strip, not the room.** A knee profile slopes only over the
measured `run` next to the low wall and is flat at the ridge everywhere else, so
the ceiling is split into TWO parts and only the strip is drawn:

* `S<n>_CEILING` (orange, dashed, ACI 30 / truecolor `0xFF8000`, 3 cm offset):
  the sloped band only — its outline, the fall line with the downhill arrow,
  the ridge line where the band ends, and `h 1.65-2.48 (knee|section)`.
* `S<n>_CEILING_FLAT` (thin, continuous, gray): the flat remainder's boundary
  and `h 2.48 (flat)`. Never orange, never a strip.

A ceiling that is flat — reconstructed flat, or an explicit source polygon with
no tilt — draws **nothing at all** on any ceiling layer: the dashed rectangle
across a plane with no slope was pure noise, and the room label already states
the height. Gables keep two bands (and a flat plateau only when the section has
a flat segment).

Explicit optimized-source ceilings (`rooms[].ceiling` / `ceiling_curr`,
`transform` + 2D `polygon`) are still annotated on the orange dashed layer when
they are genuinely tilted; a horizontal one is skipped as above. Annotations never alter wall
or floor geometry or quantities. `h 2.50` / `h 2.10-2.85` labels are
ceiling-to-floor vertical differences in one source-world space; the floor datum
must be a covering measured floor polygon, and `room.floor_height` is used only
as an explicitly labelled `supplied-floor-level` fallback. Without evidence the
height stays null with `heightReason` and a warning; never `dimensions.y`, never
a fixed 2.5 m. Raw input has no room polygons, so its ceilings are
reconstructed from wall tops and reported per storey. See
[heights-ceilings.md](references/heights-ceilings.md).

## USDZ export (`--usdz`)

`node scripts/roomplan-to-dxf.js scan.json out/ --usdz` writes `out/scan.usdz`
and prints `USDZ written: <path> (N prims)`. A USDZ is a ZIP of `*.usda` text,
so both layers are written here by hand: `scripts/lib/usdz-writer.js`
(STORE-only ZIP, own CRC-32, 64-byte aligned payloads, fixed 1980-01-01
timestamp so the file is reproducible) and `scripts/lib/usda-export.js` (the
USD ASCII layer).

Layer shape (copied from Apple's own exporter, 105 reference layers):
`#usda 1.0` with `defaultPrim = "room"`, `metersPerUnit = 1`, `upAxis = "Y"`;
`room > Section_grp` holds one `kind = "assembly"` `Xform` per captured room
(named from a sanitised label, e.g. `Kuhinja/dnevni` → `Kuhinja_dnevni`), and
`room > Mesh_grp` holds one `kind = "component"` `Xform` per element
(`Wall_1…`, `Floor_1…`, `CeilingSlope_1…`, `CeilingFlat_1…`, `Door_1…`,
`Window_1…`, `Opening_1…`, `Object_1…`),
each with `customData = { string Category string Identifier }`, each containing a
`def Mesh` **and** its own `def Material "<Name>_color"` (UsdPreviewSurface)
that the Mesh binds with `rel material:binding`. The one exception is an
OPENING (`Door_`/`Window_`/`Opening_`): it is an empty `Xform` carrying `Label`,
`Width`, `Height` and `Role = "opening"` and no mesh at all, because the hole
the wall was cut for is the element. Prim metadata always sits in the
parenthesis block after the prim name, never inside the braces.

Ceilings (`scripts/lib/ceiling-3d.js`) are real solids, so they are visible in
AR Quick Look instead of being an annotation a USDZ cannot carry. A knee
profile is **two prims** — `CeilingSlope_<n>` (the band from the knee up to the
ridge, `Geometry = "sloped strip"`, `Method = "knee"`) and `CeilingFlat_<n>`
(the remainder, `Geometry = "flat plane"`, `Method = "flat"`) — never one
tilted sheet across the whole room. A flat ceiling is ONE prim with 2 triangles
and normal −Y (seen from below); a gable is two `CeilingSlope_` planes meeting
at a ridge, plus a `CeilingFlat_` plateau only when the section has a flat
segment. `double Area` on each prim is its own FOOTPRINT area, so the strip's
area stays checkable against `run × room depth`. The
method is never used to invent geometry: `extrusion`/`unavailable` become a flat
plane at the knee height plus `usdz.ceiling-approximated`, and a room with no
footprint polygon gets no ceiling at all plus `usdz.ceiling-no-polygon`.
Because Quick Look renders no text, room and ceiling prims carry the label in
`customData`: `string Label`, `double Area`, `string Height` (`"2.50"` or
`"1.60-2.50"`), `string Method`.

Geometry: `polygonCorners` → that polygon, fan-triangulated — except for a
WALL, where a flat plan polygon is extruded through the thickness into a prism
(2 ear-clipped caps + one side per edge, `scripts/lib/polygon-prism.js`), because
a zero-thickness wall is paper and vanishes under backface culling; otherwise an
oriented box from `dimensions` (x length, y height, z thickness) placed by the
4×4 transform. Thickness precedence for walls: `dimensions.z`, then the source's
`wallThickness`, then Apple's 0.16 m default (flagged `assumed`). Every mesh is triangulated and its vertices are split per
face-vertex (a box = 12 triangles / 36 vertices), so `normal3f[] normals` has one
normal per point and no `interpolation` metadata is written — Apple's shape. An unmeasured wall gets **0.16 m** (Apple's
default) and is flagged `string Thickness = "assumed"`. **Door and window holes
are real**: a wall named by an opening's `parentIdentifier` is cut by grid
decomposition in the wall's own (u, v) plane (`scripts/lib/wall-holes.js`) — a
full rectangle of cells is emitted, minus the cells inside an opening, so the
front/back faces have holes and the opening edges become reveal faces. Openings
that cannot be placed (no transform, outside the wall by more than 20 mm, or a
wall exported from `polygonCorners`) leave the wall solid and record
`usdz.opening-not-cut`; a sub-20 mm overshoot is clamped and recorded as
`usdz.opening-clamped`. The `Door_*`/`Window_*` prims remain, marked
`Role = "opening"`. A prim with a
non-finite transform or no usable geometry is skipped with a warning (also in
the manifest) — the layer never contains `NaN`. Source space is used as-is; the
DXF sheet rotation is **not** applied.

Not exported: textures, UVs, materials, cameras, lights, semantics, RealityKit
meshes. Nothing here has been validated by Apple's `usdchecker` or by AR Quick
Look — the file must be opened on a real device to confirm. Format notes:
[usdz](references/usdz.md). Test: `node tests/test_usdz.js` (40 checks, opens
the ZIP with Python's `zipfile` and asserts `testzip() === None`) plus
`node tests/test_wall_holes.js` (16 checks: measured front area after cutting,
watertight edges, outward normals, refusal warnings).

## Quantities and area report

Use `node scripts/roomplan-to-dxf.js scan.json out/ --report --no-place-lookup`
(add `--md` for the Markdown summary `scan.md`)
to additionally write `scan.report.json` and `scan.quantities.csv`.
Combine with `--model` for the normalized capture. CSV uses UTF-8 BOM and `;`.

Read [quantities](references/quantities.md) before relying on totals. Source room
areas, polygon-computed areas, dimension-estimated wall areas and unavailable
values are distinct. Shared wall references are not additive. Net wall areas
subtract only validated parent-linked openings; incomplete coverage yields a
**partial subtotal**, not a complete building quantity. Ceiling and volume are
unavailable. This independent engine was not ported from or compared with the
historical web reporting implementation. No survey accuracy is implied.

Run `node tests/test_quantities.js` (net/paint/CSV safety), `node tests/test_authored_ceiling.js`
(authored 3D ceiling, G-5), `node tests/test_interior_area.js` (interior vs centreline
area, G-6/G-7), `node tests/test_plan_statistics.js` (G-9: gross/net per level,
living/gross, roomsWithoutArea from an ArchiPlan fixture) and `node tests/test_handoff.js`
(G-10: per-room boundary figures, quantities[] keys, gaps[]) for the numerical safety tests.
`node tests/test_spec_golden.js` runs all thirteen SPEC §7 golden rows. Reports obey
existing output overwrite and source-alias protections. Report generation is
local and does not require location lookup or an external review service.
