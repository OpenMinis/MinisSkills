# roomplan-dxf

Convert Apple RoomPlan JSON scans (raw `CapturedRoom`/`CapturedStructure`, or
an optimized explicit-v1 or validated unversioned-legacy export) into a 2D DXF floor plan in metres,
with a manifest that states every loss and assumption. A whole project
directory can be passed instead of a file: the scan and an optional
`meta.json` are found by rule. The sheet can carry a frame, a title block and
a north arrow. Includes an offline DXF audit helper and a self-test. No
network access, no upload, no capture.

```
scan.json ─┐
meta.json ─┴─► roomplan-to-dxf.js ──► scan.dxf + scan.roomplan.json
                (or a directory)          │  ├─ frame + title block (FRAME/TITLE)
                                          │  └─ north arrow (NORTH)
                                          └──► inspect_dxf.py (audit)
```

## Requirements

- **Node.js 16+** — the converter is plain CommonJS with zero npm packages.
- **Python 3.9+ with [ezdxf](https://ezdxf.mozman.at/) 1.4+** — used by
  `lib/dxf-emit.py` to write a structurally valid DXF, and by the audit
  helpers. ezdxf is a separate dependency under its own MIT licence; it is not
  bundled here.

```sh
# Debian/Ubuntu
sudo apt install nodejs python3 python3-pip
python3 -m pip install "ezdxf>=1.4"

# macOS (Homebrew)
brew install node python3
python3 -m pip install "ezdxf>=1.4"

# Alpine
apk add nodejs python3 py3-pip
python3 -m pip install --break-system-packages "ezdxf>=1.4"
```

`ezdxf` is not in the Alpine package repository, so pip is normally required
there. Verify with:

```sh
node -v
python3 -c "import ezdxf; print(ezdxf.__version__)"
```

## Install as a skill

Place this directory as `roomplan-dxf/` in your Minis skills directory (or any
skill collection) and run the commands from that directory. Nothing outside the
chosen output directory is written.

## Usage

```sh
# Convert; outputs default to ./out next to the input
node scripts/roomplan-to-dxf.js scan.json

# Explicit output directory
node scripts/roomplan-to-dxf.js scan.json build/

# Overwrite existing outputs (refused by default)
node scripts/roomplan-to-dxf.js scan.json build/ --force

# Also copy source location/compass metadata into the manifest (opt-in)
node scripts/roomplan-to-dxf.js scan.json build/ --geo

# Convert a whole project directory (scan + optional meta.json found by rule)
node scripts/roomplan-to-dxf.js "My scan project/" build/

# Title block: project/author/scale/sheet, and switching the sheet furniture off
node scripts/roomplan-to-dxf.js "My scan project/" build/ \
  --project "Kuca HH" --author "Ana" --scale "1:100" --sheet A-101
node scripts/roomplan-to-dxf.js scan.json build/ --no-frame

# Location cell: free text, or one reverse geocode through the LOCAL Apple helper
node scripts/roomplan-to-dxf.js scan.json build/ --place "Zagreb, Hrvatska"
node scripts/roomplan-to-dxf.js scan.json build/ --place-lookup

# North arrow: flipped formula is the DEFAULT, legacy formula is one flag away
node scripts/roomplan-to-dxf.js scan.json build/ --no-north-flip

# Also write an AR Quick Look model (independent of every other output)
node scripts/roomplan-to-dxf.js scan.json build/ --usdz

# Audit the result
python3 -B scripts/inspect_dxf.py build/scan.dxf
```

Options: `--force`, `--geo`, `--model`, `--usdz`, `--no-place-lookup`, `--project <text>`, `--author <text>`,
`--scale <text>`, `--sheet <text>`, `--place <text>`, `--place-lookup`,
`--north-flip` (default), `--no-north-flip`, `--no-frame`. Unknown options and
missing option values are rejected with exit 1; an existing output without
`--force` exits 2.

`--geo` never georeferences the drawing. It only copies `latLonAlt` and compass
values present in an optimized source into `sourceGeo` (including the 0–1
`orientationConfidence`; below 0.8 triggers a warning), adds a warning, and
should be used only when the recipient needs the provenance point. Coordinates
are sensitive: keep them local and redact them from shared reports. Without --geo, geographic metadata is withheld from the optional capture model; source geometry, IDs and labels remain identifying, and the ordinary title/manifest can still contain user-supplied project/place text.

The converter prints the detected dialect, story count, alignment angle,
entity/layer counts and warning count. Exit codes: `0` success, `1` usage or
conversion error, `2` refusing to overwrite an existing output.

Example audit output (abridged; `0` and `Defpoints` are ezdxf's system
layers):

```json
{
  "audit": {"errors": 0, "fixes": 0},
  "dxf_version": "AC1032",
  "entities": {"LINE": 2, "LWPOLYLINE": 5, "TEXT": 1},
  "entities_by_layer": {
    "S0_DOOR": 1, "S0_FLOOR": 1, "S0_LABEL": 1, "S0_OBJECT": 1,
    "S0_ROOM": 1, "S0_WALL": 2, "S0_WINDOW": 1
  },
  "insunits": 6,
  "layers": ["0", "Defpoints", "S0_DOOR", "S0_FLOOR", "S0_LABEL",
             "S0_OBJECT", "S0_ROOM", "S0_WALL", "S0_WINDOW"]
}
```

`$INSUNITS = 6` means metres. `inspect_dxf.py` exits 0 when clean, 1 when the
audit reports errors or fixes, and 2 when the file cannot be read. A clean
audit only proves that the file parses and is internally consistent; it does
not prove dimensional accuracy.

## Project directories and `meta.json`

A directory may be passed instead of a file. Nothing is guessed silently:

- **scan**, first match wins:
  `optimized_roomplan.json` → `roomplan.json` → `data/scan.json` → `scan.json`;
- **metadata**: `meta.json`, else `data/meta.json`.

If a directory holds more than one scan candidate the winner is used and the
loser is named in the `roomplan.directory-multiple-scans` warning. A directory
with no candidate is an error, never an empty drawing. Outputs default to
`<dir>/out`, so pass an explicit output directory when the input is read-only
(a mounted folder, for example).

`meta.json` (Polycam-style project metadata) is read for:

| field | used for |
|---|---|
| `name` | default title-block project name |
| `latitude`, `longitude` | **fallback only** when the scan has no `latLonAlt` |
| `headingDegrees` | **fallback only** when the scan has no `orientation` |
| `floorAreaSquareMetres`, `roomCount` | copied to `sourceMeta` in the manifest |
| `createdAt` | title-block date (`YYYY-MM-DD`) |

`createdAt` is accepted either as Unix epoch seconds or as Apple/Core Data
reference-date seconds (the observed Polycam convention); the manifest records
which convention was detected. Scan values always win over `meta.json` — the
metadata is a fallback, never an override. When values are taken from it the
manifest sets `sourceMetadata: "meta.json"`, lists them in
`metadataFallbackFields` and emits `roomplan.meta-metadata-fallback` plus, for
the heading, `roomplan.heading-from-meta`.

## Title block and north arrow

Unless `--no-frame` is passed, the DXF gains a frame, a title block in the
bottom-right and a north arrow in the top-right, on the separate layers
`FRAME`, `TITLE` and `NORTH`. Room geometry, units and transforms are not
touched. Full details: [references/title-block.md](references/title-block.md).

- Title block rows: **Projekt / Kat / Lokacija / Mjerilo / Datum + list /
  Nacrtao** (`by ARCHIFEST` by default).
- **Kat** names the floor of that sheet: `0` = Prizemlje, `1` = `1. kat`,
  `2` = `2. kat`, negative = Podrum.
- **Every cell text is fitted to its cell**: reduced height first (down to
  55 %), then truncated with `…`, always one line — a long project name never
  wraps and never reaches the neighbouring cell. Width is estimated as
  `0.6 x text height` per character, and the self-test verifies the drawn text
  of every cell against its cell rectangle (5 % tolerance).
- **The scale is text.** It defaults to `NTS`; `--scale 1:100` only labels the
  sheet. Nothing is rescaled and no paper scale is claimed — this is a
  model-space plan, not a plottable layout.
- **Location** resolution order: `--place "<text>"` (free text, always wins) →
  `--place-lookup` (one reverse geocode) → `--geo` `lat, lon` → the literal
  `location withheld`. Without one of those no coordinate appears anywhere in
  the DXF. `meta.json` carries no place name, so `--place` is the only way to
  put a human place name on the sheet without a lookup.
- **`--place-lookup` is opt-in in this public package (OFF by default)** and
  needs the **local Apple** helper `apple-location geocode` — it exists in the
  iOS/Minis environment and is simply reported as `unavailable` elsewhere, so
  the same command is safe to script on Linux. Only the Apple on-device
  geocoder is used, never a third-party service, and coordinates are sent to it
  only when you ask for the lookup. A failure is a warning
  (`roomplan.place-lookup-failed` / `-unavailable` / `-no-coordinates`), never
  an error: the cell falls back to coordinates or `location withheld`.
- **North** uses the scan's `orientation.orientation_degrees`, else
  `meta.json headingDegrees`, and is drawn with or without `--geo`
  (orientation is not a location). Bearing:
  `(alignmentOffset - heading) mod 360`, i.e. `360 - heading + offset`. The
  previous form `180 - heading + offset` was **exactly 180° wrong** on the real
  drawing this was checked against (165.3° drawn vs. 345.3° expected); the flip
  is the default, is recorded as `northArrow.flip180` plus
  `roomplan.north-flip-applied`, and `--no-north-flip` restores the legacy
  formula. It is labelled `N` whenever a bearing exists, `N?` only when there
  is none, and is marked `approx` in the manifest when it comes from metadata
  or from low-confidence compass data. Details, including why the vendor
  artefacts are ambiguous about the arrow head, are in
  [references/title-block.md](references/title-block.md#north-arrow).

### Multiple stories: one frame per floor

A plan with more than one story is drawn as **separate frames side by side**,
one per floor, each with its own bbox, frame, title block (with its `Kat` row)
and north arrow. The horizontal gap is **8 % of the widest frame width**, the
order is ascending story number, and each frame holds only its own `S<n>_*`
entities — the geometry is translated, never rescaled or re-projected.

```text
┌────────────┐  8 %  ┌────────────┐
│ Prizemlje  │       │ 1. kat     │
│   plan     │       │   plan     │
│  [title]   │       │  [title]   │
└────────────┘       └────────────┘
```

`--no-frame` deliberately keeps the old single common drawing (no frames, no
title blocks, floors overlapping) and then emits the warning
`roomplan.stories-not-separated`, so that drawing can never be mistaken for a
single-level plan. The manifest carries `stories` (story, label, entityCount,
bbox), `sheetLayout` (`mode`, `sheetCount`, `gapRatio`, `storiesSeparated`) and
one `sheetFurniture.sheets` entry per frame.

## Inputs supported

- a project directory containing one of the scan filenames listed above,
  optionally with `meta.json`/`data/meta.json`;
- raw Apple RoomPlan: a single `CapturedRoom`, a `CapturedStructure`
  (`rooms[]`), or a wrapper with `captureSessions[].roomplanSessions[]`;
- optimized exports with integer `format_version: 1`, `rooms[]` carrying
  `vertices_x`/`vertices_z` and optional label_automated, plus optional
  `alignment_transform`. “Optimized” is **not an Apple format**: it is a
  third-party post-processed export (commonly Polycam-style) that carries
  pre-computed room polygons and labels. Its field names are an observed
  contract from real files, not a published vendor schema, and different
  producers may vary.

Unversioned legacy optimized exports are also accepted when all required structures and numeric geometry validate (see formats reference); filenames/labels are not dialect evidence. Unknown explicit versions are still rejected.

Unrecognized wrappers, empty raw room lists and unsupported versions are rejected
with an error — never converted into an empty or partial drawing. See
[references/formats.md](references/formats.md) for the exact field subset,
transform convention, story clustering and projection rules.

## Output

- `<name>.dxf` — DXF R2018 (`AC1032`), modelspace, metres, layers
  `S<story>_<KIND>` (`WALL`, `FLOOR`, `DOOR`, `WINDOW`, `OPENING`, `OBJECT`,
  `ROOM`, `LABEL`) for the plan, plus `FRAME`/`TITLE`/`NORTH` for the sheet
  furniture (absent with `--no-frame`).
- `<name>.md` — Markdown summary of `report-v1` (`--md`, implies `--report`):
  project title, per-story floor / ceiling (with method) / walls gross+net /
  paint, rooms with areas and warnings, `gaps[]` from the handoff block, the
  `assumptions[]` list and a one-paragraph provenance legend. A `partial` total
  is printed as `(partial 3/4)` and an unknown one as `n/a — <reason>`; there is
  deliberately no table that would imply an accuracy we do not have.
- `<name>.usdz` — AR Quick Look model (`--usdz`): one STORE-only ZIP holding
  `room.usda`, an ASCII USD layer of the capture in metres, Y up. Independent
  of every other output — `--usdz` alone writes just the DXF, the manifest and
  the model. See [USDZ export](#usdz-export).
- `<name>.roomplan.json` — manifest: source SHA-256, dialect, input kind,
  `sourceMetadata`, story count and method, alignment, entity counts
  (`entityCount` incl. sheet furniture, `geometryEntityCount` plan only),
  layers, `titleBlock`, `northArrow`, `stories`, `sheetLayout`,
  `placeLookup`, `sheetFurniture`, `lossy: true`, warnings.

## Optional capture interchange

`node scripts/roomplan-to-dxf.js scan.json build/ --model --no-place-lookup`
adds `build/scan.capture.json`: schemaVersion, dialect/evidence, byte hash,
source axes/units/transform convention, canonical geometry/rooms/meta and a
loss inventory. Missing source labels stay null. No alignment is baked into
its source-space geometry, and generated IDs/dimensions/stories have provenance.

The default recursive whitelist omits unknown/location-like metadata; this
is not anonymization. `--model --geo` additionally includes a verbatim source
and metadata tree, potentially exposing private fields or opaque encoded data.
This is an interchange **subset**, not all of RoomPlan, a mesh decode or a
promise of app compatibility. See [model-schema](references/model-schema.md).
The optional capture path participates in overwrite/input-alias protections.
Run `python3 tests/test_adapters.py` for seven additional synthetic regression
groups covering legacy/version/label handling, malformed geometry, nested
privacy, source hashes, output paths and no pre-applied alignment.

## What the DXF contains

DXF is an open, text-based exchange format for CAD drawings. A file is a
sequence of **sections** (`HEADER`, `TABLES`, `BLOCKS`, `ENTITIES`); each record
is a pair of lines — a numeric **group code** and its value. This converter
writes:

- `HEADER` with `$ACADVER = AC1032` (R2018) and `$INSUNITS = 6` (metres);
- `TABLES` with the layer names and colours listed above;
- `ENTITIES` in modelspace only: `LINE` for wall/opening centre lines and
  `LWPOLYLINE` for footprints and room outlines, plus `TEXT` labels for rooms;
- no blocks, dimensions, hatches, external references or paperspace layouts.

The result is a plain 2D plan, not a 3D model. `scripts/inspect_dxf.py` reads
the same structure back and reports version, units, entity/layer counts and an
in-memory audit; it never rewrites the file. See
[references/dxf-primer.md](references/dxf-primer.md) for the minimal structure
and how to check a file without CAD software.

## USDZ export

`--usdz` writes `<name>.usdz`, an untextured 3D model of the capture that AR
Quick Look (iOS/iPadOS/macOS, Files, Messages, Safari) can open and place in a
room. It needs **no Apple SDK** and **no npm package**: a USDZ is a ZIP whose
entries are `*.usda` text, and both halves are written here by hand —
`scripts/lib/usdz-writer.js` (ZIP container) and `scripts/lib/usda-export.js`
(USD layer).

```sh
node scripts/roomplan-to-dxf.js scan.json build/ --usdz
# -> build/scan.dxf, build/scan.roomplan.json, build/scan.usdz
# USDZ written: build/scan.usdz (9 prims)
```

What is inside `room.usda`:

```
#usda 1.0
(
    defaultPrim = "room"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "room" ( kind = "assembly" )
    def Xform "Section_grp" ( kind = "group" )    # one assembly Xform per captured room
    def Xform "Mesh_grp" ( kind = "group" )       # one component Xform per element
        def Xform "Wall_1" ( customData {...} kind = "component" )
            def Mesh "Wall_1"      # triangulated, material:binding
            def Material "Wall_1_color"
```

- Every mesh carries `customData = { string Category = "Wall" string Identifier = "W-A" }`,
  so the 3D prims map back to the same identifiers the DXF/manifest use.
- A surface with 3D `polygonCorners` becomes that polygon (fan-triangulated);
  a WALL with `polygonCorners` is extruded into a solid **prism** (two caps plus
  one side per edge) because a flat sheet is invisible from behind under
  backface culling. Every other surface becomes an oriented box built from `dimensions`
  (x = length, y = height, z = thickness) and placed by its 4×4 transform.
  Meshes are triangulated with vertices split per face-vertex (a box is 12
  triangles over 36 vertices) and `normals` carries one normal per point — the
  same shape Apple's exporter writes, so no `interpolation` metadata is needed.
- A wall with no measured thickness gets Apple's default **0.16 m** and says so:
  `string Thickness = "assumed"` plus `double AssumedThickness = 0.16`.
- **Doors and windows are real holes.** A wall named by an opening's
  `parentIdentifier` is cut: the opening is projected onto the wall's own axes,
  a u/v grid over all opening edges marks cells solid or void, and only solid
  cells are emitted. The front and back faces keep actual holes, the opening
  edges become reveal faces, and the mesh stays closed with outward normals
  (`scripts/lib/wall-holes.js`). Overlapping openings are cut once. An opening
  that cannot be placed (no transform, outside the wall, or a wall exported from
  `polygonCorners`) is not cut and the manifest records
  `usdz.opening-not-cut`; a small overshoot under 20 mm is clamped and recorded
  as `usdz.opening-clamped`. The `Door_*` / `Window_*` prims stay in the file as
  separate components carrying `Role = "opening"`, `double Width` and
  `double Height` — but **no mesh**: a plate across an opening fills the hole
  the wall was just cut for (7 such plates in the reference capture), so the
  opening is the hole, and the warning `usdz.opening-hole-only` says so. A cut
  wall carries `int Openings`, `double CutArea` and `double ExposedArea`.
- Numbers are metres with a fixed 6 decimals and a `.` separator; a primitive
  with a non-finite transform or without usable geometry is **skipped with a
  warning** (the warning also lands in the manifest) instead of writing `NaN`.
- Geometry stays in source space: the DXF sheet rotation from `align.js` is a
  drawing-only transform and is not applied to the 3D model.

What it does **not** contain: textures, UVs, materials, cameras, lights,
semantics/panels, and no mesh from Apple's RealityKit mesh reconstruction. The
model renders as solid, untextured geometry.

Verification: the archive is opened by Python's own `zipfile` in the test suite
(`node tests/test_usdz.js`), the wall holes are measured from the emitted
triangles and audited for watertightness (`node tests/test_wall_holes.js`),
every payload is checked to start on a 64-byte
boundary, `testzip()` must return `None` (CRC-32 of every entry), and the output
is byte-identical between two runs (the ZIP timestamp is fixed at 1980-01-01).
**Apple's own `usdchecker`/AR Quick Look validation has not been run** — there
is no QuickLook or USD toolchain on the Linux/iSH side, so a real device must
open the file. See [references/usdz.md](references/usdz.md).

## Trademarks and independence

RoomPlan is an Apple framework; DXF is a format associated with Autodesk.
These names are used descriptively to state what the input and output are.
This project is independent and is **not affiliated with, endorsed by or
certified by Apple or Autodesk**. It bundles no Apple SDK, Autodesk library or
sample data, and it does not claim CAD-certified or survey-grade output.

## Known limitations of the DXF projection

- Raw scans have **no room polygons or labels**; rooms exist only in the
  optimized format.
- Raw stories are inferred by per-room floor-elevation clustering (0.8 m
  tolerance) unless the source carries distinct per-room values.
- Walls without captured thickness are drawn as centrelines; doors, windows
  and openings are always centrelines.
- Curved wall arcs are not faithfully represented; non-uniform wall polygons/beams (iOS 17+) are not
  represented because wall `polygonCorners` is ignored.
- Meshes, ceilings, furniture shape beyond a bounding footprint and semantic
  category taxonomies are not exported.
- Multi-session scans must already share one AR space; no registration is
  attempted.
- Coordinates are whatever the scan produced. Output is a plan, not a survey,
  and must not be labelled fabrication-ready without independent checks.
- The optimized source may contain `latLonAlt` and compass metadata. It is
  used for direction without --geo; geographic coordinates are only copied with --geo and marked sensitive. Keep such manifests local.
- The title block is annotation only. Its scale is text (`NTS` by default) and
  the DXF is not a paper layout; plot scale must be established independently.
- The north arrow comes from project/scan metadata. It is `approx` whenever it
  is derived from `meta.json` or from a compass reading below 0.8 confidence;
  a few degrees of error cannot be excluded and it is not a surveying bearing.

## DWG

This package writes **DXF only**. There is no reliable free, sandbox-friendly
DWG writer available locally: LibreDWG, ezdxf and similar tools either lack a
stable DWG write path or have licensing/quality caveats, and **no LibreDWG
compatibility is claimed here**. Renaming `.dxf` to `.dwg` does not convert
anything.

If a recipient requires DWG, convert the audited DXF with the proprietary
**ODA File Converter** (free download from the Open Design Alliance) on a
normal macOS/Linux/Windows desktop, outside this environment, then reopen the
result and check units and extents. DWG is optional: the DXF is the source of
truth and is sufficient for most CAD/BIM imports.

## Verification

```sh
# Full offline self-test: builds two synthetic scans in a temp dir, runs the
# converter, audits the DXF, and checks input preservation / overwrite refusal
python3 -B -m unittest discover -s tests -p 'selftest.py' -v
```

The suite ships **no fixture files** and holds **35 tests**: every input (raw,
optimized, project directory with `meta.json`, multi-story structures) is
generated in a fresh temporary directory on every run, so no real scan data and
no real address is distributed. It covers directory input, scan priority,
`meta.json` fallback, the title block (project/scale/date/location withheld,
`--geo`, `--project`/`--author`/`--scale`/`--sheet`, `--place`,
`--place-lookup` with an automatic skip when `apple-location` is absent,
`--no-frame`) and the north arrow rotation at 0° and 90°.

New in this revision, all asserted against the written DXF and manifest:

- **north flip** — heading 0° → 0°, heading 90° → 270° at zero offset, heading
  15° → 345° (the legacy formula gave 165°), heading 42.352° plus a 27.629°
  alignment offset → 345.28°, and `--no-north-flip` restoring 165.3° exactly;
- **text in cells** — every drawn cell text is measured (0.6 x height per
  character) against its own cell rectangle with a 5 % tolerance, a 90-character
  project name is proved to be a single line ending in `…`, and the `Kat` row is
  present with the right label for stories −1/0/1/2;
- **per-story sheets** — two frames, two title blocks, two north arrows, every
  `S<n>_*` entity inside its own frame, body boxes disjoint, measured gap equal
  to 8 % of the widest frame, `stories[]` summing to `geometryEntityCount`, and
  `--no-frame` warning that the stories are not separated;
- **place lookup** — `--place` wins over `--geo`, a missing helper or missing
  coordinates degrades to a warning without failing, and no coordinate ever
  leaks into the location cell.

Unknown options are rejected, and the suite asserts that no external review or
network code path is present (`--place-lookup` shells out only to the local
`apple-location` binary).

USDZ export is covered separately by `node tests/test_usdz.js` (40 checks) and
`node tests/test_wall_holes.js` (16 checks): the
ZIP is reopened by Python's `zipfile`, payloads must be 64-byte aligned,
`testzip()` must return `None`, the layer must declare `defaultPrim` /
`metersPerUnit` / `upAxis`, mesh counts and box/polygon vertex counts are
asserted, no `NaN`/`Infinity` may appear, two runs must be byte-identical, and
the CLI must write `<name>.usdz` and honour the overwrite/alias guards.

`check-drift.sh` compares the vendored converter against an optional private
reference tree; with no `ROOMPLAN_DXF_UPSTREAM` set it only prints local
checksums and never touches the network:

```sh
ROOMPLAN_DXF_UPSTREAM=/path/to/reference/scripts sh scripts/check-drift.sh
```

## License

MIT — see [LICENSE](LICENSE) (`SPDX-License-Identifier: MIT`).

The repository root `LICENSE` currently contains MIT text while the repository
`README.md` still links Apache License 2.0. This package follows the root
LICENSE text and is contributed under MIT; the maintainer may relicense or
align the repository-level notice as they see fit. All bundled code is the
contributor's own work and was relicensed for this contribution.

## Quantities and area report

Use `node scripts/roomplan-to-dxf.js scan.json out/ --report --no-place-lookup`
to additionally write `scan.report.json` and `scan.quantities.csv`; add `--md`
for `scan.md`. Combine with `--model` for the normalized capture. CSV uses UTF-8
BOM and `;` (CSV is written only with `--report`).

`scan.report.json` is `report-v1` (SPEC §3) and carries, in one document:

```
schemaVersion  "roomplan.report/1"
source         { sha256, byteCount, dialect, captureSchema: "roomplan.capture/1" }
totals         floorArea, ceilingArea, wallAreaGross, wallAreaNet, openingArea,
               wallLength, paintArea, livingArea, roomsWithoutArea,
               counts{roomCount, wallCount, doorCount, windowCount, objectCount}
elements[]     { id, kind, story, area, roomRefs[], slopeCut? }   (ids, not "keys")
rooms[]        { id, identifier, story, declaredArea, polygonArea, ceilingArea{...method}, volume }
warnings[]     { code, message, severity }   (extra fields allowed, those three are not)
assumptions[]  [ string ]                     (was conventions.caveat)
statistics     plan-statistics block (G-9) or null
handoff        handoff block with quantities[] and gaps[] (G-10) or null
```

Every numeric field is one measure:

```
{ value, status, coverage, included, expected, reason }
status   supplied | computed | reconstructed | estimated | unavailable   (provenance)
coverage complete | partial   with included/expected                     (completeness)
```

The two used to share one field (a `coverage` that said `computed` and a
`status` that said `partial`). They are now separate by contract: a `partial`
subtotal is never a building quantity, and `unavailable` is `null` with a reason,
never `0`.

Read [quantities](references/quantities.md) before relying on totals. Source room
areas, polygon-computed areas, dimension-estimated wall areas and unavailable
values are distinct. Shared wall references are not additive. Net wall areas
subtract only validated parent-linked openings; incomplete coverage yields a
**partial subtotal**, not a complete building quantity. Ceiling and volume are
unavailable. This independent engine was not ported from or compared with the
historical web reporting implementation. No survey accuracy is implied.

Run `node tests/test_quantities.js` for numerical/CSV safety tests. Reports obey
existing output overwrite and source-alias protections. Report generation is
local and does not require location lookup or an external review service.

## Data contract

[`SPEC.md`](SPEC.md) is the contract: one normalised input (`capture-v1`), one
computed result (`report-v1`), and every number carrying a provenance
(`supplied | computed | reconstructed | estimated | unavailable`, see SPEC §4).
Code that disagrees with the SPEC is wrong, not the other way round; the golden
numbers in SPEC §7 are executable, not prose.

The two machine-readable schemas live next to the code they describe:

| Document | Schema | Producer |
|---|---|---|
| `*.capture.json` (`--model`) | [`scripts/lib/schema/capture-v1.json`](scripts/lib/schema/capture-v1.json) | `scripts/lib/capture-export.js` → `buildCapture` |
| `*.report.json` (`--report`) | [`scripts/lib/schema/report-v1.json`](scripts/lib/schema/report-v1.json) | `scripts/lib/quantities.js` → `buildReport` |
| `*.md` (`--md`) | consumer of `report-v1`, not a producer | `scripts/lib/out-md.js` → `renderMarkdown` |

Both are JSON Schema **draft 2020-12**, self-contained (every `$ref` is
internal, nothing is fetched from the network) and versioned by the
`schemaVersion` pattern `roomplan.capture/1` / `roomplan.report/1`. Since P4
both schemas require the canonical names: `units`/`axes`/`stories`/`raw` and a
per-record `provenance` on the capture, `totals.*` without an `M2` suffix,
`elements[].id`/`area`/`roomRefs` and `assumptions[]` on the report. The schema
contract has **0 pending** rows (`node tests/test_schema.js`).

Check the contract locally — no dependencies, no network:

```sh
node tests/test_schema.js            # both schemas + real capture/report output
node tests/test_spec_golden.js       # SPEC §7 golden numbers, tolerance 1e-4
node tests/test_plan_statistics.js   # G-9 against the ArchiPlan fixtures
node tests/test_handoff.js           # G-10 (quantities[], gaps[], boundaries)
```

`tests/test_schema.js` validates a synthetic capture pushed through the real
pipeline (`decode-optimized` → `assignStories` → `buildCapture` / `buildReport`)
using the dependency-free validator in `tests/lib/mini-schema.js`. Set
`ROOMPLAN_SCHEMA_DUMP=/tmp/dir` to also write the exact validated documents, so
an external validator can re-check them:

```sh
ROOMPLAN_SCHEMA_DUMP=/tmp/dir node tests/test_schema.js
python3 -c "import json,jsonschema; \
  s=json.load(open('scripts/lib/schema/report-v1.json')); \
  jsonschema.Draft202012Validator(s).validate(json.load(open('/tmp/dir/synthetic.report.json')))"
```

`tests/test_spec_golden.js` prints `ID | expected | actual | PASS/PENDING/FAIL`
for G-1…G-12 plus G-8b. A golden value the current kernel cannot produce is
reported as **PENDING with the exact reason** instead of passing silently or
failing as a regression. Today **all 13 rows pass** (G-1…G-12 and G-8b) and the
14 auxiliary behaviour checks behind them pass too.

G-9 and G-10 run the ArchiPlan fixtures in `tests/fixtures/archiplan-plan-statistics.json`
and `tests/fixtures/archiplan-handoff.json` (extracted from ArchiPlan's own tests
at commit `299ed31`; each file records its provenance in `_meta`). G-8b is the
decided room-membership tolerance: **0.02 m**, with the 0.25 m value inherited
from `report-model.js` documented as **not adopted** — see the change log in
SPEC §7. Nothing in the calculations or in the CLI was changed to make a schema
or a golden number fit.

Practical rule for consumers: read `report-v1` (or `capture-v1`) and never
re-derive geometry from a vendor JSON. A `partial` subtotal is not a building
total, and an `unavailable` value is `null` — never zero.
