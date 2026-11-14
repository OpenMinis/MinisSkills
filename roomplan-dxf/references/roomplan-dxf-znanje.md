# General conversion and verification guidance

Historical private operating notes are excluded from this public package.
Use [DXF output](dxf-output.md), [formats](formats.md), and the
[README](../README.md) for current supported behavior.

Run `python3 -B scripts/inspect_dxf.py out/scan.dxf` after conversion;
check units (metres), bounds, layers, source SHA256 and warnings against
the input. Counts alone do not prove geometric equality. Preserve the
original scan read-only, compare numeric geometry when available, and
never treat a clean DXF audit as survey or physical verification.
