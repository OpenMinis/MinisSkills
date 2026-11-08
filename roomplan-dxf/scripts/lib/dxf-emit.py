#!/usr/bin/env python3
"""
dxf-emit.py — reads an entity PLAN (JSON, produced by lib/dxf-writer.js) on
stdin and writes a real, AutoCAD-openable DXF file using ezdxf.

Usage: python3 dxf-emit.py <output.dxf> < plan.json

Every entity is copied verbatim from the plan (translated only when the plan
has more than one story); nothing is re-projected or re-transformed here.

Sheet furniture (only when `plan.meta` and `plan.frame` are present):

  * ONE story  -> a single frame with a title block and a north arrow around
    the plan bounding box, exactly as before.
  * MORE than one story -> one frame PER STORY, laid out side by side with a
    horizontal gap of FRAME_GAP_RATIO (8 %) of the widest frame width. Each
    frame carries only that story's entities (layers S<n>_*), its own title
    block (with the "Kat" row naming the floor) and its own north arrow.

Title-block text is fitted to its cell: the text height is reduced first, and
only when that is not enough is the value shortened with an ellipsis ("…").
Width is estimated as CHAR_WIDTH_RATIO * height per character. Every drawn
cell is reported in the JSON summary so a test can verify the bbox of each
TEXT against the cell it belongs to.

A one-line JSON summary is printed to stdout so the caller can report the
final entity count, the placement of each sheet and the fitted text cells.
"""
import json
import math
import sys

# Nominal proportions of the drawing sheet furniture, expressed as fractions
# of the plan bounding box (largest side / height). Kept in one place so the
# documentation and the drawing cannot drift apart.
FRAME_MARGIN_RATIO = 0.05       # margin around the plan bbox
TITLE_WIDTH_RATIO = 0.55        # title block width vs. frame width
TEXT_HEIGHT_RATIO = 0.016       # text height vs. bbox largest side (1.6 %)
ROW_HEIGHT_RATIO = 1.6          # row height = 1.6 x text height (readability)
NORTH_RADIUS_RATIO = 0.05       # north circle radius vs. bbox largest side
FRAME_GAP_RATIO = 0.08          # gap between per-story frames (8 % of frame width)
CHAR_WIDTH_RATIO = 0.95          # conservative glyph width estimate per character, x text height
MIN_TEXT_HEIGHT_RATIO = 0.55    # never shrink a cell text below 55 % of nominal
TEXT_PAD_RATIO = 0.35           # cell padding, x text height
LABEL_COLUMN_RATIO = 0.34       # label column width vs. title block width
TITLE_ROWS = 6                  # Projekt / Kat / Lokacija / Mjerilo / Datum / Nacrtao
TEXT_LAYER = "TITLE"
FRAME_LAYER = "FRAME"
NORTH_LAYER = "NORTH"
ELLIPSIS = "\u2026"

# ---------------------------------------------------------------------------
# Draw order (paint order)
#
# DXF has no per-entity z-order in model space: a viewer that renders entities
# in file order paints the later ones on top. An opening (door/window/opening)
# is a single thin centre line lying ON the wall footprint it belongs to, so if
# the wall is written after it, a viewer that shades or thickens walls covers
# the opening and the plan reads as a windowless box. Openings are therefore
# written AFTER walls — the same table as DRAW_ORDER in lib/dxf-writer.js,
# applied here as a safety net so that a plan produced by an older writer (or
# hand-built JSON) still comes out with the openings on top. Lower = first.
DRAW_ORDER = {
    "FLOOR": 10,
    "WALL": 20,
    "ROOM": 30,
    "OBJECT": 40,
    "DOOR": 50,     # openings: above floor, walls, rooms, furniture
    "WINDOW": 50,
    "OPENING": 50,
    "LABEL": 60,    # labels stay readable, never covered by geometry
    "CEILING": 70,
    "CEILING_FLAT": 70,
    "CEILING_SEAM": 70,
}
DRAW_ORDER_DEFAULT = 65
OPENING_KINDS = ("DOOR", "WINDOW", "OPENING")


