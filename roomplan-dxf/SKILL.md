---
name: roomplan-dxf
description: 'Convert Apple RoomPlan raw or optimized JSON scans into a metres DXF plan plus lossy manifest, then audit units, entities and layers. No capture, cloud or DWG writing.'
---

# RoomPlan scan to DXF

Convert an existing RoomPlan JSON file into a standard R2018 DXF plan. This package does not capture LiDAR, decrypt meshes, upload scans or write DWG.

## One flow

1. **Identify the dialect.** Raw Apple export (`walls`/`floors`/`doors`, optionally `rooms[]` or `captureSessions[]`) or optimized `format_version: 1` (`rooms[]` with `label_automated`/`vertices_x`). Raw is Apple's own `CapturedRoom`/`CapturedStructure` encoding; “optimized” is a third-party post-processed export (commonly Polycam-style) whose field names are an observed contract, not an Apple schema. Do not guess from the filename; read the structure. See [formats](references/formats.md).
2. **Convert** from this package directory:

   ```sh
   node scripts/roomplan-to-dxf.js scan.json out/
   ```

   Writes `out/scan.dxf` (R2018/AC1032, metres, `$INSUNITS = 6`) and `out/scan.roomplan.json`. The input is opened read-only. Existing outputs are refused; add `--force` only after confirming the destination. Add `--geo` only when the recipient needs the source location/compass point: it copies existing metadata into `sourceGeo` and adds a privacy warning; it does not georeference the drawing.
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
- `polygonCorners` is used for floors only.

Coordinates are metres in the source frame. Export applies only a rigid alignment rotation; the source file is untouched. Keep scans and manifests local: optimized sources can carry `latLonAlt` and compass metadata into the manifest.

## Rules

- Never fabricate missing geometry, thickness, stories or rooms.
- Never overwrite a scan or an output without explicit permission.
- Report the exact dialect and the warnings you saw; do not present a DXF as measured, certified or fabrication-ready.
- Run the self-test after editing converter files (README).
- RoomPlan is an Apple framework and DXF is a CAD exchange format; this skill
  is independent and not affiliated with, endorsed or certified by Apple or
  Autodesk.
