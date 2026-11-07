---
name: roomplan-dxf
description: 'Convert RoomPlan or Polycam scans to audited DXF with title block and north arrow. Use for roomplan, Polycam, floor plans, DXF, measurements.'
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

## Ceilings and heights (`--ceilings`, default off)

Explicit optimized-source ceilings (`rooms[].ceiling` / `ceiling_curr`,
`transform` + 2D `polygon`) are annotated on orange dashed `S<n>_CEILING`
layers (ACI 30, truecolor `0xFF8000`, 3 cm offset). Annotations never alter wall
or floor geometry or quantities. `h 2,50 m` / `h 2,10-2,85 m` labels are
ceiling-to-floor vertical differences in one source-world space; the floor datum
must be a covering measured floor polygon, and `room.floor_height` is used only
as an explicitly labelled `supplied-floor-level` fallback. Without evidence the
height stays null with `heightReason` and a warning; never `dimensions.y`, never
a fixed 2.5 m. Raw input has no ceilings and is not reconstructed. See
[heights-ceilings.md](references/heights-ceilings.md).

## Quantities and area report

Use `node scripts/roomplan-to-dxf.js scan.json out/ --report --no-place-lookup`
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
(authored 3D ceiling, G-5) and `node tests/test_interior_area.js` (interior vs centreline
area, G-6/G-7) for the numerical safety tests. Reports obey
existing output overwrite and source-alias protections. Report generation is
local and does not require location lookup or an external review service.
