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
source: { sha256, dialect, captureSchema }
totals: { floorArea, ceilingArea, wallAreaGross, wallAreaNet, openingArea,
          wallLength, paintArea, livingArea?, roomCount, wallCount,
          doorCount, windowCount, objectCount, roomsWithoutArea }
stories: [ { story, label, totals, rooms: [ { id, label, floorArea,
             ceilingArea, ceilingMethod, wallAreaNetBoundary, wallRun,
             boundaryDoorCount, boundaryWindowCount } ] } ]
elements: [ { id, kind, story, area, areaStatus, coverage, reason,
              roomRefs[], slopeCut? } ]
warnings: [ { code, message, severity } ]
assumptions: [ string ]
```

Every numeric field appears as `{ value, status, coverage, reason }` (see §4).
`ceilingMethod` is `supplied | knee | section | extrusion | flat | unavailable`.

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

## 7. Golden numbers (executable)

Synthetic fixtures, all in metres, checked to 1e-4.

| ID | Case | Expected |
|---|---|---|
| G-1 | gable wall 4 × 2.5, ridge 2.5 → 1.6 | gross **8.2000 m²** |
| G-2 | same, cut triangle | **1.8000 m²** removed |
| G-3 | gable room 20 m², eave 1.6, ridge 2.5, knee 5 m | ceiling **21.9317 m²**, method `knee` |
| G-4 | shed roof, same footprint | ceiling **20.5000 m²**, method `knee` |
| G-5 | authored ceiling, 4 vertices 2.0–2.6 m | area per vertex elevations; holes scaled by `ceilingArea/floorArea` |
| G-6 | 1.00 × 1.00 m room, 0.15 m walls, reference edges | interior **1.0000 m²** |
| G-7 | same walls, no reference edges | centerline **1.4400 m²** |
| G-8 | wall on a room boundary | member of that room at tolerance 0.25 m |
| G-9 | ArchiPlan fixture | living **10.9725 m²**, net walls **35 − 1.89 m²** |
| G-10 | handoff fixture | quantity keys present, `gaps[]` for missing areas |
| G-11 | openings 1 m² and 4 m², threshold 3 m² | paint **10 / 1 m²** |
| G-12 | heading 193.7412°, alignment 7.9724° | sheet bearing **354.2°** |

A change to any of these requires an explicit note in this file.

## 8. Non-goals

Volume from meshes, photorealistic texturing, survey-grade accuracy, DWG
writing (no reliable free writer on iOS), automatic registration of unrelated
scans, and reinterpretation of `coreModel`.

## 9. Migration

The current modules keep working while they are moved behind the contract.
Nothing is deleted until the golden harness passes against the new path and the
old path in the same run.
