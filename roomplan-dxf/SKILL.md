---
name: roomplan-dxf
description: 'Convert RoomPlan or Polycam scans to audited DXF and quantities: room areas, ceilings from slopes, wall net/paint, handoff table.'
triggers: "RoomPlan, Polycam, DXF, floor plan"
---

# RoomPlan scan to DXF

Convert an existing RoomPlan JSON file into a standard R2018 DXF plan. This package does not capture LiDAR, decrypt meshes, upload scans or write DWG.

## Requirements

- **Node 16+, no npm packages.** The converter is plain CommonJS: `node scripts/roomplan-to-dxf.js --help`.
- **Python 3.9+ with `ezdxf` 1.4+.** `scripts/lib/dxf-emit.py` writes the DXF with it. Check with `python3 -c "import ezdxf; print(ezdxf.__version__)"`.
- Install with `python3 -m pip install "ezdxf>=1.4"`; on Alpine Linux (iSH) the system Python is externally managed, so add `--break-system-packages`.
- The converter probes the import before it touches any input and exits **3** with that exact command if `ezdxf` is missing. It never installs anything by itself.

## One flow

1. **Identify the dialect.** Raw Apple export (`walls`/`floors`/`doors`, optionally `rooms[]` or `captureSessions[]`) or optimized explicit v1 / positively validated unversioned legacy (`rooms[]` with numeric polygons; labels optional). Raw is Apple's own `CapturedRoom`/`CapturedStructure` encoding; “optimized” is a third-party post-processed export (commonly Polycam-style) whose field names are an observed contract, not an Apple schema. Do not guess from the filename; read the structure. See [formats](references/formats.md).
2. **Convert** from this package directory:

   ```sh
   node scripts/roomplan-to-dxf.js scan.json out/
   node scripts/roomplan-to-dxf.js "My scan project/" out/   # whole project directory
   ```

   Writes `out/scan.dxf` (R2018/AC1032, metres, `$INSUNITS = 6`) and `out/scan.roomplan.json`. The input is opened read-only. Existing outputs are refused; add `--force` only after confirming the destination.

   A **directory** is accepted too: the scan is taken from `optimized_roomplan.json`, `roomplan.json`, `data/scan.json` or `scan.json` (first match wins, losers named in a warning), and `meta.json` / `data/meta.json` supplies the project name, date and — only as a fallback when the scan has none — latitude/longitude and heading, recorded as `sourceMetadata: "meta.json"` with `metadataFallbackFields`; scan values always win. A **single file** also looks for `<dir>/meta.json`, then `<dir>/data/meta.json`, but only when it can be attributed to that scan: if the folder holds another scan candidate the metadata is NOT borrowed and the run warns `roomplan.meta-not-attributed` — a wrong heading is worse than a missing one. Outputs default to `<dir>/out`, so give an explicit output directory for read-only inputs.

   The DXF is a **sheet**, not just geometry: `--project`, `--author` (default `roomplan-dxf`), `--scale` (default `NTS` — text only, nothing is rescaled and no paper scale is implied) and `--sheet` (default `A-01`) fill the title block; `--no-frame` removes the frame, title block and north arrow. Location prints `lat, lon` only with `--geo`, otherwise `location withheld` (`--place` → `--place-lookup` → `--geo` → withheld). The **north bearing defaults to the flipped `(alignmentOffset - heading) mod 360`**; the unflipped `180 - heading + offset` drew the arrow exactly 180° wrong on a real drawing (165.3° drawn vs. 345.3° expected) and is kept behind `--no-north-flip`; the choice is recorded as `northArrow.flip180` + `roomplan.north-flip-applied`, never silent. **One frame per story** (own title block and `Kat` row, gap 8 % of the widest frame); `--no-frame` warns `roomplan.stories-not-separated`. Title-block cells shrink to 55 % and then ellipsise, always one line. **Openings are painted above the walls** (door 3, window 5, opening 6, at the wall's 0.35 mm lineweight). Details: [title-block](references/title-block.md), [dxf-output](references/dxf-output.md).

   **Location lookup is opt-in here (OFF by default) and needs the local Apple `apple-location` helper** (present in the iOS/Minis environment; reported as `unavailable` elsewhere). It sends the coordinates to the Apple reverse geocoder once, never to a third-party service, and a failure only warns and falls back. Both installed and contribution builds keep lookup OFF by default and accept `--no-place-lookup` explicitly.

   Add `--usdz` to also write `out/scan.usdz`, an untextured AR Quick Look model (ASCII `room.usda` in a STORE-only ZIP, metres, Y up). It needs no Apple SDK and no npm package, is independent of `--model`/`--report`/`--md`, and obeys the same guards. See [usdz](references/usdz.md).

   Add `--geo` only when the recipient needs the source location point: it copies existing metadata into `sourceGeo`, prints coordinates in the title block and adds a privacy warning; it does not georeference the drawing.
3. **Audit before trusting the result:**

   ```sh
   python3 -B scripts/inspect_dxf.py out/scan.dxf
   ```

   Expect exit 0, audit errors/fixes 0, `insunits` 6, and entity/layer counts matching the manifest. Compare bounds and room labels against the scan, not just counts. A clean audit proves file structure, not survey accuracy.
4. **DWG only if the recipient insists.** There is no reliable free DWG writer here. Use ODA File Converter outside this environment (see README) and keep the audited DXF as the source of truth. DWG is not required for the workflow.

## What the manifest tells you

`lossy` is always `true`. Read `warnings`, `storyAssignmentMethod`, `architecturalAlignment` and `sourceSHA256`. Expect:

- raw input has no room polygons or labels, only element geometry;
- raw stories are clustered per room by floor elevation (0.8 m tolerance) when the source has no distinct story values;
- walls without captured thickness become centrelines;
- doors and windows are centrelines at their transform origin;
- curved walls, non-uniform wall polygons and any mesh/ceiling data are not exported;
- `polygonCorners` is used for floors only;
- `stories[]` + `sheetLayout.storiesSeparated` tell you whether floors were separated into their own frames (they are not when `--no-frame` is used);
- `northArrow.flip180` records which bearing formula was used.

Coordinates are metres in the source frame. DXF applies a computed raw rotation or the source-provided optimized affine alignment; the source file is untouched. Keep scans and manifests local: optimized sources can carry `latLonAlt` and compass metadata into the manifest.

## Optional normalized capture model

Add `--model --no-place-lookup` to write `<name>.capture.json`: source-space geometry kept separate from the unapplied alignment, dialect evidence, SHA256 provenance, known source attributes/sections and an explicit loss inventory. It is a subset, not a complete RoomPlan/mesh decode or a compatibility promise; missing labels stay null, category/id provenance is retained, unknown explicit versions still fail. The document is `capture-v1` (SPEC §3) with `units:"metres"`, `axes:{world:"y-up",plan:"x,-z"}`, `stories[]`, `source{sha256,bytes,dialect,dialectEvidence}`, `raw{opaque,excluded}`, rooms as `polygonXZ`+`declaredArea`, and a `provenance{status,coverage,reason}` on every surface, object and room. Every number is `{value,status,coverage,included,expected,reason}`: `status` is provenance, `coverage` is completeness — never mix them. Without `--geo`, recursive whitelisting omits location-like and unknown metadata; with `--model --geo` a verbatim source tree is included and can expose private/opaque data, so keep it local. Schema: [model-schema](references/model-schema.md).

## Surface Region registry and grouping

SR means **Surface Region**, supplied or reconstructed. CLI `--surface-region-groups <sidecar.json>` supports explicit source-SHA256-scoped user-confirmed groups without flattening or double-counting; without the flag a sidecar beside the scan is auto-discovered by fixed name (`<scan>.surface-region-groups.json`, `surface-region-groups.json`), and a stale one for another capture is ignored with a warning. The registry is shared by CLI manifest/report, CSV/MD references and USDZ root metadata; provenance is `surfaceRegions.groupsSource`. Legend, discovery order and the full **source-region annotation contract (2026-11-08)** — envelope accounting, provenance vs. physical verification, layout limits: [surface-regions](references/surface-regions.md).

## Ceilings and heights (`--ceilings`, DEFAULT ON; `--no-ceilings` to disable)

Heights live on the Surface Region annotations, never on room titles (name and area only). A knee profile is a **strip**, not the room: the orange dashed `S<n>_CEILING` band carries the slope, fall line and ridge, the thin gray `S<n>_CEILING_FLAT` carries the flat remainder, and a flat ceiling draws no slope outline at all. Explicit optimized-source `rooms[].ceiling` / `ceiling_curr` surfaces are annotated when genuinely tilted; heights are ceiling-to-floor differences in one source-world space (floor datum must be a covering measured floor polygon, `room.floor_height` only as a labelled `supplied-floor-level` fallback), never `dimensions.y` and never a fixed 2.5 m — without evidence the height stays null with `heightReason`. Raw input has no room polygons, so its ceilings are reconstructed from wall tops per storey. Full rules: [heights-ceilings](references/heights-ceilings.md).

## Quantities and area report

```sh
node scripts/roomplan-to-dxf.js scan.json out/ --report --no-place-lookup   # + --md for scan.md
```

adds `scan.report.json` (`report-v1` schemaVersion `roomplan.report/1`) and `scan.quantities.csv` (UTF-8 BOM, `;`), combinable with `--model`; `--md` implies `--report`. Key caveats in one line: source, computed and estimated areas are distinct, shared walls are not additive, net wall areas are a **partial subtotal** when opening coverage is incomplete (`PAINT_FREE_OPENING_M2 = 3` governs paint only), and no number is a verified building total. Read [quantities](references/quantities.md) before quoting any total — it holds the formulas, the CSV/security rules, the test list and the **release defaults** (DXF ceilings ON, USDZ ceiling meshes OFF, location lookup OFF).

## Rules

- Never fabricate missing geometry, thickness, stories or rooms, and never re-enable the legacy `--no-north-flip` formula without saying so.
- Do not enable `--place-lookup` silently: it sends the scan coordinates to the Apple geocoder, and the result is a locality, not a verified address.
- Never overwrite a scan or an output without explicit permission.
- Report the exact dialect and the warnings you saw; do not present a DXF as measured, certified or fabrication-ready.
- Run the self-test after editing converter files (README).
- RoomPlan is an Apple framework and DXF is a CAD exchange format; this skill is independent and not affiliated with, endorsed or certified by Apple or Autodesk.
