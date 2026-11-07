#!/usr/bin/env python3
"""
dxf-emit.py — reads an entity PLAN (JSON, produced by lib/dxf-writer.js) on
stdin and writes a real, AutoCAD-openable DXF file using ezdxf.

Usage: python3 dxf-emit.py <output.dxf> < plan.json
"""
import sys
import json


def main():
    if len(sys.argv) < 2:
        print("Usage: dxf-emit.py <output.dxf> < plan.json", file=sys.stderr)
        sys.exit(1)
    out_path = sys.argv[1]
    plan = json.load(sys.stdin)

    import ezdxf

    doc = ezdxf.new("R2018", setup=True)  # AC1032 — broad CAD compatibility
    doc.header["$INSUNITS"] = 6  # meters
    doc.header["$LWDISPLAY"] = 1  # show lineweights so walls read heavier than labels
    msp = doc.modelspace()

    LAYER_COLORS = {
        "WALL": 7,     # black/white — primary structure, full contrast
        "FLOOR": 8,    # dark gray — visible but recessive vs. walls
        "DOOR": 3,     # green — standard architectural convention
        "WINDOW": 5,   # blue — standard architectural convention
        "OBJECT": 9,   # light gray — furniture labels, de-emphasized
        "ROOM": 2,     # yellow — room outlines/labels
    }
    LAYER_LINEWEIGHT = {
        "WALL": 35,    # ~0.35mm — walls read as the thickest lines
        "FLOOR": 13,
        "DOOR": 18,
        "WINDOW": 18,
        "OBJECT": 9,
        "ROOM": 13,
    }

    def color_for(layer_name):
        kind = layer_name.split("_", 1)[-1] if "_" in layer_name else layer_name
        return LAYER_COLORS.get(kind, 7)

    def lineweight_for(layer_name):
        kind = layer_name.split("_", 1)[-1] if "_" in layer_name else layer_name
        return LAYER_LINEWEIGHT.get(kind, 13)

    for name in plan.get("layers", []):
        if name not in doc.layers:
            doc.layers.add(name=name, color=color_for(name))
            doc.layers.get(name).dxf.lineweight = lineweight_for(name)

    for e in plan.get("entities", []):
        t = e["type"]
        layer = e.get("layer", "0")
        if t == "polyline":
            pts = [(p[0], p[1]) for p in e["points"]]
            msp.add_lwpolyline(pts, close=bool(e.get("closed")), dxfattribs={"layer": layer})
        elif t == "line":
            msp.add_line((e["a"][0], e["a"][1]), (e["b"][0], e["b"][1]), dxfattribs={"layer": layer})
        elif t == "text":
            txt = msp.add_text(e["value"], dxfattribs={"layer": layer, "height": e.get("height", 0.1)})
            txt.set_placement((e["pos"][0], e["pos"][1]))
        else:
            raise ValueError(f"Unknown entity type in plan: {t}")

    b = plan.get("bounds")
    if b:
        # Note: ezdxf recomputes/ignores a manually-set $EXTMIN/$EXTMAX on
        # save (AutoCAD itself recalculates extents on open/zoom-extents
        # anyway), so we don't bother forcing it here.
        pass

    doc.saveas(out_path)

    # Round-trip validation: fail loudly if what we just wrote can't be
    # re-read by a real DXF parser (catches structural mistakes immediately
    # instead of shipping a file that silently fails to open elsewhere).
    ezdxf.readfile(out_path)
    print(f"DXF written and validated: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
