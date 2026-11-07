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
- **Meshes are flat in `Mesh_grp`**, named `<Kind>_<n>` with a per-kind counter
  (`Wall_1`, `Wall_2`, `Floor_1`, …). Objects use `Object_<n>` and carry their
  RoomPlan category in `Category` (`sofa`, `table`, …).
- **Two geometry paths.** A surface with 3D `polygonCorners` becomes that
  polygon: one n-gon in `faceVertexCounts`, indices `0..n-1` (USD triangulates
  n-gons internally; the explicit fan form is equivalent and keeps the vertex
  count inspectable). Anything else becomes an oriented box from `dimensions`
  (x = length, y = height, z = thickness) placed by its 4×4 transform: 8 points,
  6 quads.
- **Thickness.** RoomPlan sometimes reports `dimensions.z = 0` for a wall. The
  exporter substitutes Apple's default **0.16 m** and labels it
  `string Thickness = "assumed"` + `double AssumedThickness` so nobody mistakes
  an assumption for a measurement.
- **Normals** are `faceVarying` (one per face-vertex) so an 8-point box still
  shades flat; they are omitted if any face is degenerate.
- **`subdivisionScheme = "none"`** — polygons are rendered as authored, not
  smoothed into a Catmull-Clark surface.

## What is deliberately missing

- textures and UVs (no `primvars:st*`, no `TfTextureReader`);
- materials, shaders and colours (QuickLook applies its default material);
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
platforms; neither is available in this Linux/iSH environment. A real device must
open the `.usdz` once before it is handed to a client — see the checklist in
README's "USDZ export" section.

## Reading list

- USD ASCII syntax: <https://openusd.org/release/spec_usda.html>
- USDZ package spec (alignment + STORE): <https://openusd.org/release/spec_usdz.html>
- AR Quick Look authoring guidelines (Apple): "Adding a 3D model to your app".
