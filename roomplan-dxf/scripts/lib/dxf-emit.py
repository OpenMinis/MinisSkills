#!/usr/bin/env python3
"""
dxf-emit.py — reads an entity PLAN (JSON, produced by lib/dxf-writer.js) on
stdin and writes a real, AutoCAD-openable DXF file using ezdxf.

Usage: python3 dxf-emit.py <output.dxf> < plan.json

Every entity is copied verbatim from the plan; nothing is re-projected or
re-transformed here. When `plan.meta` and `plan.frame` are present, a sheet
frame, a title block and a north arrow are added AROUND the plan bounding box
on their own layers (FRAME / TITLE / NORTH). Those are annotations only: room
geometry, layers, units and transforms of the scan are never touched.

A one-line JSON summary is printed to stdout so the caller can report the
final entity count without re-opening the file.
"""
import json
import math
import sys

# Nominal proportions of the drawing sheet furniture, expressed as fractions
# of the plan bounding box (largest side / height). Kept in one place so the
# documentation and the drawing cannot drift apart.
FRAME_MARGIN_RATIO = 0.05       # margin around the plan bbox
TITLE_WIDTH_RATIO = 0.40        # title block width vs. frame width
TITLE_HEIGHT_RATIO = 0.08       # nominal title block height vs. frame height
TEXT_HEIGHT_RATIO = 0.016       # text height vs. bbox largest side (1.6 %)
ROW_HEIGHT_RATIO = 1.6          # row height = 1.6 x text height (readability)
NORTH_RADIUS_RATIO = 0.05       # north circle radius vs. bbox largest side
TEXT_LAYER = "TITLE"
FRAME_LAYER = "FRAME"
NORTH_LAYER = "NORTH"


