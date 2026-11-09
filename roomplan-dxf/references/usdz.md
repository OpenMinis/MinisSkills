# USDZ: the format this exporter writes

Short, verified-by-reading-the-bytes notes on the `.usdz` file produced by
`--usdz`. Everything here is checkable with `python3` alone; no USD toolchain is
required and none is assumed.

## A USDZ is a ZIP of `.usda` text

A `.usdz` is an ordinary ZIP archive (PKWARE, no extensions) with three extra
conventions:

1. every entry is **stored** (compression method `0`), never deflated;
2. every entry's file data starts on a **64-byte boundary** (the spec says
   16-byte alignment is allowed; 64 is what Apple's own exports and QuickLook
   use, and it is what this writer produces);
3. the archive holds at least one `.usda` (ASCII) or `.usdc` (binary crate)
   layer, and the **first** `.usda` entry is the root layer
   (`defaultPrim` decides which prim is placed on AR Quick Look).

Nothing else — no manifest file, no directory entries, no compression level.

## What this exporter produces

| Entry | Content |
|---|---|
| `room.usda` | ASCII USD layer, UTF-8, metres, Y up |

ZIP details, all chosen for reproducibility:

- method `0` (STORE), flags `0`, no data descriptors;
- CRC-32 (IEEE, reflected, polynomial `0xEDB88320`) computed locally;
- DOS timestamp pinned to **1980-01-01 00:00** so the same capture yields
  byte-identical output on every run and machine;
- alignment implemented as a ZIP **extra field** of zero padding in the local
  file header, so a standard reader (Python `zipfile`, `unzip`, QuickLook) skips
  it and still finds the payload at the right offset;
- no Zip64: archives and entries must stay under 4 GiB, and the writer raises a
  clear error rather than emitting a corrupt file.

## Invoking it

```sh
node scripts/roomplan-to-dxf.js scan.json out/ --usdz
```

writes `out/scan.usdz` and prints `USDZ written: <path> (N prims)`. The export is
untextured, in metres, Y up, and independent of `--model`/`--report`/`--md` (it
only needs the decoded model). It obeys the same overwrite and source-alias
guards as every other output: an existing `.usdz` is refused unless `--force`
is given.

## Layer structure

```usda
#usda 1.0
(
    defaultPrim = "room"
    metersPerUnit = 1
    upAxis = "Y"
)

def Xform "room"
{
    def Xform "Section_grp"
    {
        def Xform "Kuhinja"
        {
            customData = {
                string Category = "Room"
                string Label = "Kuhinja"
                int Index = 0
                int Story = 0
            }
        }
    }

    def Xform "Mesh_grp"
    {
        def Mesh "Wall_1"
        {
            float3[] extent = [(0.000000, 0.000000, -0.080000), (6.000000, 2.500000, 0.080000)]
            int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
            int[] faceVertexIndices = [0, 3, 2, 1, 4, 5, 6, 7, ...]
            normal3f[] normals = [(0.000000, 0.000000, -1.000000), ...] (
                interpolation = "faceVarying"
            )
            point3f[] points = [(0.000000, 0.000000, -0.080000), ...]
            uniform token subdivisionScheme = "none"
            customData = {
                string Category = "Wall"
                string Identifier = "W-A"
                string Thickness = "assumed"
                double AssumedThickness = 0.160000
                string Geometry = "oriented box from dimensions"
            }
        }
    }
}
```

Notes on the choices that matter:

- **`upAxis = "Y"` and `metersPerUnit = 1`** are RoomPlan's own convention, so
  no axis swap or unit scale is applied. Points are written in source space; the
  DXF sheet rotation (`scripts/lib/align.js`) is drawing-only and is not baked in.
- **`Section_grp` is flat and geometric**: one empty `Xform` per captured room,
  named from the room label sanitised to a USD identifier (`Kuhinja/dnevni` →
  `Kuhinja_dnevni`, `1. kat` → `r_1_kat`). The original label is kept in
  `customData.Label`, because sanitising is lossy.
- **Meshes are flat in `Mesh_grp`**, one `kind = "component"` `Xform` per element
  named `<Kind>_<n>` with a per-kind counter: `Wall_1…`, `Floor_1…`,
  `CeilingSlope_1…`, `CeilingFlat_1…`, `Door_1…`, `Window_1…`, `Opening_1…`,
  `Object_1…`. Objects carry their RoomPlan category in `Category`
  (`sofa`, `table`, …). Code: `scripts/lib/usdz-writer.js` (ZIP) and
  `scripts/lib/usda-export.js` (USD ASCII layer), both written by hand here —
  there is no USD toolchain dependency.
