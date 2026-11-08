# roomplan-dxf — one data contract, many consumers

Status: design agreed 2026-11-07. This document is the contract; code that
disagrees with it is wrong, not the other way round.

## 1. Why this exists

The engine was rebuilt three times. `geometry.js` (v0.1) computed ceilings and
sloped walls but knew only one raw capture. `report-model.js` (v0.2) supported
multi-floor, multi-session and optimized input, and dropped ceilings, zones and
paint. `planStatistics.ts` (ArchiPlan) measures interior floor areas correctly
and exports a full quantities handoff, but assumes flat ceilings. Nothing ever
combined them, so each rewrite silently lost what the previous one had.

This contract exists so a future rewrite cannot lose anything: every value
carries its provenance, and the golden numbers below are executable.

## 2. Principles

1. **No number without provenance.** Every quantity is one of
   `supplied | computed | reconstructed | estimated | unavailable`, with a
   machine-readable reason. Unknown is never zero.
2. **One kernel, many outputs.** DXF, CSV, Markdown, an HTML app or a native
   app consume the same `report-v1`. Nobody re-derives geometry.
3. **Golden numbers are the contract.** Changing one is a decision, never an
   accident.
4. **Refuse rather than guess.** A polygon that is not simple, planar or rigid
   is `null` with a reason — not a rectangle substitute.
5. **Pure JavaScript core, zero dependencies.** Runs in Node (iSH) and in a
   browser unchanged. Python only for DXF emission (`ezdxf`).

## 3. Two contracts

### capture-v1 — normalised input

Produced by an input adapter from whatever the producer wrote. Consumers never
read vendor JSON directly.

```
schemaVersion: "roomplan.capture/1"
source: { filename, sha256, bytes, dialect, dialectEvidence[], producer? }
units: "metres"
axes: { world: "y-up", plan: "x,-z" }
alignment: { matrix[16] | null, appliedItself: false }
stories: [ { story, label, floorElevation? } ]
surfaces: [ { id, sourceId, kind: wall|floor|door|window|opening,
              story, parentId?, category?, confidence?,
              dimensions {x,y,z}, thickness?, transform[16],
              polygonCorners[]?, isOpen?, provenance } ]
objects:  [ { id, sourceId, category, story, dimensions, transform,
              polygonCorners[]?, provenance } ]
rooms:    [ { id, sourceId, label, category, story,
              polygonXZ[]?, declaredArea?, floorHeight?,
              ceilingPlane?, provenance } ]
meta:     { project?, date?, headingDegrees?, latitude?, longitude?,
            orientationDegrees?, orientationConfidence?, storyCount? }
raw:      { opaque: ["coreModel"], excluded: [] }   // never silently dropped
```

Rules: metres only; column-major 16-value transforms; `polygonCorners` in local
Y-up when the producer supplies them; `declaredArea` is the producer's number
and is never added to a computed one; location and heading are only written when
explicitly requested.

### report-v1 — computed result

```
schemaVersion: "roomplan.report/1"
source: { sha256, byteCount, dialect, captureSchema: "roomplan.capture/1" }
totals: { floorArea, ceilingArea, wallAreaGross, wallAreaNet, openingArea,
          wallLength, paintArea, livingArea, roomsWithoutArea,
          counts { roomCount, wallCount, doorCount, windowCount, objectCount } }
// every scalar above is a measure object, including roomsWithoutArea, because
// "3 rooms could not be measured" is only meaningful with the number checked.
stories: [ { story, label, totals, rooms: [ id, ... ] } ]
rooms:   [ { id, identifier, label, story, declaredArea, polygonArea,
             polygonMinusDeclared, ceilingArea { ...method }, volume } ]
elements: [ { id, kind, story, area, roomRefs[], slopeCut? } ]
statistics: plan-statistics block (§5 G-9) | null
handoff:    handoff block with quantities[] and gaps[] (§5 G-10) | null
warnings: [ { code, message, severity } ]
assumptions: [ string ]
```

Every numeric field appears as `{ value, status, coverage, included, expected,
reason }` (see §4). `ceilingMethod` is `supplied | knee | section | extrusion |
flat | unavailable`.

