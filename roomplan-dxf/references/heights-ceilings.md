# Stropovi i visine u DXF-u — provjerene pretpostavke

Ovo je **konzervativna anotacija iz izvora**, ne rekonstrukcija stropa i ne
renderer stare web aplikacije. Historijska parity nije uspostavljena.

## Current source-region annotation contract (2026-11-08)

- Explicit supplied ceiling polygons are retained as source regions, labelled
  `SR <room identifier>.<index>`. Read `sourceRegionId`, `interpretation`,
  `regionPlanM`, `worldCornersM` and `heightM` in ceiling diagnostics.
- Multiple supplied surfaces are alternatives that may overlap or conflict:
  `roomplan.ceiling-source-alternatives`. No minimum/maximum physical envelope
  is selected or verified. An individual region height is not a certified
  room-wide clear height; source regions are not additive physical quantities.
- Explicit horizontal source regions retain their thin gray outline and SR
  height label on `S<n>_CEILING_FLAT`; they are not orange slope bands.
  Reconstructed flat ceilings do not acquire a whole-room dashed slope outline.
- Layout tests a conservative TEXT envelope inside each polygon, then a local
  external callout with a checked leader. If neither fits, annotation remains
  visible with `UNRESOLVED` and `layoutStatus: unresolved-visible-no-leader`;
  no unsafe leader is fabricated. This is an unresolved association requiring
  review, not successful in-region placement. Arbitrary CAD font substitutions
  and full paper plotting remain outside this guarantee.
- Short downhill arrows are checked within the region; annotation offsets do
  not change source geometry or measurement quantities. Per-story framing
  translates geometry and text together once, after source-space alignment.
- `supplied-floor-level` is an explicitly supplied scalar fallback, not a
  measured floor plane. Positive separations up to 6 m can remain visible,
  including low heights; do not silently clamp them to plausible room heights.
- A structurally clean DXF requires audit `errors: 0` AND `fixes: 0`. It does
  not resolve source conflicts, low heights, unknown heights, unresolved labels
  or establish a verified physical envelope. Review diagnostics separately.

## Povijesne bilješke — nisu aktualni ugovor

Sljedeće bilješke zadržane su radi tragova ranijih interpretacija. Aktualni
ugovor iznad ima prednost: osobito source-region alternative, pozitivne niske
visine, eksplicitne ravne plohe i unresolved-visible-no-leader. Povijesna tvrdnja
da wall-top inferencija nije implementirana ne vrijedi za postojeći
ceiling-reconstruct fallback. Nema verified physical envelopea.

## Što se čita

Samo optimized/Polycam izvor ima eksplicitne stropove: `rooms[].ceiling` i
`rooms[].ceiling_curr[]`, svaki s `transform` (4×4, column-major) i `polygon`
(lista `[x, y]` u lokalnoj ravnini, `z = 0`). Primjer iz stvarnog skena
(`optimized_roomplan.json`): 9 soba, 12 stropnih ploha, `ceiling` i
`ceiling_curr` identični. Raw Apple izvor (`scan.json`) **nema** stropove.

`polygon` se ne miješa s `polygonCorners`: `polygon` je 2D lokalni par, a
`polygonCorners` je 3D lokalni vrh. Podržana su oba oblika, ali nikad oba
odjednom za istu plohu.

## Prostorni slijed (točno jednom)

1. `transform` plohe: lokalni vrh → **source world** (isti prostor kao zidovi i
   podovi; metri).
2. `alignment_transform` / arhitektonska poravnanja: primijenjena **jednom** na
   source world, prije projekcije.
3. projekcija tlocrta `(x, y) = (x, −z)` i per-story translacija okvira.

Anotacijski 3 cm offset i 3 cm trim **ne ulaze** ni u jedno mjerenje. Nema
dvostruke transformacije: test `tests/test_ceilings.js` provjerava rotirani
alignment i numerički rezultat.

## Visina

Visina je **vertikalna razlika u source world prostoru**, nikad
`dimensions.y` i nikad fiksna 2,5 m.

