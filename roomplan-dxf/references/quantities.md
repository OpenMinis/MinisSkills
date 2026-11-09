# Independent quantity engine — scope and formulas

`quantities.js` exports `buildReport(decodedCapture, sourceRoot = {})`,
`quantitiesCSV(report)`, `csvCell(value)`, `polygon3D(points)`, `inPolygon(point, polygon, tolerance)`.
The first argument is the **decoded internal capture**, before any DXF layout
translation; pass parsed original JSON as second argument to retain raw source-room
links and declared room areas. No mutation, file I/O, networking or geocoding occurs.
CLI ownership and write guards remain with the caller.

This is **new independent code**, not a transfer or comparison of the unavailable
ArchiDrawing `web/report-model.js` / `report-export.js`. Historical knowledge about
`assignRoomMembership` informed requirements, not a claim of source equivalence.

## Geometry

- Coordinates: local polygon points transformed by each surface's source transform.
  Architectural alignment and DXF per-floor sheet translations are not used.
- Polygon area: Newell normal `N = sum((yi-yj)(zi+zj), (zi-zj)(xi+xj),
  (xi-xj)(yi+yj))`; area = `|N|/2`. Minimum three nonduplicate points,
  positive area, planarity within `1e-5 m`, and no nonadjacent edge intersection.
  Closed last-point repetition is accepted. Curved, nonplanar, self-intersecting,
  degenerate and nonrigid-transformed surfaces return `null`, with a reason.
- Walls and apertures without polygonCorners: source `dimensions.x * dimensions.y`
  on a rigidly transformed rectangular plane. This is **estimated**, not a
  verified measured rectangle. It is explicit source dimensional modelling.
- Floors: polygonCorners area in their actual 3D local plane, never `.y` as floor
  height. With no polygon, the two largest positive source bounding-box dimensions
  give an **estimated** area with warning; generated optimized floor placeholder
  dimensions cannot supply quantities. Invalid supplied polygons do **not** fall
  back to dimensions.
- Wall net: gross minus apertures with explicit matching parentIdentifier, matching
  story, valid geometry, all aperture vertices in a convex wall polygon and wall
  plane distance <= `0.01 m`. Concave wall clipping is unsupported. Projected
  aperture bounding boxes with positive-area overlap cause net `null`; no double
  subtraction or approximate union. Negative net refused. A missing/unlinked or
  ambiguous parent never subtracts anything and makes story/building net coverage
  partial. Touching projected bounding boxes alone are not positive-area overlap.
- Thickness: positive source wallThickness, otherwise positive source dimensions.z;
  no renderer default is introduced. Missing thickness is null.
- Room source `.area` and derived polygon area are separate measures, with a signed
  polygon-minus-declared difference. Raw room polygons are never invented. Curved
  optimized room boundaries are unsupported for polygon area/membership inference.
- Ceiling areas use supplied 3D polygons with plan-union accounting (or a
  diagnosed zero-plan-extent surface-sum fallback), then explicitly labelled
  wall-profile reconstruction when no supplied geometry exists. These are not
  physically verified building totals. Closed verified volumes remain null.

## Identity, memberships, totals

`kind:identifier` deduplicates source records. Repeated IDs retain all record/room
provenance; conflicting geometry or story prevents measured area. Anonymous records
remain distinct. Source-room index/identifier links and optimized room edge/aperture
references are supplied memberships. Only then does optimized XZ point-in-polygon
infer membership; furniture/apertures use center, walls both endpoints and midpoint,
with `0.02 m` boundary tolerance. Inference is always labelled `inferred`.
Shared walls may reference two rooms but occur only once in story/building totals.
Room-side counts and gross wall-area references are explicitly not additive.

`supplied`: source scalar; `computed`: validated polygon; `estimated`: explicit
source dimension assumption; `unavailable`: null with reason. Aggregate `complete`
means every applicable **decoded element** has a number, not whole-building
completeness. `partial` includes numeric subtotal and missing-element reasons.
No applicable source elements yields null, never a fake area of zero. Counts of
absent decoded classes are zero counts, not proof of capture completeness.
Metadata `floorAreaSquareMetres` is reference-only, never additive. Detailed records
carry individual coverage while totals flag estimated if any term is estimated.