`elements[]` carries the flat line list (`id`, not `key`; `roomRefs[]`, not
`roomMemberships`); `area` is the gross measure and the specialist measures
(`netArea`, `paintArea`, `length`, `thickness`) sit beside it.
`roomRefs[]` are references and are never additive. `statistics` and `handoff`
are the two specialist blocks from §5 and live in the same document so a
consumer never re-derives them.

### capture-v1 — top level

The §3 block above is the whole document. Since the P4 cleanup the adapter
emits `units`, `axes`, `stories` and `raw` at the top level, keeps `dialect`
inside `source` (with `bytes`, not `byteCount`), and stamps a
`provenance { status, coverage, reason }` on every surface, object and room.
Rooms carry `polygonXZ` (not `vertices`) and `declaredArea` (not `area`).

## 4. Provenance model

| status | meaning |
|---|---|
| `supplied` | read from the producer; we did not compute it |
| `computed` | derived from validated geometry (simple, planar, rigid) |
| `reconstructed` | derived from a model, e.g. ceiling from wall top profiles |
| `estimated` | derived from an explicit assumption (dimensions, bbox, fallback) |
| `unavailable` | cannot be known from this input; `reason` required |

`coverage` is `complete` or `partial` with counts (`included`/`expected`). A
`partial` subtotal is never presented as a building total.

## 5. Algorithms and where they come from

| Concern | Source of truth | Golden numbers (§7) |
|---|---|---|
| wall top profile, height at x, slope cut triangle | `geometry.js` `topProfile` `wallHeightAt` `slopeCutTriangles` | G-1, G-2 |
| ceiling from slopes (knee/section/extrusion), per zone | `geometry.js` `reconstructCeilingForRoom` `ceilingByZone` | G-3, G-4 |
| ceiling as authored surface with per-vertex heights, holes scaled by slope | Swift `PlanEditorModel.ceilingElevations` | G-5 |
| interior floor area excluding wall footprints | `interiorArea.ts` `interiorRoomArea` | G-6, G-7 |
| room membership (walls by endpoints, objects by centroid) | `report-model.js` `assignRoomMembership` | G-8 |
| gross/net per level, living/gross, roomsWithoutArea | `planStatistics.ts` | G-9 |
| per-room boundary walls, handoff quantities, codes | `handoff.ts` | G-10 |
| paint area with free-opening threshold | `geometry.js` `wallPaintArea` | G-11 |
| north bearing and sheet orientation | `geometry.js` `northBearingFrom` | G-12 |

Priority inside the kernel: `supplied` beats `reconstructed` beats `estimated`.
An explicit ceiling plane from the producer is never overwritten by a
reconstruction.

## 6. Consumers

| Consumer | Reads | Never does |
|---|---|---|
| DXF writer | `report-v1` + geometry from `capture-v1` | its own area maths |
| CSV / Markdown | `report-v1` | rounding that hides `partial` |
| HTML app (future) | `report-v1` | recalculating quantities |
| Native app (Swift) | `capture-v1` in, `report-v1` out | a second quantity engine |
| USDZ writer (`--usdz`) | geometry from `capture-v1` only | a second quantity engine; no `report-v1` lookup |

### USDZ export (`--usdz`)

`--usdz` writes `<name>.usdz`: a ZIP whose entries are STORE-only (method 0),
64-byte aligned, with a fixed 1980-01-01 timestamp so the same capture always
produces the same bytes. It holds one ASCII layer, `room.usda`, written without
any Apple SDK or third-party package:

```
#usda 1.0
(
    defaultPrim = "room"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "room" ( kind = "assembly" )
    def Xform "Section_grp" ( kind = "group" )   # one assembly Xform per room
    def Xform "Mesh_grp" ( kind = "group" )      # one component Xform per element
        def Xform "Wall_1" ( customData = { ... } kind = "component" )
            def Mesh "Wall_1"   { ... rel material:binding = </room/Mesh_grp/Wall_1/Wall_1_color> }
            def Material "Wall_1_color" { UsdPreviewSurface }
```

The shape above is not invented: it is the shape Apple's own exporter writes,
sampled from 105 `.usda` layers inside four Apple `.usdz` captures (see
`references/usda-grammar.md` and `tests/lib/usda-lint.js`, which must stay green
on that corpus).

