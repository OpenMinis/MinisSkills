# RoomPlan JSON formats read by this converter

These notes describe the subset this package decodes. They are a reverse-
engineered working contract, not an official Apple or vendor schema, and not
a promise that every export from every iOS version will decode. Unsupported
shapes fail loudly; nothing is guessed silently.

All numbers are metres. Transforms are 4x4 **column-major** arrays of 16
numbers: `m[0..2]` = X axis, `m[4..6]` = Y, `m[8..10]` = Z, `m[12..14]` =
translation. Elevation of an element is `m[13]`.

## Dialect detection

| Signal | Dialect |
|---|---|
| `rooms[0].label` / `.category` / `.meshInfo` present | optimized |
| `captureSessions[]` present | raw |
| `rooms[]` array, or root `walls`/`surfaces`/`objects` | raw |

The filename is irrelevant. `meshInfo` only participates in detection; it is
never decoded. Nothing is downloaded.

## Raw Apple export

Accepted wrappers, flattened into one element list:

1. a single `CapturedRoom` at the root (`walls`, `floors`, `doors`, `windows`,
   `openings`, `objects`);
2. `{ "rooms": [CapturedRoom, ...] }` (`CapturedStructure`);
3. `{ "captureSessions": [ { "roomplanSessions": [CapturedRoom, ...] } ] }`.

Empty `rooms`, empty `captureSessions` or a session without
`roomplanSessions` is an error, never an empty drawing.

Element fields read: `identifier`, `parentIdentifier`, `category` (first key),
`confidence` (first key), `story`, `dimensions [x,y,z]`, `transform`,
`polygonCorners`, `curve`, and `category.door.isOpen` for doors. Objects carry
the same fields minus corners/curve.

Semantics used:

- length = `dimensions.x`, height = `.y`, thickness = `.z` for walls and
  openings. For floors `.y` is **not** a height; both `.x` and `.y` are
  horizontal, so floor geometry comes from `polygonCorners` instead.
- `transform` and `polygonCorners` stay in local space at decode time.
  Transform and alignment are applied only when projecting, to avoid double
  transformation.
- `curve` (curved walls) is detected only so the wall can be excluded from the
  alignment estimate; the curve itself is not exported.
- Wall `polygonCorners` is ignored. Non-uniform walls and beams (iOS 17+) are
  therefore a known loss.

Story assignment is per **room**, not per surface:

1. if every room reports a numeric `story` and the values differ, those values
   are used;
2. otherwise rooms are clustered by floor elevation (median floor `m[13]`, or
   median wall bottom when no floor exists) with a 0.8 m tolerance;
3. a single room is one story.

Per-surface `story` values from raw exports are unreliable (a real export can
carry `story: 0` on upper-floor elements), so clustering deliberately
overrides them.

## Optimized export (`format_version: 1`)

This dialect is a **third-party post-processed export**, commonly produced by
Polycam-style tools. It is not an Apple `CapturedRoom`/`CapturedStructure`
schema, and the field names below are an observed contract from real files
rather than a published vendor specification. Treat unknown keys and versions
as unsupported.

`format_version` must be the integer `1`; any other value is rejected without
fallback. Elements live in `walls`, `floors`, `doors`, `windows`, `openings`,
`objects`; rooms in `rooms[]`.

Fields read:

- room: `id`, `label_automated`, `category`, `story`, `area`, `floor_height`,
  `vertices_x[]`, `vertices_z[]`, `center_xz[2]`, `edges`,
  `ceiling_lidar_avg_diff`, `ceiling_lidar_valid_pct`;
- element: `identifier`, `parentIdentifier`, `category`, `category_detail`,
  `confidence`, `story`, `dimensions`, `transform`, `polygonCorners`,
  `wall_thickness`;
- root: `alignment_transform` (16-number array **or** an object with
  `t00,t10,t20,t30,t01,…` in column-major order), `latLonAlt`, `orientation`,
  `joints` (count only).

Differences from raw:

- `story` is taken from the source; no clustering
  (`storyAssignmentMethod: "source-provided"`).
- `floor` elements are synthetic: identifier `floor-<story>`, dimensions
  `{x:1,y:0,z:0}`. Their geometry still comes from `polygonCorners`.
- alignment is the source's own `alignment_transform`, used verbatim; it is
  never recomputed.
- room polygons and labels are exported (outline + `label  area m2` text).
- `source`, `ceiling*`, `edges` and the content of `joints` are not used.
- `latLonAlt` and `orientation` are copied into the manifest metadata. Treat
  them as location-sensitive.

## Projection and output geometry

Ground-plane point `(x, z)` becomes DXF `(x, -z)`. The minus on Z is
load-bearing: without it the plan is mirrored. Points pass through the
element transform, then the alignment transform, then the projection.

| Element | Output |
|---|---|
| floor | closed polyline from `polygonCorners` |
| raw wall, thickness > 0 | footprint rectangle (width `.x`, depth `.z`) |
| raw wall, thickness <= 0 | centreline (manifest warning) |
| optimized wall | footprint (width `.x`, depth `wall_thickness` or `.z`, else 0.1) |
| door / window / opening | centreline of length `.x` |
| object | footprint rectangle (`.x` by `.z`), never a text label |
| optimized room | closed polyline plus a text label at `center_xz` |

Raw alignment is a wall-length-weighted orthogonal circular mean of wall
directions (`atan2(-m[2], m[0])`, weighted by `4*angle`), rounded to the
nearest 90°, and applied only on export. A source whose total weight is
effectively zero or whose yaw is below 1e-12 keeps an identity matrix.

Layers follow `S<story>_<KIND>` with KIND in `WALL`, `FLOOR`, `DOOR`,
`WINDOW`, `OPENING`, `OBJECT`, `ROOM`, `LABEL`; the DXF writer assigns colours
and lineweights per kind.

## Output contract

- DXF R2018 (`AC1032`), `$INSUNITS = 6` (metres), modelspace entities only.
- Manifest `<name>.roomplan.json`: `lossy: true`, source SHA-256, dialect,
  story count/method, alignment, entity count, layers, warnings.
- Raw input never yields room polygons, labels, ceiling or mesh geometry.
- Nothing is written back to the input, and an existing output file is
  refused unless `--force` is passed.

## Known losses

Curved walls, non-uniform wall polygons/beams, meshes, ceilings, semantic
category details not listed above, furniture shape beyond a bounding
footprint, and any multi-session registration other than the shared AR space
of the capture. Scan accuracy is whatever the device produced; audit proves
file structure only.

## External references

- <https://developer.apple.com/documentation/roomplan>
- <https://developer.apple.com/documentation/roomplan/capturedroom>
- <https://developer.apple.com/documentation/roomplan/capturedstructure>

Framework context only; JSON encoding stability is not guaranteed by Apple.
