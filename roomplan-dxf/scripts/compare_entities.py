#!/usr/bin/env python3
"""
compare_entities.py — diff two DXF files entity-by-entity (type, layer,
rounded coordinates), ignoring layer name prefixes (RP_/OPT_ vs S<n>_) so
Swift Drawing-Bridge output can be compared directly against this repo's
Node converter output.

Usage:
    python3 docs/compare_entities.py <swift.dxf> <mine.dxf> [--decimals 2]
"""
import sys
import argparse
import ezdxf


def entity_list(path, decimals):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    out = []
    for e in msp:
        layer = e.dxf.layer
        for prefix in ("RP_", "OPT_"):
            if layer.startswith(prefix):
                layer = layer[len(prefix):]
        if e.dxftype() == "LINE":
            s, en = e.dxf.start, e.dxf.end
            out.append((
                "LINE", layer,
                round(s.x, decimals), round(s.y, decimals),
                round(en.x, decimals), round(en.y, decimals),
            ))
        elif e.dxftype() == "LWPOLYLINE":
            pts = tuple((round(p[0], decimals), round(p[1], decimals)) for p in e.get_points())
            out.append(("LWPOLYLINE", layer, pts))
        elif e.dxftype() == "TEXT":
            out.append((
                "TEXT", layer,
                round(e.dxf.insert.x, decimals), round(e.dxf.insert.y, decimals),
                e.dxf.text,
            ))
    return sorted(out, key=str)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("swift_dxf")
    ap.add_argument("mine_dxf")
    ap.add_argument("--decimals", type=int, default=2)
    args = ap.parse_args()

    swift = entity_list(args.swift_dxf, args.decimals)
    mine = entity_list(args.mine_dxf, args.decimals)

    print(f"swift entities: {len(swift)}")
    print(f"mine  entities: {len(mine)}")

    if len(swift) != len(mine):
        print("ENTITY COUNT MISMATCH — cannot pair 1:1, listing both sets is required.")
        sys.exit(1)

    mismatches = [(s, m) for s, m in zip(swift, mine) if s != m]
    print(f"mismatches: {len(mismatches)}")
    for s, m in mismatches[:20]:
        print(" swift:", s)
        print(" mine: ", m)

    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
