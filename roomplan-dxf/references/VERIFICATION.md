# Verification against real Drawing-Bridge (Swift) output

Date: 2026-09-22. Performed against `vzornjak/Drawing-Bridge` commit
`f85e5da` ("Support multiroom RoomPlan envelopes"), built in release mode on
a remote Mac (`vzornjakm1`) via SSH/Tailscale:

```sh
swift build -c release --product drawing-bridge
.build/release/drawing-bridge roomplan-raw-to-dxf <capture.json> out.dxf manifest.json
.build/release/drawing-bridge optimized-roomplan-to-dxf <capture.json> out.dxf manifest.json
```

## Method

1. Ran both the Node converter (this repo) and the real Swift CLI on the
   same two source captures (one raw Apple RoomPlan export with two
   `roomplanSessions`, one Polycam Optimized export with 9 rooms across 2
   floors).
2. Loaded both DXF outputs with `ezdxf` and extracted every entity as
   `(type, layer, rounded coordinates)`.
3. Sorted both entity lists identically and diffed them pairwise.

## Result

| Source | Swift entities | Node entities | Geometry mismatches |
|---|---|---|---|
| raw capture (`roomplan.json`) | 56 | 56 | **0** |
| optimized capture (`optimized_roomplan.json`) | 72 | 72 | **0** |

Both DXF files also pass `ezdxf.audit.Auditor()` with 0 errors, and match
Swift's own DXF version (`AC1032` / AutoCAD 2018 / R2018).

## Bugs this caught (fixed before the above result)

1. **Z-axis sign flip.** Ground-plane Z was mapped to DXF Y with the wrong
   sign (`+z` instead of `-z`), mirroring every plan vertically. Only found
   by comparing numeric bounds against Swift output — visually both "looked
   like a floor plan" until overlaid.
2. **`polygonCorners` used for walls/doors/windows.** The Node port used
   `polygonCorners` when present and fell back to a naive axis-aligned
   segment otherwise. Real Swift *never* uses `polygonCorners` for anything
   except floors — walls/doors/windows/openings are always a
   footprint/centerline computed purely from `dimensions` (+ `wallThickness`
   for optimized walls). This produced extra/wrong segments and, in the
   fallback case, "infinite"-looking horizontal lines ignoring the wall's
   actual orientation.
3. **Objects drawn as text labels instead of footprints.** Swift draws
   furniture as a footprint rectangle (`dimensions.x` × `dimensions.z`).
4. **Story assignment done per-floor-surface instead of per-room.** Swift's
   `AppleRoomPlanJSONDecoder.storyAssignments` operates per *room* (checking
   for a single consistent explicit `story` value across all of a room's
   records, else clustering rooms by median floor elevation, 0.8m
   tolerance). The Node port previously clustered individual floor surfaces
   directly, using a different clustering algorithm, which could produce a
   different (wrong) story count on the same input.
5. **Optimized `alignment_transform` parsed incorrectly.** The real Polycam
   export encodes this as an object with `t00..t33` keys (column-major), not
   a flat 16-number array. The old parser silently fell back to identity,
   discarding a real source-provided transform.

## When to re-run this

Any change to `align.js`, `dxf-writer.js`, `transform.js`, `decode-raw.js`,
or `decode-optimized.js` should be re-verified this way before being
trusted — these are exactly the files where a sign error or a swapped
axis/field still produces a DXF that opens and "looks plausible" while being
silently wrong. `docs/compare_entities.py` (if present) automates step 2–3
above; otherwise re-derive it inline as shown here.

---

# Verifikacija 2026-11-07: sjever (flip 180°), tekst u ćelijama, katovi

Stvarni dvokatni sken (`attachments/uploads/scan.json` + `meta.json`) kopiran
je u `/tmp` i tamo pretvoren; upload je ostao netaknut (sha256 prije i poslije
identičan). U javnom paketu isti kod prolazi 35 testova (`tests/selftest.py`),
a ovdje su ključni rezultati stvarnog crteža:

| provjera | rezultat |
|---|---|
| `ezdxf` audit | **0 grešaka, 0 popravaka** |
| katovi | 2 (`Prizemlje`, `1. kat`) → **2 okvira jedan pored drugoga** |
| razmak okvira | 0,623 m = točno **8 %** širine najšireg okvira |
| bboxovi katova | **bez preklapanja** (lijevo→desno) |
| entiteti po okviru | svaki `S<n>_*` entitet unutar svog okvira (0 izuzetaka) |
| strelice sjevera | **2**, obje **345,28°** (stara formula: 165,28°) |
| tekst u ćelijama | najveći preljev **0 %** (tolerancija 5 %), nijedno skraćivanje |
| ukupno | 115 entiteta, 14 slojeva, `lossy: true` |

Formula: `(alignmentOffset − heading) mod 360`; heading 42,352° +
alignment offset 27,629° → 345,28°. `--no-north-flip` vraća 165,28°.
Kontrolni slučajevi u javnom selftestu: heading 0° → 0°, heading 90° → 270°,
heading 15° → 345° (stara formula 165°).

Vendor usporedba (read-only `/var/minis/mounts/Downloads/Project hh`): vendor
DXF crta glavu strelice na ~3,8° (praktički prema gore) i slovo `N` na ~183,8°,
tj. **180° od glave** — artefakt je sam po sebi dvosmislen i ne može razlučiti
dvije formule, pa je mjerodavna vizualna potvrda na stvarnom crtežu. Uz to,
vendor rotira svoj list tako da je sjever gore. Nijedan podatak iz vendor skena
nije kopiran u paket.

Hashovi izvora korištenih u ovoj provjeri: `scan.json`
`48bcaef0224ae0a5c3fd1ba60893242e6f6c5d63cabec0bc517e1c71affbe785`,
`meta.json` `088f4296dff21e2cf0469d1d69d2f2613edbac30ef488977e8a8cea9068d5fbf`.