def kind_of_layer(layer_name):
    """`S<n>_<KIND>` -> `<KIND>`; anything else is returned unchanged."""
    name = "" if layer_name is None else str(layer_name)
    return name.split("_", 1)[-1] if "_" in name else name


def draw_order_of(entity):
    """Paint priority of one plan entity (lower is painted first)."""
    kind = kind_of_layer(entity.get("layer", "0"))
    if kind in DRAW_ORDER:
        return DRAW_ORDER[kind]
    return 60 if entity.get("type") == "text" else DRAW_ORDER_DEFAULT


def sort_by_draw_order(entities):
    """Stable sort by paint priority: openings above walls, labels above both."""
    decorated = [(draw_order_of(e), index, e) for index, e in enumerate(entities)]
    decorated.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in decorated]


def fmt_number(value):
    """Compact, locale-independent number for drawing text."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def add_text(msp, value, x, y, height, layer):
    txt = msp.add_text(value, dxfattribs={"layer": layer, "height": height})
    txt.set_placement((x, y))
    return txt


def text_width(value, height):
    """Estimated drawn width of a single-line TEXT (no font metrics in DXF)."""
    return len(value) * CHAR_WIDTH_RATIO * height


def fit_text(value, cell_width, height):
    """Fit `value` into a cell of `cell_width` at nominal `height`.

    Order of preference (never wrap — a title block cell holds one line):
      1. nominal height, full text;
      2. reduced height (down to MIN_TEXT_HEIGHT_RATIO * height), full text;
      3. truncated to the characters that fit at the reduced height, with a
         trailing ellipsis.
    Returns (text, height, truncated). The returned text always satisfies
    text_width(text, height) <= cell_width - 2 * (TEXT_PAD_RATIO * height),
    so no cell text can cross into its neighbour.
    """
    charset = str(value)
    min_height = height * MIN_TEXT_HEIGHT_RATIO
    current = height
    for _ in range(4):
        available = cell_width - 2 * TEXT_PAD_RATIO * current
        if available <= 0:
            break
        if text_width(charset, current) <= available:
            return charset, current, False
        shrunk = available / (len(charset) * CHAR_WIDTH_RATIO)
        if shrunk >= min_height:
            current = shrunk
            continue
        current = min_height
        available = cell_width - 2 * TEXT_PAD_RATIO * current
        max_chars = int(available // (CHAR_WIDTH_RATIO * current))
        if max_chars >= 2:
            trimmed = charset[: max_chars - 1].rstrip() + ELLIPSIS
        elif max_chars == 1:
            trimmed = ELLIPSIS
        else:
            trimmed = ""
        return trimmed, current, True
    return "", current, True


def plan_strips(bounds, text_height, row_count):
    """Geometry of one sheet: a frame around the plan plus two reserved strips
    (title block below, north symbol above) so sheet furniture never covers
    the measured plan."""
    x0, y0, x1, y1 = bounds
    span = max(x1 - x0, y1 - y0)
    margin = FRAME_MARGIN_RATIO * span
    radius = NORTH_RADIUS_RATIO * span

    # Title block height is content driven: one row per line, sized so the
    # text always has room (six rows since the "Kat" row was added).
    row_h = ROW_HEIGHT_RATIO * text_height
    title_h = row_h * row_count
    top_strip = 2.9 * radius
    frame = (x0 - margin, y0 - margin - title_h, x1 + margin, y1 + margin + top_strip)
    return frame, title_h, radius, row_h


def draw_frame(msp, frame):
    """Rectangular sheet frame around the plan + sheet furniture strips."""
    fx0, fy0, fx1, fy1 = frame
    msp.add_lwpolyline(
        [(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)],
        close=True,
        dxfattribs={"layer": FRAME_LAYER},
    )
    return frame


def draw_title_block(msp, frame, meta, text_height, title_h, story_label=None):
    """Title block in the bottom-right corner, inside its reserved strip.

    Rows: projekt / kat / lokacija / mjerilo / datum + list / nacrtao. Every
    value is fitted to its cell (shrunk, then ellipsised) and kept on one
    line, so a long project name can never spill into the neighbouring cell.
    The scale cell is free text and defaults to "NTS" — a title block is not a
    paper layout, so no plot scale is ever implied by the drawing itself.
    """
    fx0, fy0, fx1, fy1 = frame
    width = fx1 - fx0
    height = fy1 - fy0

    rows = [
        ("Projekt", meta.get("project") or "-"),
        ("Kat", story_label or meta.get("storyLabel") or "-"),
        ("Lokacija", meta.get("locationText") or "location withheld"),
        ("Mjerilo", meta.get("scaleText") or "NTS"),
        ("Datum / list", "%s / %s" % (meta.get("date") or "-", meta.get("sheet") or "-")),
        ("Nacrtao", meta.get("drawnBy") or "by ARCHIFEST"),
    ]

    row_h = title_h / len(rows)
    nominal_h = min(text_height, row_h * 0.55)
    pad = 2 * TEXT_PAD_RATIO * nominal_h
    label_need = max(text_width(lbl, nominal_h) for lbl, _ in rows) + pad
    value_need = max(text_width(str(val), nominal_h) for _, val in rows) + pad
    title_w = min(max(0.35 * width, label_need + value_need), 0.70 * width)

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
    divider_x = tx0 + min(max(label_need, 0.30 * title_w), 0.52 * title_w)
    msp.add_line((divider_x, ty0), (divider_x, ty1), dxfattribs={"layer": FRAME_LAYER})

    cells = []
    for index, (label, value) in enumerate(rows):
        row_bottom = ty0 + index * row_h
        if index > 0:
            msp.add_line((tx0, row_bottom), (tx1, row_bottom), dxfattribs={"layer": FRAME_LAYER})

        label_text, label_height, label_cut = fit_text(label, divider_x - tx0, nominal_h)
        value_text, value_height, value_cut = fit_text(str(value), tx1 - divider_x, nominal_h)
        for cell_x0, cell_x1, drawn, drawn_h, is_label in (
            (tx0, divider_x, label_text, label_height, True),
            (divider_x, tx1, value_text, value_height, False),
        ):
            if not drawn:
                continue
            pad = TEXT_PAD_RATIO * drawn_h
            baseline = row_bottom + (row_h - drawn_h) / 2.0
            x = cell_x0 + pad
            add_text(msp, drawn, x, baseline, drawn_h, TEXT_LAYER)
            msp_cells_entry = {
                "row": index,
                "key": label,
                "label": label_text,
                "drawn": drawn,
                "isLabel": is_label,
                "cellX0": round(cell_x0, 4),
                "cellX1": round(cell_x1, 4),
                "cellY0": round(row_bottom, 4),
                "cellY1": round(row_bottom + row_h, 4),
                "textHeight": round(drawn_h, 6),
                "insert": [round(x, 4), round(baseline, 4)],
                "estimatedWidth": round(text_width(drawn, drawn_h), 4),
                "truncated": bool(value_cut if not is_label else label_cut),
                "original": str(value) if not is_label else label,
            }
            cells.append(msp_cells_entry)

    return {"x0": round(tx0, 4), "y0": round(ty0, 4), "x1": round(tx1, 4), "y1": round(ty1, 4),
            "rows": len(rows), "columns": [round(tx0, 4), round(divider_x, 4), round(tx1, 4)],
            "widthRatioOfFrame": round(title_w / width, 4),
            "heightRatioOfFrame": round(title_h / height, 4),
            "cells": cells}


NORTH_UNKNOWN_LABEL = "SMJER NEPOZNAT"


def draw_unknown_north(msp, frame, cx, cy, r):
    """Empty compass rose: two plain rings, cardinal ticks and NO needle.

    The only honest symbol when the source carries no orientation. Drawing a
    needle up "by convention" is a false north: a reader cannot tell it from a
    real bearing. The words say the direction is unknown.
    """
    fx0, fy0, fx1, fy1 = frame
    lw = {"layer": NORTH_LAYER}
    msp.add_circle((cx, cy), r, dxfattribs=lw)
    msp.add_circle((cx, cy), 0.78 * r, dxfattribs=lw)
    for i in range(8):
        ang = math.radians(i * 45.0)
        ax, ay = math.sin(ang), math.cos(ang)
        inner = 0.83 * r if i % 2 == 0 else 0.87 * r
        msp.add_lwpolyline([(cx + inner * ax, cy + inner * ay),
                            (cx + 0.96 * r * ax, cy + 0.96 * r * ay)], dxfattribs=lw)
    msp.add_circle((cx, cy), 0.045 * r, dxfattribs=lw)
    label = NORTH_UNKNOWN_LABEL
    height = 0.26 * r
    width = len(label) * height * 1.2
    tx = min(max(cx, fx0 + width / 2.0 + 0.10), fx1 - width / 2.0 - 0.10)
    ty = cy - 1.45 * r
    txt = msp.add_text(label, dxfattribs={"layer": NORTH_LAYER, "height": height})
    from ezdxf.enums import TextEntityAlignment
    txt.set_placement((tx, ty), align=TextEntityAlignment.MIDDLE_CENTER)
    return {"centre": [round(cx, 4), round(cy, 4)], "radius": round(r, 4),
            "label": label, "needle": False, "degreesClockwiseFromDrawingUp": None,
            "tip": None, "height": round(height, 4),
            "textPosition": [round(tx, 4), round(ty, 4)]}


def draw_north_arrow(msp, frame, north, text_height, north_radius):
    """Professional compass rose.

    Outer ring is broken on the north bearing so the upright letter N sits in the gap
    between the two rings. The needle is a slim diamond: north half filled,
    south half outlined. One LINE remains the measurable shaft.
    """
    fx0, fy0, fx1, fy1 = frame
    r = north_radius
    cx = fx1 - 2.2 * r
    cy = fy1 - 2.2 * r

    degrees = north.get("degreesClockwiseFromDrawingUp")
    known = degrees is not None
    if not known:
        # No bearing in the source: an empty rose plus text. A needle at any
        # angle would be a north claim the data does not support.
        return draw_unknown_north(msp, frame, cx, cy, r)
    theta = math.radians(degrees)
    ux, uy = math.sin(theta), math.cos(theta)
    px, py = -uy, ux

    def pt(a, b):
        return (cx + a * ux + b * px, cy + a * uy + b * py)

    # Outer ring: two arcs leave a 24-degree gap at the top for the letter.
    gap = 12.0
    lw = {"layer": NORTH_LAYER}
    north_angle = 90.0 - math.degrees(theta)
    msp.add_arc((cx, cy), r, (north_angle + gap) % 360,
                (north_angle - gap) % 360, dxfattribs=lw)
    msp.add_circle((cx, cy), 0.78 * r, dxfattribs=lw)

    # Ticks on the inter-cardinal and cardinal points, north omitted.
    for i in range(1, 8):
        ang = theta + math.radians(i * 45.0)
        ax, ay = math.sin(ang), math.cos(ang)
        inner = 0.83 * r if i % 2 == 0 else 0.87 * r
        msp.add_lwpolyline([(cx + inner * ax, cy + inner * ay),
                            (cx + 0.96 * r * ax, cy + 0.96 * r * ay)],
                           dxfattribs=lw)

    # Slim diamond needle, north half filled, south half outline.
    tip = pt(0.72 * r, 0.0)
    tail = pt(-0.72 * r, 0.0)
    left = pt(0.0, -0.085 * r)
    right = pt(0.0, 0.085 * r)
    msp.add_solid([tip, left, right], dxfattribs=lw)
    msp.add_lwpolyline([tail, left, right], close=True, dxfattribs=lw)
    msp.add_circle((cx, cy), 0.045 * r, dxfattribs=lw)
    msp.add_line((cx, cy), tip, dxfattribs=lw)

    # N stays upright for readability, but its centre follows the north bearing.
    label = "N"
    txt = msp.add_text(label, dxfattribs={"layer": NORTH_LAYER, "height": 0.20 * r})
    from ezdxf.enums import TextEntityAlignment
    txt.set_placement(pt(0.89 * r, 0.0), align=TextEntityAlignment.MIDDLE_CENTER)

    return {"centre": [round(cx, 4), round(cy, 4)], "radius": round(r, 4),
            "label": label, "needle": True, "degreesClockwiseFromDrawingUp": degrees,
            "tip": [round(tip[0], 4), round(tip[1], 4)]}

def story_of(entity):
    """Story of an entity: explicit `story` first, else the S<n>_ layer prefix."""
    story = entity.get("story")
    if isinstance(story, (int, float)):
        return int(story)
    layer = str(entity.get("layer") or "")
    if layer.startswith("S") and "_" in layer:
        head = layer[1:].split("_", 1)[0]
        try:
            return int(head)
        except ValueError:
            pass
    return 0


def plan_sheets(plan):
    """Decide the sheet layout: one frame per story, side by side.

    Returns (sheets, single_mode). Each sheet is
    {story, label, bbox: (x0,y0,x1,y1) in local drawing coords, dx, dy} where
    (dx, dy) is the translation applied to that story's entities.
    Horizontal placement rule (documented): the frame of story i starts at the
    end of the previous frame plus FRAME_GAP_RATIO * (widest frame width).
    All sheets share one bottom line (lowest plan edge -> y = 0).
    """
    stories = plan.get("stories") or []
    if not plan.get("multiSheet") or len(stories) < 2:
        return [], True

    entries = []
    for s in stories:
        b = s.get("bounds") or {}
        x0, y0 = float(b.get("minX", 0.0)), float(b.get("minY", 0.0))
        x1, y1 = float(b.get("maxX", x0)), float(b.get("maxY", y0))
        span = max(x1 - x0, y1 - y0)
        if span <= 0:
            span = 1.0
            x1 = x0 + 1.0
            y1 = y0 + 1.0
        entries.append({
            "story": int(s.get("story", 0)),
            "label": s.get("label"),
            "entityCount": s.get("entityCount"),
            "bbox": (x0, y0, x1, y1),
            "span": span,
            "margin": FRAME_MARGIN_RATIO * span,
        })

    # One common text size keeps the sheets visually identical; the margin
    # follows each story's own bbox so a small floor does not swim in space.
    max_frame_width = max(
        (e["bbox"][2] - e["bbox"][0]) + 2 * e["margin"] for e in entries
    )
    gap = FRAME_GAP_RATIO * max_frame_width

    cursor = 0.0
    for e in entries:
        # Horizontal: the frame's own left edge lands on the cursor.
        e["dx"] = cursor + e["margin"] - e["bbox"][0]
        # Vertical: every sheet shares one bottom line (local minY -> y = 0).
        e["dy"] = -e["bbox"][1]
        e["frameWidth"] = (e["bbox"][2] - e["bbox"][0]) + 2 * e["margin"]
        cursor += e["frameWidth"] + gap
    return entries, False


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
        "CEILING": 30, # orange ceiling annotations only (the sloped band)
        "CEILING_FLAT": 8, # thin gray boundary of the FLAT ceiling remainder, never orange
        "CEILING_SEAM": 8, # reserved: group seams are no longer drawn (one-piece group)
        "WALL": 7,     # black/white — primary structure, full contrast
        "FLOOR": 8,    # dark gray — visible but recessive vs. walls
        "DOOR": 3,     # green — standard architectural convention
        "WINDOW": 5,   # blue — standard architectural convention
        "OPENING": 6,  # magenta — a hole with neither leaf nor glass is neither of those two
        "OBJECT": 9,   # light gray — furniture labels, de-emphasized
        "ROOM": 2,     # yellow — room outlines/labels
        "FRAME": 8,    # sheet furniture: recessive gray
        "TITLE": 7,    # title block text — same contrast as walls
        "NORTH": 7,    # north arrow
    }
    LAYER_LINEWEIGHT = {
        "CEILING": 9,  # 0.09mm dashed annotation, never wall thickness
        "CEILING_FLAT": 9,  # same thin weight, continuous line: no strip, just a boundary
        "CEILING_SEAM": 9,  # reserved for a source joint; not emitted for confirmed groups
        "WALL": 35,    # ~0.35mm — walls read as the thickest lines
        "FLOOR": 13,
        "DOOR": 35,    # openings carry the WALL weight: the coloured mark must
        "WINDOW": 35,  # cover the whole painted wall band it lies in, or half
        "OPENING": 35, # of it disappears under the wall's own 0.35 mm line
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

    if "CEILING_DASHED" not in doc.linetypes:
        doc.linetypes.new("CEILING_DASHED", dxfattribs={"description": "Ceiling annotation 8cm dash 4cm gap", "pattern": [0.12, 0.08, -0.04]})
    for name in plan.get("layers", []):
        if name not in doc.layers:
            doc.layers.add(name=name, color=color_for(name))
            doc.layers.get(name).dxf.lineweight = lineweight_for(name)
            if name.endswith("_CEILING"):
                doc.layers.get(name).dxf.linetype = "CEILING_DASHED"
                doc.layers.get(name).dxf.true_color = 0xFF8000

    sheets, single_mode = plan_sheets(plan)
    translations = {}
    if sheets:
        for sheet in sheets:
            translations[sheet["story"]] = (sheet["dx"], sheet["dy"])

    geometry_count = 0
    entity_story_count = {}
    ordered_entities = sort_by_draw_order(plan.get("entities", []))
    order_positions = [kind_of_layer(e.get("layer", "0")) for e in ordered_entities]
    last_wall_index = max((i for i, k in enumerate(order_positions) if k == "WALL"), default=-1)
    first_opening_index = next((i for i, k in enumerate(order_positions) if k in OPENING_KINDS), None)
    openings_above_walls = first_opening_index is None or first_opening_index > last_wall_index
    for e in ordered_entities:
        t = e["type"]
        layer = e.get("layer", "0")
        story = story_of(e)
        ox, oy = translations.get(story, (0.0, 0.0))
        entity_story_count[story] = entity_story_count.get(story, 0) + 1
        if t == "polyline":
            pts = [(p[0] + ox, p[1] + oy) for p in e["points"]]
            msp.add_lwpolyline(pts, close=bool(e.get("closed")), dxfattribs={"layer": layer})
        elif t == "line":
            msp.add_line((e["a"][0] + ox, e["a"][1] + oy),
                         (e["b"][0] + ox, e["b"][1] + oy), dxfattribs={"layer": layer})
        elif t == "text":
            txt = msp.add_text(e["value"], dxfattribs={"layer": layer, "height": e.get("height", 0.1)})
            txt.set_placement((e["pos"][0] + ox, e["pos"][1] + oy))
        elif t == "circle":
            msp.add_circle((e["centre"][0] + ox, e["centre"][1] + oy), e.get("radius", 0.1),
                           dxfattribs={"layer": layer})
        else:
            raise ValueError(f"Unknown entity type in plan: {t}")
        geometry_count += 1

    summary = {"geometryEntityCount": geometry_count, "titleBlock": None,
               "northArrow": None, "frame": None, "sheets": [], "sheetCount": 0,
               # Evidence that the file order really puts openings on top of
               # the walls, and which colour each opening layer carries.
               "drawOrder": {
                   "openingsAboveWalls": bool(openings_above_walls),
                   "firstOpeningIndex": first_opening_index,
                   "lastWallIndex": last_wall_index,
                   "order": {k: DRAW_ORDER[k] for k in sorted(DRAW_ORDER, key=DRAW_ORDER.get)},
                   "openingColors": {
                       lyr.dxf.name: lyr.dxf.color for lyr in doc.layers
                       if lyr.dxf.name != "0"
                       and kind_of_layer(lyr.dxf.name) in OPENING_KINDS
                   },
               },
               "layout": {"mode": "single-sheet", "gapRatio": FRAME_GAP_RATIO}}

    meta = plan.get("meta")
    if plan.get("frame") and meta:
        b = plan.get("bounds")
        if b:
            bbox = (b["minX"], b["minZ"], b["maxX"], b["maxZ"])  # plan Y is stored as Z
        else:
            bbox = (0.0, 0.0, 1.0, 1.0)

        if sheets:
            # ---- one sheet per story, side by side ------------------------
            common_span = max(
                max(s["bbox"][2] - s["bbox"][0], s["bbox"][3] - s["bbox"][1]) for s in sheets
            )
            text_height = TEXT_HEIGHT_RATIO * common_span
            summary["layout"] = {
                "mode": "per-story-sheets",
                "gapRatio": FRAME_GAP_RATIO,
                "gap": round(FRAME_GAP_RATIO * max(s["frameWidth"] for s in sheets), 6),
                "textHeight": round(text_height, 6),
            }
            for sheet in sheets:
                x0, y0, x1, y1 = sheet["bbox"]
                placed = (x0 + sheet["dx"], y0 + sheet["dy"], x1 + sheet["dx"], y1 + sheet["dy"])
                frame, title_h, radius, _row_h = plan_strips(placed, text_height, TITLE_ROWS)
                draw_frame(msp, frame)
                sheet_meta = dict(meta)
                sheet_meta["storyLabel"] = sheet.get("label") or meta.get("storyLabel")
                title = draw_title_block(msp, frame, sheet_meta, text_height, title_h,
                                         story_label=sheet_meta["storyLabel"])
                north = draw_north_arrow(msp, frame, meta.get("north") or {}, text_height, radius)
                note = meta.get("sourceNote") if sheet is sheets[0] else None
                if note:
                    nh = 0.50 * text_height
                    add_text(msp, fit_text(note, frame[2] - frame[0], nh)[0],
                             frame[0], frame[1] - 1.15 * nh, nh, TEXT_LAYER)
                summary["sheets"].append({
                    "story": sheet["story"],
                    "label": sheet_meta["storyLabel"],
                    "entityCount": entity_story_count.get(sheet["story"], 0),
                    "bbox": [round(v, 4) for v in placed],
                    "frame": [round(v, 4) for v in frame],
                    "titleBlock": title,
                    "northArrow": north,
                    "offset": [round(sheet["dx"], 4), round(sheet["dy"], 4)],
                })
            summary["sheetCount"] = len(summary["sheets"])
            summary["frame"] = summary["sheets"][0]["frame"]
            summary["titleBlock"] = summary["sheets"][0]["titleBlock"]
            summary["northArrow"] = summary["sheets"][0]["northArrow"]
        else:
            span = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
            if not span > 0:
                span = 1.0
            text_height = TEXT_HEIGHT_RATIO * span
            frame, title_h, radius, _row_h = plan_strips(bbox, text_height, TITLE_ROWS)
            draw_frame(msp, frame)
            summary["frame"] = [round(v, 4) for v in frame]
            summary["titleBlock"] = draw_title_block(msp, frame, meta, text_height, title_h)
            north = meta.get("north") or {}
            summary["northArrow"] = draw_north_arrow(msp, frame, north, text_height, radius)
            note = meta.get("sourceNote")
            if note:
                nh = 0.50 * text_height
                add_text(msp, fit_text(note, frame[2] - frame[0], nh)[0],
                         frame[0], frame[1] - 1.15 * nh, nh, TEXT_LAYER)
            summary["sheets"].append({
                "story": meta.get("story", 0),
                "label": meta.get("storyLabel"),
                "entityCount": geometry_count,
                "bbox": [round(v, 4) for v in bbox],
                "frame": summary["frame"],
                "titleBlock": summary["titleBlock"],
                "northArrow": summary["northArrow"],
                "offset": [0.0, 0.0],
            })
            summary["sheetCount"] = 1

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
