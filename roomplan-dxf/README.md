# roomplan-dxf

Convert Apple RoomPlan JSON scans (raw `CapturedRoom`/`CapturedStructure`, or
an optimized `format_version: 1` export) into a 2D DXF floor plan in metres,
with a manifest that states every loss and assumption. Includes an offline DXF
audit helper and a self-test. No network access, no upload, no capture.

```
scan.json ──► roomplan-to-dxf.js ──► scan.dxf + scan.roomplan.json
                                          │
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

# Audit the result
python3 -B scripts/inspect_dxf.py build/scan.dxf
```

`--geo` never georeferences the drawing. It only copies `latLonAlt` and compass
values present in an optimized source into `sourceGeo`, adds a warning, and
should be used only when the recipient needs the provenance point. Coordinates
are sensitive: keep them local and redact them from shared reports. Without
`--geo`, no coordinates are written anywhere.

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

## Inputs supported

- raw Apple RoomPlan: a single `CapturedRoom`, a `CapturedStructure`
  (`rooms[]`), or a wrapper with `captureSessions[].roomplanSessions[]`;
- optimized exports with integer `format_version: 1`, `rooms[]` carrying
  `label_automated`/`vertices_x`/`vertices_z`, and optional
  `alignment_transform`. “Optimized” is **not an Apple format**: it is a
  third-party post-processed export (commonly Polycam-style) that carries
  pre-computed room polygons and labels. Its field names are an observed
  contract from real files, not a published vendor schema, and different
  producers may vary.

Unrecognized wrappers, empty room lists and unsupported versions are rejected
with an error — never converted into an empty or partial drawing. See
[references/formats.md](references/formats.md) for the exact field subset,
transform convention, story clustering and projection rules.

## Output

- `<name>.dxf` — DXF R2018 (`AC1032`), modelspace, metres, layers
  `S<story>_<KIND>` (`WALL`, `FLOOR`, `DOOR`, `WINDOW`, `OPENING`, `OBJECT`,
  `ROOM`, `LABEL`).
- `<name>.roomplan.json` — manifest: source SHA-256, dialect, story count and
  method, alignment, entity count, layers, `lossy: true`, warnings.

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

## Trademarks and independence

RoomPlan is an Apple framework; DXF is a format associated with Autodesk.
These names are used descriptively to state what the input and output are.
This project is independent and is **not affiliated with, endorsed by or
certified by Apple or Autodesk**. It bundles no Apple SDK, Autodesk library or
sample data, and it does not claim CAD-certified or survey-grade output.

## Known limitations

- Raw scans have **no room polygons or labels**; rooms exist only in the
  optimized format.
- Raw stories are inferred by per-room floor-elevation clustering (0.8 m
  tolerance) unless the source carries distinct per-room values.
- Walls without captured thickness are drawn as centrelines; doors, windows
  and openings are always centrelines.
- Curved walls are skipped; non-uniform wall polygons/beams (iOS 17+) are not
  represented because wall `polygonCorners` is ignored.
- Meshes, ceilings, furniture shape beyond a bounding footprint and semantic
  category taxonomies are not exported.
- Multi-session scans must already share one AR space; no registration is
  attempted.
- Coordinates are whatever the scan produced. Output is a plan, not a survey,
  and must not be labelled fabrication-ready without independent checks.
- The optimized source may contain `latLonAlt` and compass metadata. It is
  ignored unless `--geo` is passed; then it is copied to `sourceGeo` and marked
  sensitive. Keep such manifests local.

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

The suite ships **no fixture files**: both inputs are generated in a fresh
temporary directory on every run, so no real scan data is distributed. Unknown
options are rejected, and the suite asserts that no external review or network
code path is present.

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
