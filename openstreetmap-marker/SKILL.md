---
name: openstreetmap-marker
version: 1.1.0
description: Generate a mobile-first, immersive, Amap(Gaode)-style custom landmark marker HTML map for travel itinerary planning, place showcasing, location sharing, etc. Built on Leaflet + OpenStreetMap, no API key required. Trigger when the user mentions "annotate a map", "travel map", "itinerary map", "mark locations", "map display", "trip planning map", "OpenStreetMap marker", or asks to generate a map page for a city/set of places. Includes a built-in GCJ-02 (Mars/China coordinate system used by Amap/Tencent/Baidu/Apple Maps search results in mainland China) to WGS-84 (Leaflet basemap coordinate system) conversion tool to avoid marker offset in mainland China.
---

# OpenStreetMap Marker

Generates a self-contained, browser-previewable custom marker map HTML page styled after Amap's mobile app (light minimal basemap + circular colored icon + text label + immersive full-screen layout with safe-area support).

## Core Workflow

1. **Get marker coordinates**: prefer `apple-maps search --query "place name city" --lat <city lat> --lon <city lng> --limit 1 -q --compact`, which returns JSON with `lat`/`lon`/`coordinate_system`.
2. **Coordinate conversion (critical, do not skip)**: apple-maps / Amap / Tencent / Baidu almost always return **GCJ-02** coordinates in mainland China, while this skill's Leaflet+OSM/CartoDB basemap uses **WGS-84**. Using GCJ-02 directly causes markers to drift tens to hundreds of meters (often landing in a river/sea). Coordinates within mainland China MUST be converted with `scripts/gcj_convert.py` before writing to landmarks.json; the script auto-skips conversion for points outside China (out_of_china check).
   ```bash
   python3 /var/minis/skills/openstreetmap-marker/scripts/gcj_convert.py <lng> <lat>
   # outputs "wgs_lat,wgs_lng"
   ```
3. **Assemble landmarks.json**: an array, each item:
   ```json
   {"name": "West Lake", "desc": "UNESCO World Heritage Site, Hangzhou's iconic landmark", "address": "Xihu District, Hangzhou", "lat": 30.2614, "lng": 120.1443, "type": "green", "icon": "fa-tree"}
   ```
   - `name`/`lat`/`lng` required; `desc`/`address`/`type`/`icon` optional
   - `type` determines the marker dot color: `red` (government/medical/core attraction) `green` (park/nature) `blue` (transport/building) `purple` (commercial/venue) `brown` (heritage/university) `orange` (other), defaults to blue. Each type also has a sensible **default Font Awesome icon** (red→fa-star, green→fa-tree, blue→fa-building, purple→fa-bag-shopping, brown→fa-landmark, orange→fa-circle-dot) — leave `icon` empty to use it.
   - `icon` (optional): a Font Awesome 6 **solid**-style icon class name, e.g. `"fa-train"`, `"fa-utensils"`, `"fa-mosque"`, `"fa-museum"`, `"fa-mountain"`. Overrides the type default. Look up icon names at fontawesome.com/icons (free "solid" set) — do NOT use emoji, all icons are unified Font Awesome glyphs rendered via `<i class="fa-solid ...">` for a consistent cross-device look.
   - Write this JSON array to a temp file with file_write, e.g. `/tmp/landmarks.json`
4. **Generate the page**:
   ```bash
   python3 /var/minis/skills/openstreetmap-marker/scripts/build_map.py \
     /tmp/landmarks.json /var/minis/workspace/<descriptive-filename>.html \
     --title "West Lake Area Landmarks" --header "⚡ Hangzhou Trip" \
     --style light
   ```
   - `--style light` (default, light minimal, Amap-like palette) or `--style dark` (dark immersive)
   - Without `--center`/`--zoom`, the script auto-centers/zooms to fit all points with padding; a single point defaults to zoom 14
5. **Deliver**: present the result to the user as a Markdown link `[Preview](minis://workspace/<filename>.html)`, tappable to open in the built-in browser.

## Built-in style features (already handled by the template, no need to re-explain)

- Full-screen immersive: `viewport-fit=cover` + `env(safe-area-inset-*)` for notch/Dynamic Island devices
- Semi-transparent top status bar (live clock on the left, custom header text on the right)
- No bottom search bar / tab bar / side floating buttons (kept minimal per user preference — just map + markers)
- Markers are circular colored icons (Font Awesome, loaded via CDN `cdnjs.cloudflare.com/.../font-awesome/...`) + white text label pills for a unified, non-emoji icon style
- Leaflet zoom control hidden by default (`zoomControl: false`) for a clean UI
- **Tapping a marker opens a Google-Maps-style bottom info card** (not Leaflet's default popup) showing: title (with FA icon), address (if provided, 📍-style row), coordinates (lat, lng), and desc as a note below a divider — no ratings/route/save/share buttons, kept intentionally minimal. A close (✕) button and tapping the basemap both dismiss it.
- The info card has a single **"Open Location in..." button**, which slides up a bottom action sheet listing available map apps vertically (Amap / Google Maps / Apple Maps), each with an FA icon; a "Cancel" row closes the sheet. Available options are platform-aware:
  - **Amap** (labeled "高德地图" in the sheet UI): only shown if the point falls within mainland China (coarse lat/lng range check). landmarks.json stores WGS-84 — the frontend JS auto-converts WGS-84→GCJ-02 before building the Amap deep link.
  - **Google Maps**: always shown.
  - **Apple Maps**: only shown on iOS (UA-detected); hidden on Android since it's not a relevant/installable app there.
  - Platform is detected via `navigator.userAgent` (`isAndroid` / `isIOS`). Each option first tries a **native URL scheme / intent** to directly launch the installed app even from inside an embedded WebView — plain `https://` links alone do NOT auto-launch native apps in an embedded webview (only a full browser like Safari/Chrome does that reliably). A short `setTimeout` fallback then redirects to the equivalent `https://` web link if the scheme silently fails (app not installed):
    - Amap: `iosamap://` (iOS) / `amapuri://` (Android) → fallback `https://uri.amap.com/marker?...`
    - Google Maps: `comgooglemaps://` (iOS) / `geo:lat,lng?q=...` (Android) → fallback `https://www.google.com/maps/search/?api=1&query=...`
    - Apple Maps: `maps://` → fallback `https://maps.apple.com/?ll=...`

## Tile provider note

Uses CARTO's free Voyager/Dark basemap tiles (no API key required) — fine for personal/demo use, but subject to CARTO's rate limits and non-commercial-scale terms. For high-traffic production use, switch `TILE_STYLES` in `scripts/build_map.py` to a licensed provider (Mapbox, Stadia Maps, etc.).

## Common adjustments

- Change basemap: edit `TILE_STYLES` in `scripts/build_map.py` and add a new key, e.g. Esri World Imagery tile URL for satellite view
- Add routes/tracks: append `L.polyline([[lat,lng],...]).addTo(map)` to the generated HTML; these coordinates also need GCJ-02→WGS-84 conversion first if in mainland China
- Multi-day itineraries: generate one HTML per day, or use different `type` colors to distinguish Day1/Day2/Day3

## Reference files

- `scripts/gcj_convert.py` — GCJ-02→WGS-84 coordinate conversion (single-point CLI and batch JSON mode)
- `scripts/build_map.py` — map HTML generator
- `assets/template.html` — page template with placeholders `__PAGE_TITLE__` `__HEADER_TEXT__` `__LANDMARKS_JSON__` `__CENTER_LAT__` `__CENTER_LNG__` `__ZOOM__` `__TILE_URL__`