Contract, in order of precedence: a surface with 3D `polygonCorners` is emitted
as that polygon (fan-triangulated) — except a WALL, whose plan polygon is
extruded along its local thickness axis into a closed prism (ear-clipped caps +
one side quad per edge, `scripts/lib/polygon-prism.js`; a zero-thickness wall is
paper and disappears from the far side under backface culling). Wall thickness
precedence is `dimensions.z`, then the source `wallThickness`, then the 0.16 m
default; otherwise an oriented box from `dimensions`
+ `transform` with x = length, y = height, z = thickness; a wall without
measured thickness uses the Apple default 0.16 m and carries
`string Thickness = "assumed"`. Meshes are **triangulated** with vertices split
per face-vertex, so `points`, `normals` and `faceVertexIndices` are all the same
length and `normal3f[] normals` has one normal per point (Apple's shape; no
`interpolation` metadata is written). Every element is a `kind = "component"`
Xform carrying `customData {Category, Identifier}` so it maps back to
`capture-v1`, and every Mesh binds its own `UsdPreviewSurface` Material.
Values are metres, 6 fixed decimals, `.` separator. A primitive with a
non-finite transform or no usable geometry is **skipped with a warning**
(surfaced in the manifest); `NaN`/`Infinity` are never written. Source space
only: `align.js`'s sheet rotation is a drawing transform and is not applied.

Door and window holes are real, not overlaid: an opening whose
`parentIdentifier` names a wall box is projected onto that wall's own axes
(u = 0…length, v = 0…height, w = ±thickness/2), the u/v boundaries of every
opening form a grid, and only the cells outside every opening are emitted
(`scripts/lib/wall-holes.js`, no CSG library). The front and back faces
therefore have genuine holes, each opening edge becomes a reveal face, the mesh
stays closed and every normal points outward; overlapping openings are cut once
as a union. An opening that cannot be placed sensibly — no 4×4 transform, no
positive width/height, more than 20 mm outside the wall, or a wall exported from
`polygonCorners` (an n-gon, not a box) — is not cut: the wall stays solid and
the manifest records `usdz.opening-not-cut`. An overshoot under 20 mm is clamped
and recorded as `usdz.opening-clamped`. A cut wall carries
`string Geometry = "box with openings cut out (grid decomposition)"`,
`int Openings`, `double CutArea`, `double ExposedArea`; the separate `Door_*`,
`Window_*`, `Opening_*` prims are retained and marked
`customData Role = "opening"`. Tests: `tests/test_wall_holes.js` measures the
front-face area from the emitted triangles (4 × 2.5 wall with a 0.9 × 2.1 door
gives 8.11 m²), the signed volume, and the directed-edge closure.

Out of scope for `usdz-v1` (stated, not hidden): textures, UVs, cameras,
lights, semantics/panels, RealityKit mesh data. **No Apple validation is
performed** — `usdchecker`/AR Quick Look are unavailable in this environment, so
the evidence is: Python `zipfile.testzip()`, 64-byte alignment and the 0x1986
padding field, byte determinism, and `tests/lib/usda-lint.js` — a strict
tokenizer/parser/semantic checker that passes on all 105 Apple reference layers
as well as on our own output.

## 7. Golden numbers (executable)

Synthetic fixtures, all in metres, checked to 1e-4.

| ID | Case | Expected |
|---|---|---|
| G-1 | gable wall 4 × 2.5, ridge 2.5 → 1.6 | gross **8.2000 m²** |
| G-2 | same, cut triangle | **1.8000 m²** removed |
| G-3 | gable room 20 m², eave 1.6, ridge 2.5, knee 5 m | ceiling **21.9317 m²**, method `knee` |
| G-4 | shed roof, same footprint | ceiling **20.5000 m²**, method `knee` |
| G-5 | authored ceiling, 4 vertices 2.0–2.6 m | area per vertex elevations; holes scaled by `ceilingArea/floorArea` |
| G-6 | 1.00 × 1.00 m room, **0.20 m** walls on the inner face | interior **1.0000 m²** |
| G-7 | same building written on wall centrelines (1.20 m polygon) | centerline **1.4400 m²** |
| G-8 | wall on a room boundary | member of that room; kernel tolerance 0.02 m |
| G-8b | wall centreline 0.25 m outside the same boundary | **not** a member; tolerance is 0.02 m — decided 2026-11-07, the 0.25 m value inherited from `report-model.js` is **not** adopted |
| G-9 | ArchiPlan fixture (`tests/fixtures/archiplan-plan-statistics.json`, ArchiPlan commit `299ed31`) | living **10.9725 m²**, net walls **35 − 1.89 m²** |
| G-10 | handoff fixture (`tests/fixtures/archiplan-handoff.json`, ArchiPlan commit `299ed31`) | the 10 contracted quantity keys present, `gaps[]` for missing areas |
| G-11 | openings 1 m² and 4 m², threshold 3 m² | paint **10 / 1 m²** |
| G-12 | heading 193.7412°, alignment 7.9724°, **optimized** dialect | sheet bearing **174.2312°** — user confirmed on site that this arrow points north (default `--north-flip`, which is the optimized default) |
| G-12b | same heading/alignment, **raw Apple** dialect | sheet bearing **174.2312°** — the same flipped default applies to every dialect; the 180° other reading (354.2312°) is wrong on site. `--no-north-flip` still forces it |