| pokrivenost | uvjet | značenje |
|---|---|---|
| `computed` | horizontalna podna ploha istog kata pokriva **sve** vrhove stropa (±2 cm) i `room.floor_height` se s njom slaže (±2 cm) | izmjereno iz podnog poligona |
| `supplied-floor-level` | nema pokrivne podne plohe, ali `room.floor_height` postoji i razlika je unutar 1,5–6,0 m | visina iz izvornog skalara, **nije** izmjereni pod |
| nema | podna ploha proturječi skalaru >2 cm, razlika ≤0 ili >6 m | `null` uz `heightReason` i upozorenje |

Oznaka je `h 2,50 m` kad je ploha vodoravna, inače `h 2,10–2,85 m` (min/max po
vrhovima). Zapis u `manifest.ceilingDiagnostics.records[].heightM` nosi
`min`, `max`, `coverage`, `basis`, `floorElevationM`.

Stvarni rezultat na `optimized_roomplan.json` (7.11.2026): 9 od 12 ploha ima
`h 2,77–2,79 m` (`supplied-floor-level`); 2 plohe sobe `1_3`/`1_4` ostaju
`null` jer `room.floor_height` (1,803 m) proturječi transformiranoj podnoj
plohi kata (0,855 m) za 0,95 m — sukob se prijavljuje, ne rješava nagađanjem.

## Crtanje

- Sloj **`S<n>_CEILING`** po katu, boja ACI 30, truecolor `0xFF8000`.
- Linija `CEILING_DASHED` (8 cm crtica / 4 cm praznina), lineweight 9 (~0,09 mm).
- Offset 3 cm prema van od stropa, trim 3 cm na krajevima, samo ako su offset i
  sredina unutar izvornog (i konkavnog) poligona; inače se rub preskače i broji
  u `skippedOffsetEdges`.
- Duplikati segmenata (isti kat, isti zaokruženi par) crtaju se jednom.
- Tekst se postavlja samo ako cijeli bbox stane u poligon stropa i ne siječe
  postojeću geometriju/tekst; inače `roomplan.ceiling-label-layout` — traženje
  je konzervativno i **nije** jamstvo CAD layouta.
- Postojeća zidna/podna geometrija i sve količine ostaju nepromijenjene; offset
  nikad ne ulazi u `netAreaM2`.

### Ravan strop i kosi pojas (8.11.2026)

Profil s prelomom (knee) ima kosinu **samo uz niski zid**, u dužini mjerenog
`run` (Project hh: 1,2248 m), a dalje je ravan na ridžu. Zato:

- **`S<n>_CEILING` nosi samo kosi pojas**: njegov isprekidani obris, liniju pada
  sa strelicom, liniju ridža i oznaku `h 1.65-2.48 (knee)`.
- **`S<n>_CEILING_FLAT`** (tanka neprekidna linija, siva, nikad narančasta)
  nosi granicu ravnog dijela i oznaku `h 2.48 (flat)`.
- **Ravan strop se ne crta uopće** — ni rekonstruirani ni eksplicitni s
  nagibom < 2,5°. Visinu nosi oznaka sobe (`Room  40.49 m2  h 3.07`); trake
  preko cijelog stropa bile su čisti šum.
- Dvovodni krov (gable, `downhill === 'both'`) daje dva pojasa s ridžom u
  sredini, plus ravni plato samo ako profil ima ravni segment.

Isti rez se koristi u 3D-u (`lib/ceiling-3d.js`, `splitCeilingPlan`) i u DXF-u
(`lib/ceilings.js`), pa se površina pojasa u planu i u USDZ-u ne može razići.

## Nedostupno / ograničenja

- Raw format: nema stropova → `roomplan.ceiling-missing`, bez rekonstrukcije iz
  gornjih rubova zidova. Wall-top inferencija nije implementirana (svjesno).
- `ceiling` vs `ceiling_curr` različiti → `roomplan.ceiling-conflicting-variants`,
  bez odabira.
- Vertikalna ploha, neplanarni ili samosiječući poligon, ne-rigidna matrica →
  `roomplan.ceiling-unsupported`.
- Površina stropa >20 % različita od `room.area` → `roomplan.ceiling-area-discrepancy`.
- Neuniformni gornji rubovi zidova, kose plohe bez eksplicitnog poligona i
  stvarni nagibi krovnih ploha izvan su dosega ovog prikaza.
- Stari web engine nije uspoređen; vidi `REPORT-2026-11-07.md` u skillu za
  primjedbe iz dostupnih kopija.