## Output and security

Report schemaVersion is `roomplan.report/1`, with source SHA256/byte count,
summary, unique element records, rooms, stories, totals and warnings. Location
lookup is not required. Surface Region records and opening diagnostics can
contain source geometry; IDs and labels also remain identifying user data.
Keep reports local. The optional `--model` output remains separate and fuller.

CSV: UTF-8 BOM, semicolon separator, CRLF, doubled quotes and quoted fields when
containing semicolon, newline or quote. Non-numeric strings whose first nonwhitespace
character is `=`, `+`, `-` or `@` receive an apostrophe formula guard before quoting.
Nulls are blank. Room memberships/provenance are JSON cells. CSV contains unique
**element rows**; room declarations and aggregate coverage remain in report JSON.

## Dijagnostika otvora i clipping (7.11.2026)

`wall.openingDiagnostics[]` čuva točan dokaz za svaki parent-linked otvor:
vrhove u parent-local mm, potpisane udaljenosti od ravnine zida (mm),
prekoračenja bboxa po osi (mm), `containedVertices`, površinu zida/otvora,
`intersectionAreaM2`, `outsideAreaM2`, `maxOutsideDistanceM` i `convexWall`.

Neto pravilo ostaje strogo: otvor se odbija samo ako je u cijelosti unutar
konveksnog zidnog poligona. Jedna iznimka je numerički dokazana: za
**dimenzijske pravokutnike** smije se odbiti točan konveksni presjek kad je
prekoračenje ≤ 1 µm i vanjska površina ≤ 1e-5 m² (`clippingApplied: true`).
Sve veće ili poligonalno odstupanje ostaje `null`, bez proširenja EPS-a.

## Bojanje — trade površina (7.11.2026)

`wall.paintAreaM2` je **zasebno** polje uz `netAreaM2`; neto ostaje geometrijski
točan broj. Prag je imenovana konstanta `PAINT_FREE_OPENING_M2 = 3` (izvoz iz
`quantities.js`): otvor do praga se **ne odbija**, iznad praga odbija se samo
višekratnik preko praga (otvor 4 m² → odbija se 1 m²). Pravilo se primjenjuje po
otvoru, ne na zbroj (dva otvora po 2 m² ne odbijaju ništa). `wall.paintRule` nosi
`thresholdM2`, `deductedM2` i politiku; `totals.paintAreaM2` je zbroj s
`{value, status, coverage, reasons}` i postaje `partial` kad ima nevezanih otvora.
CSV dobiva tri kolone: `Povrsina_bojanje_m2`, `Bojanje_pokrivenost`,
`Bojanje_odbijeno_m2`. Nepoznata površina otvora → `null` s razlogom, nikad
besplatno bojanje. Konvencija je u `report.conventions.paintFreeOpeningM2`.

Dodatni moduli istog ugovora: `authored-ceiling.js` (strop zadan poligonom i
visinom po vrhu, Newell 3D, rupe skalirane faktorom `ceilingArea/floorArea`) i
`interior-area.js` (`interiorRoomArea` scanline bez otisaka zidova te
`centerlineArea`).

## Ceiling envelope (2026-11-08)

`totals.ceilingArea` and `rooms[].ceilingArea` use a plan-union accounting
**envelope where available**, with an explicit surface-sum fallback for a
zero-plan-extent supplied face. Several supplied surfaces can
describe the same plan footprint at different heights (stacked alternatives) or
overlap as competing hypotheses; summing them counted the same square metre
twice or three times.

- `scripts/lib/polygon-union.js` computes the exact plan area of the union of
  the footprints (x-sweep: split every edge at every crossing, evaluate the
  spanning edges at each slab midpoint, merge the intervals of all rings, then
  integrate). No rasterisation, no bounding box, no approximation.
- Each surface contributes `exclusivePlanArea × surfaceArea/planArea`, so a real
  slope keeps its developed area (`tilt > 1`) and a stacked duplicate adds
  `0 m2`. Exclusive parts are assigned largest surface first.