- **Two geometry paths, and walls always have volume.** A surface with 3D
  `polygonCorners` becomes that polygon. For a *floor* that is one flat n-gon
  (planar-validated ear-clipped). For a *wall* it is a plan outline with no thickness, which
  reads as paper and — because back faces are culled — is invisible from the far
  side; so a wall polygon is extruded along the surface's local +Z through the
  thickness into a **prism**: two ear-clipped caps (plan outlines are routinely
  concave) plus one quad per polygon edge, all wound outward
  (`scripts/lib/polygon-prism.js`). Surface area is
  `2·area(polygon) + perimeter·thickness` and the volume is
  `area(polygon)·thickness`, both asserted in `tests/test_wall_prism.js`.
  Anything else becomes an oriented box from `dimensions` (x = length,
  y = height, z = thickness) placed by its 4×4 transform: 8 points, 6 quads.
- **Thickness.** Precedence is `dimensions.z`, then the source's
  `wallThickness`, then Apple's default **0.16 m**. RoomPlan sometimes reports
  `dimensions.z = 0` for a wall; an unmeasured wall gets the 0.16 m default and
  is flagged `string Thickness = "assumed"` + `double AssumedThickness`, so
  nobody mistakes an assumption for a measurement.
- **Real door and window holes.** A wall that an opening names in
  `parentIdentifier` is *cut*, never merely overlaid. Each opening is projected
  onto the wall's own axes (u = 0…length, v = 0…height, w = ±thickness/2), all
  u and v boundaries form a grid, and only the cells outside every opening are
  emitted: the front and back faces have genuine holes, each opening edge turns
  into a reveal face, and the result stays a closed solid with every normal
  pointing outward. Overlapping openings are cut once (the union). An opening
  that cannot be placed sensibly — no 4×4 transform, no positive width/height,
  more than 20 mm outside the wall, or a wall exported from `polygonCorners`
  (an n-gon, not a box) — is **not** cut: the wall stays solid and the manifest
  records `usdz.opening-not-cut`. An overshoot under 20 mm is clamped to the
  wall and recorded as `usdz.opening-clamped`. A cut wall carries
  `string Geometry = "box with openings cut out (grid decomposition)"`,
  `int Openings`, `double CutArea` and `double ExposedArea`; the separate
  `Door_*` / `Window_*` / `Opening_*` prims are kept (Apple keeps
  `Window0.units` beside its wall) and marked `customData Role = "opening"`.
  Code: `scripts/lib/wall-holes.js`, tests: `node tests/test_wall_holes.js`.
- **Normals** are one per face-vertex, ordered so an 8-point box still shades
  flat without any `interpolation` metadata (the `(...) ( interpolation =
  "faceVarying" )` form some samples show is legal USD but not written here);
  they are omitted if any face is degenerate.
- **`subdivisionScheme = "none"`** — polygons are rendered as authored, not
  smoothed into a Catmull-Clark surface.
- **Each mesh prim also contains its own `def Material "<Name>_color"`**
  (`UsdPreviewSurface`) that the mesh binds with `rel material:binding`, so
  doors (3/green), windows (5/blue) and openings (6/magenta) keep their plan
  colours in AR Quick Look.
- **The one exception is an OPENING** (`Door_`/`Window_`/`Opening_`): an empty
  `Xform` carrying `Label`, `Width`, `Height` and `Role = "opening"` and no mesh
  at all, because the hole the wall was cut for is the element. Prim metadata
  always sits in the parenthesis block after the prim name, never inside the
  braces.
- The whole layer shape was copied from Apple's own exporter (105 reference
  layers), so it is what AR Quick Look already expects.

## Meshes, planarity and metadata

- `polygonCorners` → that polygon, validated planar and ear-clipped (all mesh
  faces use `scripts/lib/planar-polygon.js`; vertices are never angle-sorted).
  Non-planar or self-intersecting rings and unsupported explicit hole rings fail
  clearly instead of inventing a filled polygon. Grid-decomposed opening cells
  remain separate faces, preserving their holes.
- Every mesh is triangulated and its vertices are split per face-vertex (a box =
  12 triangles / 36 vertices), so `normal3f[] normals` carries one normal per
  point and no `interpolation` metadata is written — Apple's shape.
- `SurfaceArea3D`, `ProjectedArea` and `RenderMeshArea` are separate USD metadata;
  the legacy ceiling `Area` stays footprint for compatibility.
