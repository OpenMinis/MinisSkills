"""Summarise a DXF produced by roomplan-to-dxf (or any DXF) on stdout.

Reports the DXF version, $INSUNITS, entity counts by type and layer, and an
in-memory audit. The file is opened read-only; nothing is saved and no
external references are resolved. Exit codes: 0 clean, 1 audit errors or
fixes, 2 unreadable input.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import ezdxf


def inspect(path):
    doc = ezdxf.readfile(path)
    # Counts describe the parsed source before audit's possible in-memory repairs.
    msp = list(doc.modelspace())
    result = {
        "dxf_version": doc.dxfversion,
        "insunits": int(doc.header.get("$INSUNITS", 0)),
        "scope": "top-level modelspace before audit; no block expansion",
        "entities": dict(sorted(Counter(e.dxftype() for e in msp).items())),
        "entities_by_layer": dict(sorted(Counter(e.dxf.layer for e in msp).items())),
        "layers": sorted(layer.dxf.name for layer in doc.layers),
    }
    auditor = doc.audit()
    result["audit"] = {"errors": len(auditor.errors), "fixes": len(auditor.fixes)}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        result = inspect(args.input)
    except Exception as exc:
        # Keep paths, drawing text and exception details out of diagnostic JSON.
        print(json.dumps({"error": type(exc).__name__}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return int(any(result["audit"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