- Reported diagnostics: `surfaceAreaSumM2` (the old sum), `overlapAreaM2`
  (footprint double counted), `doubleCountAvoidedM2`, `orderSensitive` +
  `boundsM2` when overlapping surfaces have different tilts
  (`roomplan.ceiling-envelope-order-sensitive`), and `usedFallback` when a
  supplied surface has no plan extent at all — a vertical plane cannot be
  unioned in plan, so that room keeps the sum and warns
  `roomplan.ceiling-envelope-unavailable`.
- Per-surface Surface Region records, labels, heights and the manifest
  `ceilingDiagnostics.records[]` are unchanged; the per-room envelope is
  additionally listed in `ceilingDiagnostics.envelope[]`.
- Source-derived arithmetic on the an anonymized regression example scan: ceiling total `100.321 m2`
  as a surface sum, `69.647 m2` as the current accounting result, **including
  one surface-sum fallback zone**; one room went from `41.737` to `19.636 m2`
  (its declared room area), another from `12.880` to `4.306 m2`. None of these
  numerical matches independently verifies the built ceiling. Largest-face-first
  is not physical selection. `supplied/complete` denotes provenance/source-zone
  coverage; `orderSensitive` is a conservative tilt-difference flag (threshold
  0.01, including disjoint faces), and its bounds are not field measurements.
- Coverage: `node tests/test_ceiling_envelope.js` (10 checks) plus the
  envelope assertions in `tests/test_source_preservation.js`.

## CLI usage

```sh
node scripts/roomplan-to-dxf.js scan.json out/ --report --no-place-lookup
node scripts/roomplan-to-dxf.js scan.json out/ --report --md --no-place-lookup
```

`--report` additionally writes `scan.report.json` and `scan.quantities.csv`;
add `--md` for the Markdown summary `scan.md` (it implies `--report`). Combine
with `--model` for the normalized capture. CSV uses a UTF-8 BOM and `;`.
Reports obey the same output-overwrite and source-alias protections as the DXF,
and report generation is local: it does not require location lookup or an
external review service.

`report-v1` (§3) carries `totals{floorArea, ceilingArea, wallAreaGross,
wallAreaNet, openingArea, wallLength, paintArea, livingArea, roomsWithoutArea,
counts{...}}`, `elements[].id/area/roomRefs`, `warnings[{code,message,severity}]`
and `assumptions[]`, plus the `statistics` (G-9) and `handoff` (G-10) blocks in
the same file.

Read this file before relying on totals. Source room areas, polygon-computed
areas, dimension-estimated wall areas and unavailable values are distinct.
Shared wall references are not additive. Net wall areas subtract only validated
parent-linked openings; incomplete coverage yields a **partial subtotal**, not a
complete building quantity. Ceiling areas use supplied-source accounting or an
explicitly labelled reconstruction; a closed verified volume remains
unavailable. Plan-statistics and handoff calculations are ported from ArchiPlan
and checked against synthetic fixtures, not field measurements. No survey
accuracy is implied.

## Tests

- `node tests/test_quantities.js` — net/paint/CSV safety.
- `node tests/test_authored_ceiling.js` — authored 3D ceiling (G-5).
- `node tests/test_interior_area.js` — interior vs centreline area (G-6/G-7).
- `node tests/test_plan_statistics.js` — G-9: gross/net per level, living/gross,
  `roomsWithoutArea` from an ArchiPlan fixture.
- `node tests/test_handoff.js` — G-10: per-room boundary figures, `quantities[]`
  keys, `gaps[]`.
- `node tests/test_ceiling_envelope.js` — the plan-union envelope (10 checks).
- `node tests/test_spec_golden.js` — all thirteen SPEC §7 golden rows.

## Release defaults and validation (2026-11-09)

DXF ceiling annotations are ON by default; `--no-ceilings` affects DXF only.
USDZ ceiling meshes are OFF by default: use `--usdz --usdz-ceilings` to opt in,
or `--no-usdz-ceilings` to turn them off; the last USDZ toggle wins. These
controls are independent, and source-region metadata may remain even without
meshes. Conversion itself is offline; only the optional Apple reverse geocoder
may use network services, and it runs only when `--place-lookup` is passed
explicitly. **Location lookup is OFF by default in this build**;
`--no-place-lookup` is still accepted explicitly. The user has confirmed opening a generated USDZ on Apple and the
separate OpenUSD tests were run; that is not Apple certification of every
output, and structural tests do not establish physical accuracy.