North convention (decided 2026-11-07): the default is `--north-flip`,
`bearing = (alignmentOffset - heading) mod 360`. The owner verified on site
that this arrow points north. Vendor PDF/DXF artefacts for the same project
appear 180° away from it; that discrepancy is recorded, not resolved, and no
golden number may be changed back without a new on-site check.

A change to any of these requires an explicit note in this file.

### Change log

- **2026-11-07 — `usdz-v1` added (`--usdz`).** A new consumer writes an
  untextured AR Quick Look model (`<name>.usdz`) from the same decoded geometry,
  with no Apple SDK: a hand-written STORE-only ZIP (`scripts/lib/usdz-writer.js`)
  plus an ASCII USD layer (`scripts/lib/usda-export.js`). It reuses `capture-v1`
  and reports its prim counts; it computes no quantities and adds no golden
  number. Nothing in §7 changed — 13 PASS / 0 PENDING / 0 FAIL.

- **2026-11-07 — G-8b added and G-8 corrected.** G-8 previously said the kernel
  tolerance was "stricter than report-model's 0.25 m", which left the contract
  ambiguous: G-8b was listed as PENDING on the 0.25 m reading. Decision: the
  kernel tolerance is **0.02 m** and the 0.25 m value from `report-model.js` is
  **rejected** — a wall 25 cm outside a room is not part of that room and
  tolerating it silently adds its run and area to the wrong room's takeoff. G-8b
  is now an executable row asserting that a wall centreline 0.25 m outside the
  boundary is **not** a member, plus aux check A-14 (0.02 m in, 0.03 m out,
  0.25 m out). The kernel was **not** changed.
- **2026-11-07 — P4: the two contracts are now what the code emits.** The
  canonical shapes above are no longer aspirational. `report-v1` is stamped
  `roomplan.report/1`, totals lost their `M2` suffix and gained `wallLength`,
  `paintArea`, `livingArea` and `roomsWithoutArea`, the counts moved under
  `totals.counts`, elements use `id`/`area`/`roomRefs`, warnings carry
  `message`+`severity` and `assumptions[]` replaced `conventions.caveat`.
  `capture-v1` gained `units`/`axes`/`stories`/`raw`, a `source` block with
  `bytes`+`dialect`+`dialectEvidence`, per-record `provenance`, and
  `polygonXZ`/`declaredArea` on rooms. §4 was made literal: `status` is
  provenance only and `coverage` is completeness only, with `included`/`expected`
  counts on the measure — a `partial` subtotal is expressed by its coverage, not
  by a `status` value (the old double use, defect C-6, is gone). A `--md`
  consumer (`scripts/lib/out-md.js`) was added under §6 "one kernel, many
  outputs". No golden number in §7 changed; the golden harness still reports
  13 PASS / 0 PENDING / 0 FAIL.
- **2026-11-07 — G-9 / G-10 made executable.** `planStatistics` (`scripts/lib/plan-statistics.js`)
  and `handoffScope` (`scripts/lib/handoff.js`) are ported from ArchiPlan and
  fixtures were extracted from its tests at commit `299ed31`. Both rows now run
  real data instead of being PENDING.

## 8. Non-goals

Volume from meshes, photorealistic texturing, survey-grade accuracy, DWG
writing (no reliable free writer on iOS), automatic registration of unrelated
scans, and reinterpretation of `coreModel`.

## 9. Migration

The current modules keep working while they are moved behind the contract.
Nothing is deleted until the golden harness passes against the new path and the
old path in the same run.
