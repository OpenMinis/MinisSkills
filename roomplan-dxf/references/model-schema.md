# Normalized capture interchange — `roomplan.capture/1`

`node scripts/roomplan-to-dxf.js input.json out/ --model --no-place-lookup`
adds `<name>.capture.json` beside the DXF and diagnostics manifest. Without
`--model` no capture file is written. Output collisions, including an existing
capture file, exit 2 unless `--force`; aliases of the input or meta file are
rejected even with `--force`. Input bytes are never rewritten.

## Meaning and limits

This is a documented **subset interchange**, not a complete Apple RoomPlan
archive, a vendor-neutral BIM model or proof that any other app can import it.
The parser understands fields listed here; that is not full understanding of
RoomPlan. `coreModel`/meshes are opaque and never decoded. DXF is a separate,
lossy 2D projection. Unknown attributes can be omitted; see `completeness`.

The programmatic API is `require('./scripts/lib/model').buildCapture(model,
sourceJSON, options)` after decoding, assigning stories and setting
`architecturalAlignment`. It returns JSON-safe data and does not mutate the
source-space model. This normalized document is an output contract, **not**
an additional input dialect accepted by the DXF CLI.

## Top-level fields

| Field | Contract |
|---|---|
| `schemaVersion` | literal `roomplan.capture/1` |
| `dialect` | `name`, `kind`, positive content `evidence`; explicit v1 and legacy-unversioned are distinct |
| `source` | SHA256 of original **bytes**, byte count; optional metadata byte hash/count; original bytes stay external and unchanged |
| `conventions` | metres, square metres, source axes, matrix order, transform composition, DXF projection, numerical limits |
| `coordinateState` | source-space, not aligned; no sheet translations applied |
| `alignment` | numeric 16-value matrix, method, `applied:false` |
| `surfaces`, `objects` | canonical element records; identifiers, parent, category, confidence, dimensions, transform, story, polygon/curve where decoded |
| `rooms` | optimized polygons/centres/category/label provenance; raw room records have nullable identity/story and no invented measured polygon or name |
| `meta` | story-assignment method, source direction/uncertainty/confidence with caveat, metadata fallback field names |
| `sourceRecords` | recursively whitelisted known source room/element/section/attribute/joint fields, still in source space; complements canonical records without opaque metadata copying |
| `completeness` | `lossless:false`, `meshDecoded:false`, opaque coreModel presence/status, loss inventory and count scope |
| `privacy` | redaction policy and whether a verbatim source tree was requested |

### Transform convention — apply only once

Source axes are right-handed, `+Y` up, ground plane `XZ`. Matrices are
column-major with translation in indices 12–14, acting on column vectors.
`polygonCorners` are element-local. For an aligned point use
`alignment.matrix * element.transform * localPoint`. Optimized room vertices
and centres are source-space XZ, so use **only alignment** for them. DXF then
projects `(x,z)` to `(x,-z)` and can translate stories onto separate sheets.
None of these DXF presentation translations is baked into capture records.

Source-provided alignment may include translation (it is not necessarily a
pure rotation). No new inter-session registration is attempted. Affine and
nonsingular validation is not proof of rigid registration or surveyed units.

### Identity, confidence and missing data

Optimized `label_automated` is optional: absent labels remain `null`, with
`labelProvenance`; source category and ID are retained. DXF then prints an
explicit `[category; id=...]` classification, not an invented measured name.
Nullable `floor_height` stays null. Source room edges, curved edges, ceilings
and associations may remain in canonical/source records, but are not thereby
rendered faithfully in DXF. Known source attributes such as `StorageType`
are preserved; unknown attribute keys are omitted by default.

Raw surfaces/objects retain `sourceRoomIndex`/`sourceRoomIdentifier` and
`sourceRecordIndex`. `sourceStory`/provenance distinguish source values from
DXF story assignment. An optimized missing story still defaults to 0 for DXF,
but the default is explicitly not measured. Floors retain a supplied
identifier; an absent ID is generated from story and record path and labelled
as generated. Optimized floor dimensions `(1,0,0)` are marked DXF placeholders:
use the original source dimensions/sourceRecords or polygonCorners instead.

Direction is source-provided, not verified true north. A metadata fallback
has no invented confidence. A compass can be wrong despite successful parsing.

## Privacy and loss accounting

Without `--geo`, a whitelist is applied recursively to canonical/source
records: geo/location/address-like fields and nested unknown fields are not
copied. Source paths, basenames and project metadata are not embedded. Unknown
field names/values are not echoed into the loss inventory; counts and known
limitations state the loss. The projection omission count is **not** a count
of every original field; its scope is stored alongside it. Unprojected raw
wrapper metadata is explicitly noted. IDs, geometry and source labels can
still identify a property: metadata redaction is **not anonymization**.

`--model --geo` explicitly opts into location metadata **and a verbatim
`sourceTree`**, plus `sourceMetaTree` when present. This preserves unknown
source fields, original story/confidence/section representations and opaque
coreModel strings, but may expose private locations/names/encoded data. It is
not byte-for-byte embedding: SHA256 always refers to the separate original
bytes. Keep these files private. `--geo` does not trigger a network lookup;
use `--no-place-lookup` explicitly for offline local runs.

## Validation scope

Finite coordinates ±1e6 m; dimensions 0..1e5 m; integral stories ±10000;
nonnegative room area up to 1e10 m²; matched room coordinate arrays with at
least three non-collinear vertices; finite affine nonsingular 4×4 matrices
(including recognized ceiling/section transforms). Latitude/longitude limits
are ±90/±180; direction accepts signed degrees −360..360. Wrong types,
lengths and ambiguous tagged categories fail. This is not a comprehensive
polygon topology, manifold, registration or physical plausibility validator.