- Supplied ceiling sums retain every source plane, including vertical upstands
  and 0.84 m low ceilings; multiplicity/alternative source hypotheses warn and
  are not a verified physical total. Unknown relative height is null, never
  inferred from stage zero.
- A prim with a non-finite transform or no usable geometry is skipped with a
  warning (also in the manifest) — the layer never contains `NaN`.
- Source space is used as-is; the DXF sheet rotation is **not** applied.

## Ceilings in USDZ

Ceilings (`scripts/lib/ceiling-3d.js`) are real solids, so they are visible in AR
Quick Look instead of being an annotation a USDZ cannot carry. USDZ ceiling meshes
are OFF by default: `--usdz --usdz-ceilings` opts in, `--no-usdz-ceilings` turns
them off, the last toggle wins, and this is independent of the DXF `--ceilings`
switch (source-region metadata may remain even without meshes).

- A knee profile is **two prims** — `CeilingSlope_<n>` (the band from the knee up
  to the ridge, `Geometry = "sloped strip"`, `Method = "knee"`) and
  `CeilingFlat_<n>` (the remainder, `Geometry = "flat plane"`, `Method = "flat"`)
  — never one tilted sheet across the whole room.
- A flat ceiling is ONE prim with 2 triangles and normal −Y (seen from below); a
  gable is two `CeilingSlope_` planes meeting at a ridge, plus a `CeilingFlat_`
  plateau only when the section has a flat segment.
- `double Area` on each prim is its own FOOTPRINT area, so the strip's area stays
  checkable against `run × room depth`.
- The method is never used to invent geometry: `extrusion`/`unavailable` become a
  flat plane at the knee height plus `usdz.ceiling-approximated`, and a room with
  no footprint polygon gets no ceiling at all plus `usdz.ceiling-no-polygon`.
- Because Quick Look renders no text, room and ceiling prims carry the label in
  `customData`: `string Label`, `double Area`, `string Height` (`"2.50"` or
  `"1.60-2.50"`), `string Method`.

## Tests

- `node tests/test_usdz.js` — 40 checks; opens the produced ZIP with Python's
  `zipfile` and asserts `testzip() === None`.
- `node tests/test_wall_holes.js` — 16 checks: measured front area after cutting,
  watertight edges, outward normals, refusal warnings.
- `node tests/test_planar_polygon.js`, `python3 tests/test_planar_polygon_shapely.py`
  (requires Shapely) and `node tests/test_source_preservation.js` cover planarity
  and source preservation.
- `node tests/test_wall_prism.js` asserts the prism area/volume formulas above.

## What is deliberately missing

- textures and UVs (the per-mesh `UsdPreviewSurface` material has a constant
  colour only, no texture);
- cameras, lights, physics, semantics/`SemanticsLabels` beyond `customData`;
- RealityKit / RoomPlan mesh reconstruction (this is analytic geometry from the
  capture records, not a triangle soup from the device's mesh).

An untextured model is smaller, diffable and honest: it shows exactly the
geometry the capture contains.

## Validating it without Apple tooling

```sh
# 1. the container: opens, lists, and every CRC checks out
python3 -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); \
print(z.namelist(), z.testzip())" out/scan.usdz

# 2. the alignment: every payload begins at a 64-byte boundary
python3 -c "
import zipfile,sys
for i in zipfile.ZipFile(sys.argv[1]).infolist():
    off = i.header_offset + 30 + len(i.filename.encode()) + len(i.extra)
    print(i.filename, off, off % 64)
" out/scan.usdz

# 3. the layer itself
unzip -p out/scan.usdz room.usda | head -40
```

What this can prove: the archive is a valid ZIP, the CRCs are right, the
payloads are aligned, the layer's text is what we meant to write, and the output
is reproducible.

What it **cannot** prove: that Apple's own validator or AR Quick Look accepts the
file. `usdchecker` ships with Pixar's USD, and QuickLook only exists on Apple
platforms. User-confirmed Apple opening and separately recorded OpenUSD tests
are available, but not Apple certification. Review each delivered model — see the checklist in
README's "USDZ export" section.

## Reading list

- USD ASCII syntax: <https://openusd.org/release/spec_usda.html>
- USDZ package spec (alignment + STORE): <https://openusd.org/release/spec_usdz.html>
- AR Quick Look authoring guidelines (Apple): "Adding a 3D model to your app".

Release defaults (DXF ceiling annotations ON, USDZ ceiling meshes OFF, and the
per-build default for location lookup) are listed once in
[quantities.md](quantities.md#release-defaults-and-validation-2026-11-09).
