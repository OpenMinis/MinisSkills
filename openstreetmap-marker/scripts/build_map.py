#!/usr/bin/env python3
"""Generate a previewable marker map HTML page from the template + a landmarks JSON file.

Usage:
  python3 build_map.py <landmarks.json> <output.html> [--title "Title"] [--header "⚡ text"]
                       [--center lat,lng] [--zoom N] [--style light|dark]

landmarks.json format (array of objects):
  {"name": "West Lake", "desc": "UNESCO World Heritage Site", "address": "West Lake, Xihu District, Hangzhou",
   "lat": 30.2614, "lng": 120.1443, "type": "green", "icon": "fa-tree"}

  Required: name, lat, lng
  Optional: desc (extra note shown in the info card), address (shown under a 📍 row, Google-Maps-style),
            type (red/green/blue/purple/brown/orange, dot color AND default Font Awesome icon, defaults to blue),
            icon (a Font Awesome solid icon class like "fa-store", overrides the type default; if omitted,
                  the marker uses a sensible icon based on type)

If --center/--zoom are omitted, the map auto-fits all points (single point excepted, uses --center or
that point's coordinates, zoom defaults to 14).
"""
import sys, json, argparse
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "assets" / "template.html"

TILE_STYLES = {
    "light": "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
    "dark": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("landmarks_json")
    ap.add_argument("output_html")
    ap.add_argument("--title", default="Custom Marker Map")
    ap.add_argument("--header", default="⚡ Pikachu Map")
    ap.add_argument("--center", default=None, help="lat,lng manual center override")
    ap.add_argument("--zoom", type=int, default=None)
    ap.add_argument("--style", default="light", choices=list(TILE_STYLES.keys()))
    ap.add_argument("--show-location", action="store_true", default=False,
                    help="Show a locate button that displays the user's current position as a pulsing blue dot")
    args = ap.parse_args()

    with open(args.landmarks_json, encoding="utf-8") as f:
        landmarks = json.load(f)

    for item in landmarks:
        item.setdefault("desc", "")
        item.setdefault("type", "blue")
        item.setdefault("icon", "")  # empty -> template picks a Font Awesome icon based on `type`

    if args.center:
        clat, clng = map(float, args.center.split(","))
    elif landmarks:
        clat = sum(i["lat"] for i in landmarks) / len(landmarks)
        clng = sum(i["lng"] for i in landmarks) / len(landmarks)
    else:
        clat, clng = 30.0, 120.0

    zoom = args.zoom if args.zoom else (14 if len(landmarks) <= 1 else 12)

    tpl = TEMPLATE.read_text(encoding="utf-8")
    html = (
        tpl.replace("__PAGE_TITLE__", args.title)
        .replace("__HEADER_TEXT__", args.header)
        .replace("__LANDMARKS_JSON__", json.dumps(landmarks, ensure_ascii=False))
        .replace("__CENTER_LAT__", str(clat))
        .replace("__CENTER_LNG__", str(clng))
        .replace("__ZOOM__", str(zoom))
        .replace("__TILE_URL__", TILE_STYLES[args.style])
        .replace("__LOCATE_BTN_DISPLAY__", "flex" if args.show_location else "none")
    )

    Path(args.output_html).write_text(html, encoding="utf-8")
    print(f"Generated {args.output_html} ({len(landmarks)} markers)")


if __name__ == "__main__":
    main()