def fmt_number(value):
    """Compact, locale-independent number for drawing text."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def add_text(msp, value, x, y, height, layer):
    txt = msp.add_text(value, dxfattribs={"layer": layer, "height": height})
    txt.set_placement((x, y))
    return txt


def plan_strips(bounds, text_height):
    """Geometry of the sheet: a frame around the plan plus two reserved strips
    (title block below, north symbol above) so sheet furniture never covers
    the measured plan."""
    x0, y0, x1, y1 = bounds
    span = max(x1 - x0, y1 - y0)
    margin = FRAME_MARGIN_RATIO * span
    radius = NORTH_RADIUS_RATIO * span

    # Title block height: nominal TITLE_HEIGHT_RATIO of the plan, grown when
    # five legible rows need more room than that.
    row_h = max(TITLE_HEIGHT_RATIO * (y1 - y0) / 5.0, ROW_HEIGHT_RATIO * text_height)
    title_h = row_h * 5.0
    top_strip = 2.9 * radius
    frame = (x0 - margin, y0 - margin - title_h, x1 + margin, y1 + margin + top_strip)
    return frame, title_h, radius


def draw_frame(msp, frame):
    """Rectangular sheet frame around the plan + sheet furniture strips."""
    fx0, fy0, fx1, fy1 = frame
    msp.add_lwpolyline(
        [(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)],
        close=True,
        dxfattribs={"layer": FRAME_LAYER},
    )
    return frame


def draw_title_block(msp, frame, meta, text_height, title_h):
    """Title block in the bottom-right corner, inside its reserved strip.

    Rows: projekt / lokacija / mjerilo / datum + list / nacrtao. The scale cell
    is free text and defaults to "NTS" — a title block is not a paper layout,
    so no plot scale is ever implied by the drawing itself.
    """
    fx0, fy0, fx1, fy1 = frame
    width = fx1 - fx0
    height = fy1 - fy0

    rows = [
        ("Projekt", meta.get("project") or "-"),
        ("Lokacija", meta.get("locationText") or "location withheld"),
        ("Mjerilo", meta.get("scaleText") or "NTS"),
        ("Datum / list", "%s / %s" % (meta.get("date") or "-", meta.get("sheet") or "-")),
        ("Nacrtao", meta.get("drawnBy") or "by ARCHIFEST"),
    ]

    title_w = TITLE_WIDTH_RATIO * width
    row_h = title_h / len(rows)

    tx0 = fx1 - title_w
    ty0 = fy0
    tx1 = fx1
    ty1 = fy0 + title_h

    msp.add_lwpolyline(
        [(tx0, ty0), (tx1, ty0), (tx1, ty1), (tx0, ty1)],
        close=True,
        dxfattribs={"layer": FRAME_LAYER},
    )
    # Column divider: label cell on the left, value cell on the right.
    divider_x = tx0 + 0.34 * title_w
    msp.add_line((divider_x, ty0), (divider_x, ty1), dxfattribs={"layer": FRAME_LAYER})

    pad = 0.30 * text_height
    for index, (label, value) in enumerate(rows):
        row_bottom = ty0 + index * row_h
        if index > 0:
            msp.add_line((tx0, row_bottom), (tx1, row_bottom), dxfattribs={"layer": FRAME_LAYER})
        baseline = row_bottom + (row_h - text_height) / 2.0
        add_text(msp, label, tx0 + pad, baseline, text_height, TEXT_LAYER)
        add_text(msp, str(value), divider_x + pad, baseline, text_height, TEXT_LAYER)

    return {"x0": tx0, "y0": ty0, "x1": tx1, "y1": ty1, "rows": len(rows),
            "widthRatioOfFrame": TITLE_WIDTH_RATIO,
            "heightRatioOfFrame": round(title_h / height, 4)}


def draw_north_arrow(msp, frame, north, text_height, north_radius):
    """Circle + arrow + 'N' in the top-right of the frame.

    The bearing is `degreesClockwiseFromDrawingUp`; 0 points up (+Y), 90
    points right (+X). An unknown bearing is drawn pointing up and labelled
    "N?" — the label never claims a straight-up north that was not measured.
    """
    fx0, fy0, fx1, fy1 = frame
    radius = north_radius
    cx = fx1 - 2.2 * radius
    cy = fy1 - 2.2 * radius

    degrees = north.get("degreesClockwiseFromDrawingUp")
    known = degrees is not None
    theta = math.radians(degrees if known else 0.0)
    ux, uy = math.sin(theta), math.cos(theta)
    px, py = -uy, ux

    msp.add_circle((cx, cy), radius, dxfattribs={"layer": NORTH_LAYER})

    shaft_start = (cx + 0.20 * radius * ux, cy + 0.20 * radius * uy)
    tip = (cx + 1.00 * radius * ux, cy + 1.00 * radius * uy)
    msp.add_line(shaft_start, tip, dxfattribs={"layer": NORTH_LAYER})

    head_len = 0.42 * radius
    head_half = 0.24 * radius
    head_base = (tip[0] - head_len * ux, tip[1] - head_len * uy)
    msp.add_lwpolyline(
        [
            (head_base[0] + head_half * px, head_base[1] + head_half * py),
            tip,
            (head_base[0] - head_half * px, head_base[1] - head_half * py),
        ],
        close=True,
        dxfattribs={"layer": NORTH_LAYER},
    )

    label = "N" if known else "N?"
    la = 1.42 * radius
    label_h = max(text_height, 0.9 * radius)
    add_text(msp, label,
             cx + la * ux - 0.35 * label_h,
             cy + la * uy - 0.5 * label_h,
             label_h, TEXT_LAYER)

    return {"centre": [round(cx, 4), round(cy, 4)], "radius": round(radius, 4),
            "label": label, "degreesClockwiseFromDrawingUp": degrees,
            "tip": [round(tip[0], 4), round(tip[1], 4)]}


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
        "FRAME": 8,    # sheet furniture: recessive gray
        "TITLE": 7,    # title block text — same contrast as walls
        "NORTH": 7,    # north arrow
    }
    LAYER_LINEWEIGHT = {
        "WALL": 35,    # ~0.35mm — walls read as the thickest lines
        "FLOOR": 13,
        "DOOR": 18,
        "WINDOW": 18,
        "OBJECT": 9,
        "ROOM": 13,
        "FRAME": 18,
        "TITLE": 13,
        "NORTH": 18,
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

    geometry_count = 0
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
        elif t == "circle":
            msp.add_circle((e["centre"][0], e["centre"][1]), e.get("radius", 0.1),
                           dxfattribs={"layer": layer})
        else:
            raise ValueError(f"Unknown entity type in plan: {t}")
        geometry_count += 1

    summary = {"geometryEntityCount": geometry_count, "titleBlock": None,
               "northArrow": None, "frame": None}

    meta = plan.get("meta")
    if plan.get("frame") and meta:
        b = plan.get("bounds")
        if b:
            bbox = (b["minX"], b["minZ"], b["maxX"], b["maxZ"])  # plan Y is stored as Z
        else:
            bbox = (0.0, 0.0, 1.0, 1.0)
        span = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
        if not span > 0:
            span = 1.0
        text_height = TEXT_HEIGHT_RATIO * span
        frame, title_h, radius = plan_strips(bbox, text_height)
        draw_frame(msp, frame)
        summary["frame"] = [round(v, 4) for v in frame]
        summary["titleBlock"] = draw_title_block(msp, frame, meta, text_height, title_h)
        north = meta.get("north") or {}
        summary["northArrow"] = draw_north_arrow(msp, frame, north, text_height, radius)
        note = meta.get("sourceNote")
        if note:
            add_text(msp, note, frame[0] + 0.5 * text_height,
                     frame[1] + 0.45 * text_height, 0.62 * text_height, TEXT_LAYER)

    doc.saveas(out_path)

    # Round-trip validation: fail loudly if what we just wrote can't be
    # re-read by a real DXF parser (catches structural mistakes immediately
    # instead of shipping a file that silently fails to open elsewhere).
    ezdxf.readfile(out_path)
    summary["entityCount"] = len(msp)
    print(json.dumps(summary))
    print(f"DXF written and validated: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
