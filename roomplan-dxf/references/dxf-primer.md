# Minimal DXF primer

DXF (Drawing Exchange Format) is a text-based CAD exchange format. This note
covers only what this skill writes and checks; it is not a complete standard.

## Records, group codes, sections

A DXF file is a sequence of records. Each record is two lines:

```
0
SECTION
2
HEADER
```

The first line is a numeric **group code**; the second is its value. Code `0`
starts a new object (`SECTION`, `ENDSEC`, `LINE`, `LWPOLYLINE`, `TEXT`, `EOF`).
Codes such as `8` (layer), `10`/`20` (start point X/Y), `11`/`21` (end point)
carry object data.

A minimal drawing has:

- `HEADER` — document settings such as `$ACADVER` and `$INSUNITS`;
- `TABLES` — layers, linetypes, text styles;
- `BLOCKS` — reusable block definitions (this skill writes none);
- `ENTITIES` — modelspace geometry;
- `EOF`.

## What this skill emits

| Item | Value |
|---|---|
| Version | `AC1032` (R2018) |
| Units | `$INSUNITS = 6` (metres) |
| Geometry | `LINE` (centre lines), `LWPOLYLINE` (footprints, room outlines) |
| Labels | `TEXT` with room name and area |
| Layers | `S<story>_<KIND>` |
| Not written | blocks, dimensions, hatches, xrefs, paperspace layouts, 3D |

Coordinates are planar millimetre-equivalent values in metres in the source
frame. A DXF viewer that ignores `$INSUNITS` may display the drawing at a
different scale.

## Check without CAD software

```sh
python3 -B scripts/inspect_dxf.py drawing.dxf
```

The helper prints JSON with `dxf_version`, raw `insunits`, layer names,
top-level modelspace entity counts and audit error/fix counts. Exit `0` means a
clean audit, `1` means findings, `2` means the file could not be read. The audit
runs in memory and never saves repairs.

`python3 -B scripts/make_fixture.py /tmp/test.dxf` writes a synthetic 100×50 mm
rectangle for comparison; it refuses to overwrite an existing file.

## Limits

A clean audit proves internal file structure, not geometric accuracy, intended
units, layer semantics or compatibility with a specific CAD application. Counts
and bounds do not prove two drawings are identical or manufacturing-safe.
Open the file in the target application before relying on it.
