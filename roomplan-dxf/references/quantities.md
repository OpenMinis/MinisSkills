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
- Ceilings and volumes are null: no supported explicit closed geometry is decoded
  by this module. Ceiling classification alone is not proof of ceiling geometry.

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

Report schemaVersion is `report1`, with source SHA256/byte count, AI-sized summary,
unique element records, rooms, stories, totals and warnings. No private coordinate
metadata is copied; report contains no element coordinates (IDs and labels remain
user data). The canonical `--model` output remains separate and fuller.

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
