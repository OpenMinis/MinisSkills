# USDA grammar as Apple actually writes it

Reference corpus: **105 `.usda` layers** extracted from four Apple `.usdz`
captures (a fifth, `ArchiPlan-BIM-…usdz`, holds a single binary `.usdc` and is
therefore opaque here).

| # | Corpus | Layers |
|---|---|---|
| 1 | `Project hh.usdz` | 33 |
| 2 | `Project Aug 5, 2026 at 2326.usdz` | 29 |
| 3 | `Novi.usdz` | 25 |
| 4 | `BF4C1AE3-…/room.usdz` | 18 |
| 5 | `ArchiPlan-BIM-…usdz` | 0 (`.usdc`, binary crate) |

Every rule below is followed by the file:line where it can be seen with your
own eyes. `tests/lib/usda-lint.js` encodes this table and must pass on all 105
layers (it does); a rule that is *not* in the corpus is reported as a warning,
never as an error, so the corpus — not our taste — stays the authority.

## 1. Prologue

```
#usda 1.0
(
    defaultPrim = "room"
    metersPerUnit = 1
    upAxis = "Y"
)
```
*s4/room.usda:1-6*, *s2/Project Aug 5…usda:1-5* — byte-identical field order
(`defaultPrim`, `metersPerUnit`, `upAxis`) in **105 of 105** layers, always
exactly three entries, one per line, four spaces of indent, ` = ` with one
space on each side, `(` and `)` on their own lines. No `doc`, no `subLayers`,
no comment after the magic line.

## 2. `kind` on every prim

| prim role | metadata | citation |
|---|---|---|
| stage root | `kind = "assembly"` | s2 root:8-9 |
| container ("grp") | `kind = "group"` | s2 root:12-13 |
| captured room | `kind = "assembly"` | s2 root:16-17, 23-24 |
| leaf element | `kind = "component"` | s2 Floor0:17 |

Distribution over the corpus: 20 × `"assembly"`, 61 × `"group"`,
101 × `"component"`, **0 prims without a kind**. The root prim is always the
defaultPrim.

## 3. Where prim metadata lives

In the parenthesis block **after the prim name**, never in the braces
(*s2 Floor0:9-19*):

```
def Xform "Floor0" (
    assetInfo = {
        asset identifier = @./Floor0.usda@
        string name = "Floor0"
    }
    customData = {
        string Category = "Floor"
        string UUID = "7BC4E9B6-2C2C-42EB-8CEE-960221BCECFC"
    }
    kind = "component"
)
{
```
`(` follows the name on the same line, entries are 4 spaces deeper than `def`,
one per line, **no commas**, closing `)` alone at the prim's indent. Entry order
is alphabetical (`assetInfo` < `customData` < `kind`). Dictionary entries are
typed (`string Category = "Wall"`, *s4 Wall0:13-16*).

## 4. Mesh attribute set and order

*s2 Floor0:22-29* — exactly eight properties, in ASCII-alphabetical order, one
per line, no blank lines, no metadata on any of them:

```
int[] faceVertexCounts = [...]
int[] faceVertexIndices = [...]
rel material:binding = </Floor0/Floor0_color>
normal3f[] normals = [...]
point3f[] points = [...]
uniform token subdivisionScheme = "none"
matrix4d xformOp:transform = ( (…), (…), (…), (…) )
uniform token[] xformOpOrder = ["xformOp:transform"]
```

Types are literal: `int[]`, `normal3f[]`, `point3f[]` — never `float3[]`,
never `int64[]`. `matrix4d` is authored as **four rows of four**
(`( (a,b,c,d), (e,f,g,h), … )`, *Floor0:28*).

## 5. `interpolation`

**Does not appear in any of the 105 layers.** `normal3f[] normals` count equals
`point3f[] points` count (24/24 in *s2 Floor0:25-26*; 42/42 in *s1 Floor0*), i.e.
Apple relies on the USD default `interpolation = "vertex"` and gets flat
shading by *splitting vertices per face* instead. Writing
`( interpolation = "faceVarying" )` is legal USDA but has no precedent in the
reference corpus.

## 6. Meshes are triangles

382 of 382 face sizes in the corpus are `3`. No quads, no n-gons. Vertices are
duplicated per face, so `faceVertexIndices` references every point at most once
per face and `normals` lines up 1:1 with `points`.

## 7. Material

Every geometry prim binds a Material and every Material holds a
UsdPreviewSurface shader — 101 Materials for 101 geometry prims
(*s2 Floor0:24, 32-45*):

```
def Material "Floor0_color"
{
    token outputs:surface.connect = </Floor0/Floor0_color/surfaceShader.outputs:surface>

    def Shader "surfaceShader"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor = (1, 1, 1)
        color3f inputs:emissiveColor = (0, 0, 0)
        normal3f inputs:normal = (1, 1, 1)
        float inputs:occlusion = 1
        float inputs:opacity = 1
        token outputs:surface
    }
}
```
The Material is a **sibling of the Mesh** inside the component Xform and is
named `<PrimName>_color`.

## 8. Numerals

Written compactly, whatever the magnitude, with a `.` separator and one space
after each comma inside tuples: `(0.99999994, 1.3069635e-7, 0)`,
`(-0.0364103764295578, 0, 0.999336838722229, 0)` (*s2 Floor0:25-28*). No
padded fixed-width decimals, no `-0`.

## 9. Present but rare

| feature | where | note |
|---|---|---|
| `prepend references` | s2 root:57-61, s4 room.usda:43-50 | parametric asset instancing, root layer only |
| `def Cube` + `double size` + `double3 xformOp:scale` | s2 Wall0:20-26 | furniture/walls as unit cubes, not meshes |

## 10. Never present in the corpus

`extent`, `interpolation`, `apiSchemas`, `payload`, `variantSets`, `over`,
`class`, `inherits`, `add`/`append` (only `prepend`), `timeSamples`,
`customData`/`assetInfo` on an *attribute*, UVs, textures, `displayColor`,
`xformOp:rotateXYZ`/`translate`/`orient`. Apple expresses every placement as a
single `matrix4d xformOp:transform`.

Prim names are `[A-Za-z_][A-Za-z0-9_]*` (e.g. `Wall_0_grp`,
`livingRoom0_centerTop`, `Wall0_color`); no duplicates inside a scope; the Mesh
and its Material share the parent Xform's name (+ `_color`).
