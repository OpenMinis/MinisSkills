# RoomPlan JSON formats read by this converter

These notes describe the subset this package decodes. They are a reverse-
engineered working contract, not an official Apple or vendor schema, and not
a promise that every export from every iOS version will decode. Unsupported
shapes fail loudly; nothing is guessed silently.

Geometry lengths are metres, areas square metres, direction angles degrees unless explicitly named radians, and confidence/quality metrics retain source conventions. Transforms are 4x4 **column-major** arrays of 16
numbers: `m[0..2]` = X axis, `m[4..6]` = Y, `m[8..10]` = Z, `m[12..14]` =
translation. Elevation of an element is `m[13]`.

## Project directory input

A directory replaces a single file; the choice is by rule, never by guesswork:

| role | candidates, first match wins |
|---|---|
| scan | `optimized_roomplan.json`, `roomplan.json`, `data/scan.json`, `scan.json` |
| metadata | `meta.json`, `data/meta.json` |

Any further scan candidate present is reported in
`roomplan.directory-multiple-scans`. An empty directory is an error (exit 1),
never an empty drawing.

`meta.json` (Polycam-style project metadata) fields read — everything else is
ignored:

| field | type | used as |
|---|---|---|
| `name` | string | default title-block project name |
| `latitude`, `longitude` | number | fallback for `latLonAlt` when the scan has none |
| `headingDegrees` | number | fallback for `orientation.orientation_degrees` |
| `floorAreaSquareMetres` | number | `sourceMeta.floorAreaSquareMetres` |
| `wallAreaSquareMetres` | number | read, not written |
| `roomCount` | integer | `sourceMeta.roomCount` |
| `createdAt` | number | title-block date; Unix epoch seconds **or** Apple reference-date seconds (≥ 1e9 = Unix) |
| `id` | string | `sourceMeta` only |

Rules:

1. **Scan values always win.** `meta.json` only fills fields the scan lacks, so
   a drawing is never georeferenced by assumption.
2. Every fallback is recorded: `sourceMetadata: "meta.json"`,
   `metadataFallbackFields: ["latitude","longitude","orientationDegrees"]`,
   plus `roomplan.meta-metadata-fallback` and `roomplan.heading-from-meta`.
3. `meta.json` carries **no confidence** for its heading; anything derived from
   it is therefore `approx` in `northArrow`, never `source-provided`.
4. `createdAt` is normalised to `YYYY-MM-DD`; implausible values (before 1990
   or after 2200) are dropped rather than printed.

### Polycam raw variant (`scan.json` with `rooms[0].coreModel`)

`data/scan.json` in a Polycam project is a `CapturedStructure`-shaped wrapper
whose room record carries extra keys — `coreModel` (an opaque base64 mesh),
`version`, `story`, `sections`, `referenceOriginTransform`,
`completedEdges`, `curve: null`. `decode-raw.js` already accepts this shape:
`roomRecords()` returns `root.rooms`, and the per-element decoder reads only
the fields it documents, ignoring the rest. Verified on a real project
directory (one room, 10 walls, 5 doors, 2 windows, 14 objects, 1 floor): the
conversion succeeds with no special-casing, so no normalisation layer was
added. `coreModel` is never decoded or uploaded.

## Dialect detection (content, not filenames)

- Explicit `format_version: 1` selects optimized-v1; its geometry must validate.
- Any other explicit `format_version` (including null/string/99) is rejected;
  it is never guessed to be 1 and never falls back to raw.
- Legacy **unversioned** optimized requires all six element arrays, nonempty
  walls and rooms, and alignment_transform. Numeric room polygons/centres,
  element dimensions and matrices must validate. Its dialect remains
  `optimized-legacy-unversioned`, not v1.
- Raw requires nonempty element arrays at the root or in each supported
  room/session wrapper. Mixed/ambiguous shapes fail clearly. Isolated
  category/label/meshInfo, a filename or an empty walls array is not evidence.

`sourceDialect` and `dialectEvidence` are recorded in the manifest and the
optional capture model. Directory filename priority only chooses a file:
content determines its dialect. Nothing is downloaded.

## Raw Apple export

Accepted wrappers, flattened into one element list:

1. a single `CapturedRoom` at the root (`walls`, `floors`, `doors`, `windows`,
   `openings`, `objects`);
2. `{ "rooms": [CapturedRoom, ...] }` (`CapturedStructure`);
3. `{ "captureSessions": [ { "roomplanSessions": [CapturedRoom, ...] } ] }`.

Empty `rooms`, empty `captureSessions` or a session without
`roomplanSessions` is an error, never an empty drawing.

Element fields read: `identifier`, `parentIdentifier`, `category` (string or a single tagged key),
`confidence` (string or a single tagged key), `story`, `dimensions [x,y,z]`, `transform`,
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

## Optimized export (explicit v1 or positively recognized unversioned legacy)

This dialect is a **third-party post-processed export**, commonly produced by
Polycam-style tools. It is not an Apple `CapturedRoom`/`CapturedStructure`
schema, and the field names below are an observed contract from real files
rather than a published vendor specification. Unknown keys are not silently interpreted; unknown explicit versions are unsupported.

`format_version`, when present, must be the integer `1`; other explicit values are rejected without fallback. An absent version is accepted only via the strict legacy adapter above. Elements live in `walls`, `floors`, `doors`, `windows`, `openings`,
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
- A floor identifier is retained if supplied, otherwise generated with provenance from story/record path. Dimensions `{x:1,y:0,z:0}` are marked DXF placeholders, not measurements; geometry comes from polygonCorners and sourceRecords preserves supplied dimensions.
- alignment is the source's own `alignment_transform`, used verbatim; it is
  never recomputed.
- Room polygons and labels are exported. Missing label_automated stays null in the model; DXF prints `[category; id=...]` plus area rather than inventing a room name. Null floor_height is retained as unknown.
- `ceiling*`, edges, curves, joints, attributes and sections are not fully rendered in DXF; recognized fields can be preserved in the optional capture model/sourceRecords.
- Direction is available without --geo (with a source-confidence caveat). Location metadata is opt-in; --model --geo additionally embeds a potentially private verbatim source tree.

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
and lineweights per kind (DOOR 3 green, WINDOW 5 blue, OPENING 6 magenta, all at
the wall's 0.35 mm weight) and writes the entities in **paint order**: floors,
walls, rooms, objects, then the openings, then labels and ceiling annotations.
Openings are single centre lines lying on the wall footprint they interrupt, so
writing them after the walls is what keeps them visible in viewers that paint
the file top to bottom. The emitter re-applies the same order and reports
`drawOrder.openingsAboveWalls` in its summary.

## Output contract

- DXF R2018 (`AC1032`), `$INSUNITS = 6` (metres), modelspace entities only.
- Optional `--model`: `<name>.capture.json`, source-space normalized subset with explicit loss/privacy inventory. See [model-schema.md](model-schema.md).
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

## Validation limits

See [model-schema.md](model-schema.md) for finite numeric bounds, affine/nonsingular matrix checks, nullable fields and privacy. Validation is structural, not a topology or survey certificate.
