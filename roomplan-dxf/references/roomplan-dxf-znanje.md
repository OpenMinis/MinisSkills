# RoomPlan → DXF: izvučeno znanje iz koda (ArchiDrawing `converter/`)

> **Povijesna referenca, dopuna 7.11.2026.** Današnji adapteri skilla više ne koriste detekciju po label/category/meshInfo iz A1 ni bezuvjetni zahtjev format_version iz A3. Vrijede [formats.md](formats.md) i [model-schema.md](model-schema.md): eksplicitni optimized v1, pozitivno prepoznat legacy bez verzije, sadržajna raw detekcija i opcionalni --model. Nepoznate eksplicitne verzije ostaju odbijene; label_automated može biti odsutan, bez izmišljenog imena. Izvorni ArchiDrawing/converter/lib/model.js pregledan je read-only; prazan module.exports i dokumentirana zajednička geometrija nisu kompletni RoomPlan/mesh parser. Arhivirani upstream nije mijenjan. IoU/session registracija opisuje zasebni aplikacijski kod, ne ovaj CLI. Raniji navodi o klonu i stanju GitHuba ispod povijesni su, nisu nova mrežna provjera. archi-alpine nije pregledan; iz toga se ne zaključuje da ne postoji.


> Sirovina za pisanje skillova `roomplan` i `dxf`. Sve je izvučeno **iz koda i dokumenata**, ne iz općeg znanja.
> Izvori: `/var/minis/shared/ArchiDrawing/converter/` (identično GitHubu, potvrđeno `diff -r` = IDENTICAL),
> svježi klon `github.com/vzornjak/ArchiDrawing` u `/tmp/archidrawing` (sadrži i `web/`, `docs/`, `package.json`, `README.md`),
> `/var/minis/memory/2026-09-22.md`, `2026-09-23.md`, `2026-09-24.md`, `2026-09-27.md`, `2026-09-28.md`,
> `/var/minis/shared/ArchiPlan/cad-first-plan.md`, te git povijest repoa preko `gh api`.
>
> Repo je **arhiviran** (GitHub `archived:true`, `pushed_at 2026-09-27T19:46:13Z`), `default_branch: main`,
> privatni `vzornjak/ArchiDrawing`. Zadnji commit `4806a3c` "docs: archive research and link canonical ArchiPlan guide".

---

## A. ROOMPLAN — ulazni format

### A1. Koje oblike ulaza converter prihvaća i kako ih razlikuje (`detectFormat()`)

`detectFormat(json)` u `converter/roomplan-to-dxf.js` vraća `'raw'` ili `'optimized'`, ovim redom:

1. **`'optimized'`** ako vrijedi: `Array.isArray(json.rooms) && json.rooms.length > 0 && (json.rooms[0].label !== undefined || json.rooms[0].category !== undefined || json.rooms[0].meshInfo !== undefined)`.
2. **`'raw'`** ako `json.captureSessions && Array.isArray(json.captureSessions)`.
3. **`'raw'`** ako `Array.isArray(json.rooms) || json.walls || json.surfaces || json.objects`.
4. Inače baca:
   `'Unrecognized RoomPlan JSON shape: expected raw CapturedRoom/CapturedStructure (optionally wrapped in captureSessions[].roomplanSessions[]) or Optimized/Polycam "rooms[]" with label/category/meshInfo.'`

**Web verzija** (`web/roomplan-core.js`, `detectFormat`) razlikuje se (drugačiji test i hrvatska poruka):
- `'optimized'` ako `rooms[0].label_automated !== undefined || rooms[0].vertices_x !== undefined || rooms[0].meshInfo !== undefined`; **ili** ako `json.format_version === 1 && Array.isArray(json.walls)`.
- `'raw'` ako `captureSessions`; `'raw'` ako `rooms || walls || surfaces || objects`.
- Inače baca `'Neprepoznat oblik RoomPlan JSON-a.'`

**Zamka (dokumentirano stanje koda, ne pretpostavka):** converter provjerava `.label`/`.category`, a web `.label_automated`/`.vertices_x`. `meshInfo` se pojavljuje **samo u `detectFormat`** i nigdje se dalje ne čita/sprema (nema ga ni u `decode-optimized.js` ni u `model.meta`). Raw `CapturedStructure` je `{rooms:[CapturedRoom,...]}` gdje sobe nemaju `label/category/meshInfo`, pa pada na korak 3 (`raw`).

Detalji wrappera u raw dekoderu, funkcija `roomRecords(root)` (`lib/decode-raw.js`):
- ako `root.walls` → `[root]` (pojedinačni `CapturedRoom`);
- ako `Array.isArray(root.rooms)` → `root.rooms` (baca `'Malformed raw RoomPlan JSON at rooms'` ako je prazno);
- ako `Array.isArray(root.captureSessions)` → konkatenacija svih `cs.roomplanSessions` (baca `'Malformed raw RoomPlan JSON at captureSessions'` ako je prazno, odnosno `'...captureSessions[].roomplanSessions'` ako sesija nema/nema neprazan `roomplanSessions`);
- inače `[root]`.

### A2. Koordinate, jedinice, transform, poligon, dimenzije

- **Transform je 4×4 column-major**, ARKit/RoomPlan konvencija (`lib/transform.js`):
  `m[0..2]` = X os, `m[4..6]` = Y os, `m[8..10]` = Z os, `m[12..14]` = translacija (`m[12]=tx`, `m[13]=ty`, `m[14]=tz`).
  Pomoćne funkcije: `apply(m,p)`, `multiply(a,b)` (vraća `a*b`, tj. prvo primijeni `b` pa `a`), `identity()`, `rotationY(radians)` (rotacija oko **world Y** = ARKit "up"), `worldX/worldY/worldZ(m)` = `m[12]/m[13]/m[14]`, `apply2D`, `project`.
- **`transform` se u dekoderu čuva lokalno/netransformirano.** Eksplicitno u docstringu `decode-raw.js`: `polygonCorners` i `transform` ostaju točno kako su dekodirani; `surface.transform` i alignment primjenjuju se tek pri projekciji (`composed(alignment, surface.transform)`). Prethodno transformiranje značilo bi dvostruku transformaciju.
- **Projekcija u DXF ravninu: `project(p) = { x: p.x, y: -p.z }`** — ground-plane točka `(x,z)` → DXF `(x, y=-z)`. "Load-bearing" pravilo (README + `transform.js`).
- **Jedinice:** metri (RoomPlan/ARKit). `dimensions` je `[x, y, z]` i pretvara se u `{x,y,z}`.
- **Duljina zida = `dimensions.x`**, **visina zida = `dimensions.y`**, **debljina zida = `dimensions.z`** (raw format).
  Optimized: duljina `dimensions.x`, debljina `wall_thickness` ako postoji, inače `dimensions.z`, inače `0.1`.
  `dimensions.y` (visina) **ne koristi se** za geometriju crtanja (samo za izračune u web report modelu).
- Raw wall kad je `dimensions.z <= 0`: nema izmjerenu debljinu → crta se **centerline**, ne footprint (uz manifest upozorenje).
- `polygonCorners` je lista `{x,y,z}`; koristi se **samo za `floor`** (i u webu za detekciju kosih zidova). Za zidove/vrata/prozore/otvore nikad.
- **Elevacija** (za dodjelu kata) = `transform[13]` (world Y); fallback za sobu bez podova: medijan `transform[13] - dimensions[1]/2` (donji rub zida).
- **`curve`** (samo raw): `{centerX, centerZ, radius, startAngleRadians, endAngleRadians}`, s fallback imenima `center_x`, `center_z`, `start_angle`, `end_angle`. `align.js` preskače zakrivljene zidove (`if (w.curve) continue`).

### A3. Sadržaj po tipu elementa

Raw `Surface` (kind = `'wall' | 'floor' | 'door' | 'window' | 'opening'`; u JSON-u su ključevi u množini `walls/floors/doors/windows/openings`, `kind` se dobije `kind.replace(/s$/,'')`):
`identifier`, `parentIdentifier` (ili `null`), `kind`, `category` (prvi ključ objekta kategorije, npr. `'wall'`), `confidence` (prvi ključ objekta pouzdanosti, npr. `'high'`), `story`, `dimensions {x,y,z}`, `transform[16]`, `polygonCorners [{x,y,z}]`, `curve | null`, `isOpen | null`.
`isOpen` se puni **samo za vrata**: `kind === 'doors' && record.category.door` → `!!record.category.door.isOpen`.

Raw `Obj` (namještaj):
`identifier`, `parentIdentifier`, `category` (prvi ključ ili `'object'`), `confidence`, `story`, `dimensions`, `transform`. **Nema `polygonCorners` ni drugih polja**; crta se kao pravokutnik `dimensions.x × dimensions.z`.

Raw `Capture` kao cjelina (`model`): `kind:'raw'`, `sourceByteCount`, `sourceSHA256`, `originalFilename`, `storyAssignmentMethod`, `surfaces[]`, `objects[]`, `rooms:null`, `meta:{ roomCount }`.
Web raw dodatno: `roomSessionCount`, `storyOrigins` (Map story → `referenceOriginTransform`, prvi viđeni), a svaki element nosi i `roomIdx`.

Optimized `Surface`/`Obj` (`lib/decode-optimized.js`):
`identifier`, `parentIdentifier`, `kind` (= `'wall'|'floor'|'door'|'window'|'opening'|'object'`), `category` (string ili prvi ključ objekta), `categoryDetail` (iz `record.category_detail`), `confidence` (string ili prvi ključ), `story`, `dimensions`, `transform[16]`, `polygonCorners[]` (čuva se lokalno), `wallThickness` (iz `record.wall_thickness`, inače `null`).
**Specijalno za `floor` u optimized:** `identifier = 'floor-' + story`, `dimensions = {x:1, y:0, z:0}`, `category = 'floor'` (bez obzira na ulaz).

Optimized `Room` (`decodeRoom`): `identifier` (iz `record.id`), `label` (iz `record.label_automated`), `category` (iz `record.category`), `story`, `area` (iz `record.area`), `floorHeight` (iz `record.floor_height`), `centerX`/`centerZ` (iz `record.center_xz[2]`), `vertices` (iz `record.vertices_x[]`/`record.vertices_z[]`), `edges`, `ceilingLidarAverageDifference` (iz `ceiling_lidar_avg_diff`), `ceilingLidarValidFraction` (iz `ceiling_lidar_valid_pct`).

`model` za optimized: `kind:'optimized'`, `storyAssignmentMethod:'source-provided'`, `surfaces` (sve osim objekata), `objects`, `rooms[]`, te `meta:{ formatVersion, alignmentTransform, latitude, longitude, altitude, orientationDegrees, orientationUncertaintyDegrees, jointCount }` (web drži ta polja raspršeno, npr. `formatVersion`, `alignmentTransform`, `latitude`...).

### A4. Multi-room i multi-story

**Multi-room:** `roomRecords()` spljošti `rooms[]` ili `captureSessions[].roomplanSessions[]` u jednu listu soba; svi elementi svih soba idu u isti `surfaces`/`objects`, s prefiksom puta `rooms[i].` u porukama grešaka (web dodaje `roomIdx`).

**Dodjela kata (raw)** — `storyAssignments(rooms)` u `lib/decode-raw.js`, portano 1:1 iz `AppleRoomPlanJSONDecoder.storyAssignments`:
- `rooms.length <= 1` → `{ stories:[null], method:null }`.
- `sourceStories`: za svaku sobu skupi sve zapise iz `SURFACE_KINDS` + `objects`; ako svi imaju numerički `story` i svi su isti → taj broj, inače `null`. Ako su **sve** sobe non-null i `Set(sourceStories).size > 1` → `method:'source story values'`.
- Inače `floorElevation(room)` po sobi (vidi A2), pa ako je bilo koja `null` → `stories` sve `null`, `method:null`.
- Inače sortiranje po elevaciji i klasteriranje s **tolerancijom 0.8 m**: nova vrijednost je novi kat kad je `elevation - clusterMean > 0.8`; `method:'multiroom floor-elevation clustering (0.8 m tolerance)'`.

**`lib/story.js` `assignStories(model)`** je lagani pass-through: ako je `model.storyAssignmentMethod == null`, postavi `'source story field (single room / per-surface)'`; zatim `meta.storyCount` = broj različitih `story` vrijednosti preko svih `surfaces` + `objects`. Za optimized: `storyAssignmentMethod` je već `'source-provided'` (iz dekodera).

**`lib/align.js` `applyArchitecturalAlignment(model)`**:
- `kind === 'optimized'` → koristi `model.meta.alignmentTransform` (ili `identity()`), `angleRad:null`, `method:'source-provided alignment_transform'`.
- `kind === 'raw'` → `computeArchitecturalAlignment(model.surfaces.filter(s => s.kind === 'wall'))`.

**`computeArchitecturalAlignment(wallSurfaces)`** (port `RoomPlanRawProjector.architecturalAlignment(for:)`):
- Preskače zidove s `w.curve`, transform koji nije 16 konačnih brojeva, i `dimensions.x` koji nije konačan/`>0`.
- Kut zida: `angle = Math.atan2(-m[2], m[0])` (**minus** `m[2]`, ne `+m[2]`).
- Akumulira `cosine += length*cos(4*angle)`, `sine += length*sin(4*angle)` (težina = duljina zida).
- Ako `hypot(cosine,sine) <= 1e-9` → `identity()`, `method:'no-walls-found (identity alignment)'`.
- Inače `yaw = atan2(sine, cosine) / 4` (ortogonalna cirkularna sredina — rješava neodređenost od 90°).
- Ako `|yaw| <= 1e-12` → `identity()`, `method:'identity (yaw below threshold)'`.
- Inače matrica rotacije oko Y: `[c,0,s,0, 0,1,0,0, -s,0,c,0, 0,0,0,1]`, `method:'wall-length-weighted orthogonal circular mean (N wall(s) considered)'`.
- Napomena o konzistentnosti u kodu: `align.js` matrica ima predznake `[c,0,s; -s,0,c]`, dok `transform.js` `rotationY(rad)` vraća `[c,0,-s; s,0,c]` — to su međusobno transponirano/inverzno. Oba su u kodu; nisam ih međusobno provjeravao (vidi E).

**Kompozicija i raspored** (`lib/dxf-writer.js` + `transform.js`):
svaka lokalna točka → `apply(multiply(alignmentMatrix, surfaceTransform), localPoint)` → `project` → `(x, -z)`.
Ovo odgovara Swift `composed(alignment, surface.transform)` + `project(transform(p, by: matrix))`: prvo vlastita transformacija površine, zatim alignment ("composed on the left — i.e. applied after").
`align.js` izvozi i `multiply` (re-export iz `transform.js`). `assignStories` se poziva **prije** `applyArchitecturalAlignment` u `main()`, a `applyArchitecturalAlignment` **prije** `buildDXF`.

### A5. Optimized / Polycam varijanta — čime se razlikuje

Polja/obilježja koja je razlikuju (točno kako su u kodu):
- **`format_version`** — mora biti `=== 1`, inače `decode-optimized.js` baca `'Unsupported optimized RoomPlan format version ' + root.format_version`.
- **`label` / `label_automated`**: converter testira `rooms[0].label`; web `rooms[0].label_automated` (i `vertices_x`). Sama soba koristi `label_automated`.
- **`category`**: soba ima `category` kao string (raw soba ga nema); element ima `category` kao objekt ili string.
- **`area`** (soba) — precomputed površina; **`floor_height`** → `floorHeight`.
- **`meshInfo`** — javlja se samo u `detectFormat` (oboje: converter i web), **nikad se ne dekodira**.
- **`story`** — dolazi iz izvora za svaki element i sobu (default `0` ako nije broj); `storyAssignmentMethod:'source-provided'`, nema klasteriranja.
- **`alignment_transform`** — source-provided: ili polje od 16 brojeva, ili **objekt s ključevima `t00,t10,t20,t30,t01,t11,t21,t31,t02,t12,t22,t32,t03,t13,t23,t33`** (column-major, isti poredak); default `identity()`. Koristi se verbatim kao alignment.
- **`wall_thickness`** na zidovima → `wallThickness`.
- **`room.vertices_x[]` + `room.vertices_z[]`**, `room.center_xz[2]`, `room.edges`, `room.id`.
- **`latLonAlt`** `{latitude, longitude, altitude}`, **`orientation`** `{orientation_degrees, uncertainty_degrees}`, **`joints[]`** (samo `jointCount`).
- **`source`** (u testnom fixtureu `"polycam"`) — **ne čita se** u dekoderu.
- Geometry pravilo za optimized zid: **uvijek footprint** (`footprintDXF(dimensions.x, wallThickness ?? dimensions.z ?? 0.1)`).
- Raw ima `curve` i `isOpen` (vrata) i `parentIdentifier`; optimized ih ne koristi (osim `parentIdentifier` koji se samo sprema).

### A6. Rubni slučajevi, validacije i zamke koje kod izričito rješava/odbija

- **`detectFormat`** baca na nepoznat oblik (točna poruka u A1).
- **Raw validacije** (`num/nums/str/dims/points`): svaki ne-broj / ne-konačan broj / pogrešna dužina polja / prazan string → `'Malformed raw RoomPlan JSON at <path>'`. Točno: `nums(arr,count)` traži `Array` i (ako je `count` zadan) točnu dužinu; `dimensions` traži 3 broja; `transform` 16; `identifier` neprazan string.
- **`roomRecords`** baca za prazne `rooms`/`captureSessions`/`roomplanSessions` (vidi A1).
- **Optimized validacije**: `format_version !== 1` → throw; `nums/nums/str/taggedName` → `'Malformed optimized RoomPlan JSON at <path>'`; `decodeRoom` baca `'...at <path>.vertices'` ako se dužine `vertices_x` i `vertices_z` razlikuju ili je `< 3`; `center_xz` mora imati 2 broja.
- **`dxf-writer.buildDXF`**:
  - `floor` s `< 3` `polygonCorners` → **preskočen** (komentar: "Swift throws; we just skip (manifest already warns elsewhere)").
  - raw zid `dimensions.z <= 0` → centerline; manifest upozorenje `roomplan.wall-no-thickness-centerline`.
  - optimized zid: `wallThickness ?? (dimensions.z > 0 ? dimensions.z : 0.1)`.
  - `door`/`window`/`opening` → **uvijek** centerline iz `dimensions.x` (`polygonCorners` se ignorira).
  - `object` → footprint `dimensions.x × dimensions.z` (oba formata).
  - room oznaka: `{r.label}  {r.area.toFixed(2)} m2`, `height: 0.18`; sobe imaju identitet-local transform (samo alignment).
  - ako nijedna točka nije viđena → `minX=maxX=minY=maxY=0`.
- **`align.js`**: zidovi bez valjanog `transform`/duljine i zakrivljeni zidovi se ignoriraju; bez zidova → identity.
- **`dxf-emit.py`**: nepoznat tip entiteta u planu → `ValueError('Unknown entity type in plan: ...')`; nakon `doc.saveas` **round-trip** `ezdxf.readfile(out_path)` (baca ako se ne može pročitati).
- **`roomplan-to-dxf.js`**: ako `dxf-emit.py` izađe s ne-nula statusom → `throw Error('dxf-emit.py failed (exit N) — DXF not written or not AutoCAD-valid.')` (uz ispis stderr/stdout).
- **CLI**: bez `inputPath` → `Usage: node roomplan-to-dxf.js <input.json> [outDir] [--jev]`, `process.exit(1)`.
- **`--jev`** bez `TYPESAFE_API_KEY` → `'Warning: --jev requested but TYPESAFE_API_KEY is not set. Continuing without Jev triage.'`; svaki Jev failure se tiho guta (`return null`).
- **Manifest upozorenja** (`lib/manifest.js`, točni kodovi):
  - `roomplan.story-assigned-by-clustering` — raw + metoda počinje s `'multiroom floor-elevation'`.
  - `roomplan.wall-no-thickness-centerline` — raw zidovi s `dimensions.z <= 0`.
  - `roomplan.no-room-polygons-raw-format` — `!model.rooms` (raw).
  - `roomplan.compass-orientation-uncertain` — optimized + `orientationUncertaintyDegrees > 10`.
  Manifest uvijek ima `lossy: true`.
- **Poznata zamka iz `jev-review.js` (ispravljena 2026-09-22):** `jev` wrapper poštuje `--state` samo kad dođe **nakon** podnaredbe → poziva se `['--no-cache','choice',question,...options,'--state',stateText,'--compact']`.

---

## B. DXF — izlaz i format

### B1. Točne konvencije izlaza (verzija, header, jedinice, lineweight)

**Konverter (`lib/dxf-emit.py`):**
- `ezdxf.new("R2018", setup=True)` → **`$ACADVER = AC1032`** (AutoCAD 2018 / R2018). Komentar u kodu: "matches Drawing-Bridge's Swift DXFWriter exactly".
- `doc.header["$INSUNITS"] = 6` → **metri**.
- `doc.header["$LWDISPLAY"] = 1` → prikaz lineweighta (da zidovi čitaju deblje od labela).
- `setup=True` dodaje standardne tablice; u stvarnom izlazu to konkretno daje: `$LUNITS=2`, `$MEASUREMENT=1`, `$CELTSCALE/$LTSCALE`, linetype tablicu (CONTINUOUS, ByLayer, ...), text style tablicu (`Standard`, `OpenSans-Light`, `OpenSans`, `OpenSans-Light-Italic`, ...), i slojeve **`0`** i **`Defpoints`**.
- **Lineweight se postavlja na razini sloja** (`doc.layers.get(name).dxf.lineweight`), cijeli brojevi u 1/100 mm: `WALL=35`, `FLOOR=13`, `DOOR=18`, `WINDOW=18`, `OBJECT=9`, `ROOM=13`; `OPENING` i `LABEL` → default `13`. Slojevi `0`/`Defpoints` imaju lineweight `-3` (ByLayer/default).
- `$EXTMIN`/`$EXTMAX` ostaju na `1e+20` / `-1e+20` (vidi E — komentar u kodu tvrdi suprotno od snimljenog izlaza).

**Web writer (`web/dxf-export.js`, `emitDXF`):**
- **`AC1015`** (R2000) — drugačija verzija od konvertera.
- Header: samo `$ACADVER` + `$INSUNITS` (`70` = `6`).
- Ručno građen ASCII: `TABLES`/`LAYER` tablica (color + `CONTINUOUS`), prazan `BLOCKS`, pa `ENTITIES` sa subclass markerima `AcDbEntity`/`AcDbPolyline`/`AcDbLine`/`AcDbText` i **sekvencijalnim handleovima** koji počinju od `0x40` (`nextHandle()` → hex uppercase). Line za entitete ima `330` (owner) = `'0'`. **Nema lineweighta** (samo boja sloja).
- Boje slojeva (web `LAYER_COLORS`): `WALL 7, FLOOR 8, DOOR 3, WINDOW 5, OBJECT 9, ROOM 2, LABEL 2`; default `7`.

### B2. Popis layera i što ide u koji

Imenovanje (oboje): `layerFor(story, kind) = 'S' + story + '_' + String(kind).toUpperCase()`.
Kindovi koji se stvarno pojavljuju: `WALL`, `FLOOR`, `DOOR`, `WINDOW`, `OPENING`, `OBJECT`, `ROOM`, `LABEL`.
Napomena: `story` se umeće izravno — ako je `story = null` (raw single-room), dobije se npr. `Snull_WALL`.

Mapiranje entiteta → layer:
| element | layer | entitet |
|---|---|---|
| floor | `S<n>_FLOOR` | closed LWPOLYLINE (`polygonCorners`) |
| wall (footprint) | `S<n>_WALL` | closed LWPOLYLINE (footprint `dims.x × debljina`) |
| wall (bez debljine, raw) | `S<n>_WALL` | LINE (centerline `dims.x`) |
| door | `S<n>_DOOR` | LINE (centerline `dims.x`) |
| window | `S<n>_WINDOW` | LINE (centerline `dims.x`) |
| opening | `S<n>_OPENING` | LINE (centerline `dims.x`) |
| object | `S<n>_OBJECT` | closed LWPOLYLINE (footprint `dims.x × dims.z`) |
| room (optimized) | `S<n>_ROOM` | closed LWPOLYLINE (`room.vertices`) |
| label (optimized) | `S<n>_LABEL` | TEXT |

**Boje** (konverter `LAYER_COLORS` u `dxf-emit.py`): `WALL=7` (crno/bijelo), `FLOOR=8` (tamno sivo), `DOOR=3` (zeleno), `WINDOW=5` (plavo), `OBJECT=9` (svijetlo sivo), `ROOM=2` (žuto). `OPENING` i `LABEL` **nisu** u dictu → `color_for()` vraća default `7`.
Boja se određuje iz imena sloja: `kind = layer_name.split("_", 1)[-1]` (sve nakon prvog `_`); isto vrijedi za lineweight.

**Tipovi linija:** svi slojevi koriste default `CONTINUOUS` (ne postavlja se drugi tip). Web eksplicitno upisuje `CONTINUOUS`.

**Tekst:** samo room labele (optimized format). Vrijednost: `"<label>  <area.toFixed(2)> m2"` (dva razmaka), `height = 0.18`. Stil se **ne postavlja eksplicitno** → u izlazu je `Standard` (default). Pozicionira se na centar sobe (`set_placement((centerX, centerY))`); u TEXT entitetu se upisuju i `10/20` i `11/21` (alignment point). Fallback visine u `dxf-emit` je `0.1` ako `height` nije zadan (u praksi uvijek 0.18 jer `dxf-writer` uvijek šalje 0.18).

### B3. Podjela posla: `dxf-writer.js` (JSON plan) vs `dxf-emit.py` (ezdxf) — INTERFACE

`buildDXF(model)` u `lib/dxf-writer.js` vraća `{ plan, layers, entityCount }`, gdje je:
```
plan = {
  bounds:   { minX, maxX, minZ, maxZ },      // napomena: ključevi su minZ/maxZ, ali drže DXF Y vrijednosti
  layers:   [ "<ime sloja>", ... ],           // sortirano (Array.from(Set).sort())
  entities: [ <entity>, ... ]
}
```
Oblici **entity** objekata (točno kako ih `dxf-emit.py` očekuje):
- `{ type: 'polyline', layer, points: [[x,y], ...], closed: <bool> }` → `msp.add_lwpolyline(pts, close=...)`
- `{ type: 'line', layer, a: [x,y], b: [x,y] }` → `msp.add_line((a),(b))`
- `{ type: 'text', layer, pos: [x,y], height, value }` → `msp.add_text(value, dxfattribs={"height": height}).set_placement(pos)`

`roomplan-to-dxf.js` prosljeđuje **`JSON.stringify(dxfResult.plan)` na stdin** procesu `python3 lib/dxf-emit.py <izlazni.dxf>` (`spawnSync`, `encoding:'utf8'`). `dxf-emit.py` čita `json.load(sys.stdin)`, stvara slojeve iz `plan["layers"]`, pa entitete, `doc.saveas(out_path)`, i validira `ezdxf.readfile(out_path)`. Ako bilo koji entitet ima nepoznat `type` → `ValueError`.

`bounds` se u `dxf-emit.py` **ne koristi** (blok koji bi postavljao `$EXTMIN/$EXTMAX` je prazan `pass` uz komentar da ezdxf ionako preračuna/ignorira). `bounds` ipak postoji u planu (i web ga ne emitira uopće).

### B4. `docs/VERIFICATION.md` i `docs/compare_entities.py`

`docs/VERIFICATION.md` (datum 2026-09-22, referenca: `vzornjak/Drawing-Bridge` commit `f85e5da` "Support multiroom RoomPlan envelopes", buildan release na remote Macu `vzornjakm1` preko SSH/Tailscale):
- Metoda: (1) pokrenuti Node konverter i pravi Swift CLI na ista dva izvorna capturea (jedan raw Apple export s dva `roomplanSessions`, jedan Polycam Optimized s 9 soba na 2 kata); (2) učitati oba DXF-a s `ezdxf` i izvući svaki entitet kao `(type, layer, zaokružene koordinate)`; (3) sortirati identično i diffati u parovima.
- Rezultat: raw capture → Swift 56 / Node 56 entiteta, **0 geometrijskih razlika**; optimized → Swift 72 / Node 72, **0 razlika**. Oba DXF-a prolaze `ezdxf.audit.Auditor()` s 0 grešaka i poklapaju se s Swift verzijom `AC1032`.
- **Bugovi koje je verifikacija uhvatila (popravljeni prije rezultata):**
  1. **Zamjena predznaka Z-osi** — `+z` umjesto `-z` (zrcali cijeli tlocrt); otkriveno tek usporedbom numeričkih boundsa.
  2. **`polygonCorners` korišten za zidove/vrata/prozore** — Swift ga koristi **samo za podove**; zidovi/vrata/prozori/otvori uvijek footprint/centerline iz `dimensions` (+ `wallThickness`). Stari fallback davao "beskonačne" vodoravne linije.
  3. **Objekti crtani kao tekst labele umjesto footprinta.**
  4. **Dodjela kata po podnoj plohi umjesto po sobi** — Swift `storyAssignments` radi per-room; stari port klasterirao pojedinačne floor surface. Ispravljeno na per-room + 0.8 m.
  5. **Optimized `alignment_transform` krivo parsiran** — pravi Polycam ga kodira kao objekt `t00..t33` (column-major), ne ravno polje od 16 brojeva; stari parser tiho padao na `identity`.
- "When to re-run": svaka promjena `align.js`, `dxf-writer.js`, `transform.js`, `decode-raw.js`, `decode-optimized.js` mora se ponovno verificirati ovako.

`docs/compare_entities.py` (Python + ezdxf, CLI `python3 docs/compare_entities.py <swift.dxf> <mine.dxf> [--decimals 2]`, default 2 decimale):
- `entity_list(path, decimals)`: iz `modelspace` vadi `LINE` (start/end), `LWPOLYLINE` (točke) i `TEXT` (insert + tekst), zaokružuje koordinate; **skida prefikse `RP_` i `OPT_`** s imena sloja da se Swift Drawing-Bridge izlaz može direktno usporediti s ovim Node izlazom (koji koristi `S<n>_`).
- Ispisuje broj entiteta svakog; ako se brojevi razlikuju → `"ENTITY COUNT MISMATCH — cannot pair 1:1..."` i `sys.exit(1)`. Inače ispisuje broj mismatcheva i prvih 20; `exit(1)` ako ima mismatcheva, inače `0`.

### B5. Što konkretno čini DXF "AutoCAD-validnim" (samo što je dokumentirano) i zamke

Dokumentirano u kodu/docs:
- **Koristi se `ezdxf`, ne ručno pisani ASCII DXF.** Docstring `dxf-emit.py`: "see that file's docstring for why a hand-rolled ASCII DXF writer isn't safe for real AutoCAD."
- **Round-trip validacija:** nakon `doc.saveas(out_path)` odmah `ezdxf.readfile(out_path)` — "fail loudly if what we just wrote can't be re-read by a real DXF parser".
- **`ezdxf.audit.Auditor()` s 0 grešaka** (navedeno u README/VERIFICATION za oba DXF-a).
- **Verzija AC1032** identična Swift Drawing-Bridge izlazu.
- Web writer (ručno građen) ima "correct subclass markers (AcDbEntity/AcDbPolyline/AcDbLine/AcDbText) and sequential entity handles" i "audit-clean"; handleovi od `0x40`, owner `330='0'`.
- `dxf-emit` baca `ValueError` na nepoznat tip entiteta; `roomplan-to-dxf.js` baca ako exit != 0 uz poruku "...not written or not AutoCAD-valid".

Zamke koje su **dokumentirane kao stvarno nađene i popravljene** (VERIFICATION): predznak Z-osi, `polygonCorners` za zidove, objekti kao tekst, story assignment per-floor, `alignment_transform` kao objekt.

### B6. Zavisnosti i postavljanje

- **Node.js** — obični CommonJS, **bez ijedne npm zavisnosti**. `package.json` (`name: "archidrawing"`, `version: "0.5.0"`, `private: true`, `license: UNLICENSED`) **nema polja `dependencies`**. Radi u iSH (Alpine aarch64).
- **Python 3** — `roomplan-to-dxf.js` poziva `python3` preko `spawnSync` (mora biti u PATH-u).
- **`ezdxf`** — instaliran u okruženju, provjereno: **verzija 1.4.4**, Python `3.12.14` (pip paket; `apk info -e py3-ezdxf` ne vraća ništa — Alpine nativni paket nije instaliran, koristi se pip). README kaže: `pip install ezdxf`. U `dxf-emit.py` import je **lazy** (`import ezdxf` unutar `main()` nakon čitanja plana).
- `spawnSync('python3', [emitScript, dxfPath], {input: JSON.stringify(plan)})`.

---

## C. POKRETANJE

### C1. CLI sintaksa

Iz `roomplan-to-dxf.js` (docstring i `main()`):
```
node roomplan-to-dxf.js <input.json> [outDir] [--jev]
```
- `inputPath` = prvi pozicijski argument (obavezno).
- `outDir` = drugi pozicijski argument; default `path.join(path.dirname(inputPath), 'out')`.
- `--jev` = flag (filtrira se iz pozicijskih; ostali nepoznati flagovi nisu podržani).
- `--jev` pokreće trijažu upozorenja preko `jev-review.js` (samo ako je `TYPESAFE_API_KEY` postavljen; inače upozorenje).
- Bez argumenata: `Usage: ...` + exit 1.

### C2. Ulazi i izlazi (koje datoteke nastaju)

Ulaz: jedan JSON (raw ili optimized). Izlaz **u `outDir`** (kreira se `fs.mkdirSync(outDir, {recursive:true})`):
- `"<baseName>.dxf"` — gotovi DXF (`baseName = path.basename(inputPath).replace(/\.json$/i,'')`).
- `"<baseName>.roomplan.json"` — dijagnostički **manifest** (ne report u drugom smislu).
Nema trećeg izlaznog fajla. Manifest (`buildManifest`) ima ključeve:
`tool` (`'archiplan-roomplan (Node/iSH port)'`), `sourceFormat`, `sourceFilename`, `sourceSHA256`, `storyCount`, `storyAssignmentMethod`, `architecturalAlignment` (`{matrix, angleRad, method}`), `entityCount`, `layers`, `lossy: true`, `warnings[]` (`{code,message}`), `jev` (null ili trijaža).
`sourceSHA256`/`sha256(buf)` se računa u dekoderu i u `roomplan-to-dxf.js` (crypto).

stdout konvertera (točni formati):
```
Format detected: <raw|optimized>
Stories: <N> (<storyAssignmentMethod>)
Architectural alignment: <deg>° (<method>)      // ili "n/a" kad je angleRad null
DXF written: <put> (<entityCount> entities, <layers.length> layers)
Manifest written: <put> (<warnings.length> warning(s))
[Jev triage: ...]                                // samo uz --jev
```
`dxf-emit.py` na **stderr** ispisuje `"DXF written and validated: <put>"`.

### C3. Primjer stvarnog poziva

Ovo su povijesni rezultati. Izvršive assertions za oba postojeća fixturea, round-trip i audit nalaze se u kanonskom `../SKILL.md`, odjeljak Verifikacija. Pravilo `polygonCorners` samo za podove opisuje ovaj konverter, ne Appleov iOS 17+ format; `.y` je visina samo vertikalnih površina, ne podova.

U kodu/dokumentaciji postoji samo sintaksa iz README; dnevnik ne sadrži konkretan poziv. **Stvarno sam pokrenuo** konverter na oba testna fixturea (dokaz da sintaksa radi):

```
node roomplan-to-dxf.js test/test_scan.json /tmp/t1
  → Format detected: raw
  → Stories: 1 (source story field (single room / per-surface))
  → Architectural alignment: 0.00° (identity (yaw below threshold))
  → DXF written: /tmp/t1/test_scan.dxf (9 entities, 5 layers)
  → Manifest written: /tmp/t1/test_scan.roomplan.json (2 warning(s))
  (slojevi: S0_DOOR, S0_FLOOR, S0_OBJECT, S0_WALL, S0_WINDOW; 6 LINE + 3 LWPOLYLINE;
   upozorenja: roomplan.wall-no-thickness-centerline, roomplan.no-room-polygons-raw-format)

node roomplan-to-dxf.js test/optimized_2floor.json /tmp/t2
  → Format detected: optimized
  → Stories: 2 (source-provided)
  → Architectural alignment: n/a (source-provided alignment_transform)
  → DXF written: /tmp/t2/optimized_2floor.dxf (18 entities, 6 layers)
  → Manifest written: /tmp/t2/optimized_2floor.roomplan.json (0 warning(s))
  (slojevi: S0_LABEL, S0_ROOM, S0_WALL, S1_LABEL, S1_ROOM, S1_WALL; 14 LWPOLYLINE + 4 TEXT)
```
Za referencu, Swift CLI (iz VERIFICATION.md):
```
swift build -c release --product drawing-bridge
.build/release/drawing-bridge roomplan-raw-to-dxf <capture.json> out.dxf manifest.json
.build/release/drawing-bridge optimized-roomplan-to-dxf <capture.json> out.dxf manifest.json
```

### C4. Web (browser) put — nije CLI

`web/dxf-export.js` izlaže `window.convertRoomPlanToDXF(json, filename, opts)`:
- `opts.story: number|null` — ako je zadan, uključuje samo entitete tog kata, **ali alignment se računa na punom modelu** (da pojedinačni kat ostane konzistentan).
- Vraća `{ dxfText, manifest, format, model }`; manifest tool je `'archi-alpine web export (browser, no server)'`.
- Ovisi o `window.RoomPlanCore` (`roomplan-core.js`) — decode + alignment.
- Izvoz JSON i CSV (BOQ) je u `report-export.js` (CSV: hrvatski header, `;` delimiter, UTF-8 BOM; kolone uključuju `Kat, Tip, ID, Izvorni ID, Kategorija, Duzina_m, Sirina_m, Visina_m, Debljina_m, Povrsina_m2, Pouzdanost, Napomena`).

---

## D. POVIJEST I ODLUKE (iz dnevnika i git povijesti)

### D1. Zašto Node port umjesto Swift-a

- **Razlog iz koda/README:** Drawing-Bridge (privatni Swift repo `vzornjak/Drawing-Bridge`) ima pravi RoomPlan→DXF konverter, ali **builda se samo na macOS/Xcode**. `converter/` je "independent Node.js port of that same projection logic, built and run entirely on-device (iSH)" — **bez Swift/Xcode**. Docstring `roomplan-to-dxf.js`: "Pure Node.js port of Drawing-Bridge's RoomPlanRaw/OptimizedRoomPlan -> DXF path, built to run inside iSH (no Swift/Xcode required)."
- **Operativni kontekst (dnevnik 2026-09-23):** iSH Node je `--jitless`; Vite/SvelteKit build **ne radi** u iSH-u jer `es-module-lexer` treba pravi WebAssembly (`/lib/wasm-polyfill.js` pokriva samo uski llhttp slučaj). Obični Node skript poput ovog konvertera radi — arhitekturno ograničenje pogađa build toolchain, ne plain Node.
- **iSH reset (dnevnik 2026-09-23):** usred sesije nestali su `ssh`, `curl`, `git`, `python3`, `~/.ssh/` i cijeli `/var/minis/shared/` (klonovi `archi-alpine`, `openPlan3D`); vraćeni s `apk add --no-cache openssh-client python3 curl git`. Sav rad je bio siguran jer je prethodno pushan na GitHub.

### D2. Što je Drawing-Bridge

Iz dnevnika 2026-09-22: **privatni GitHub `vzornjak/Drawing-Bridge` (SwiftDWG)** — native Swift DWG-inspektor + rastući DWG→DXF (ASCII AC1032) konverter, ~21k linija Swifta (117 datoteka: `DWGKit`/`DXFKit`/`CADExchange`/`RoomPlanRaw`/`DrawingBridgeCLI`), ~70 Python skripti za verifikaciju/ledger, 39 research dokumenata. Svaki uspješan izlaz eksplicitno `lossy` — projekt namjerno nikad ne tvrdi punu vjernost. CLI ima ~30 naredbi (`inspect`, `build-neutral`, `write-dxf`, `verify-dxf`, `roomplan-raw-to-dxf`, `optimized-roomplan-to-dxf`, `convert-oda`, ...). Kod generira desetke strojno čitljivih dijagnostičkih poruka po "opaque"/"unsupported" objektu (29 jedinstvenih `dwg.*` kodova). Verifikacijska referenca je commit **`f85e5da`** "Support multiroom RoomPlan envelopes".

### D3. Što je provjereno i kako (dokazi)

1. **Build & run reference:** `swift build -c release --product drawing-bridge` na remote Macu `vzornjakm1` preko SSH/Tailscale; pokrenuti `roomplan-raw-to-dxf` / `optimized-roomplan-to-dxf` na ista dva source JSON-a.
2. **Entity-by-entity diff:** `docs/compare_entities.py` (type, layer, zaokružene koordinate) → **0 mismatches** na oba capturea (raw 56, optimized 72 entiteta).
3. **Round-trip + audit:** svaki DXF odmah `ezdxf.readfile`; `ezdxf.audit.Auditor()` 0 grešaka; `AC1032`.
4. **Web writer neovisno:** `web/dxf-export.js` (na `roomplan-core.js`) izvezen `node`-with-`window`-shim executionom stvarnog browser filea i diffan protiv istih Swift referentnih DXF-ova → 0 mismatches; dodatno click-testiran kroz pravi `index.html` UI (button → Blob → download), preuzeti bajtovi prolaze audit s 0 grešaka.
5. **Web UI end-to-end:** v0.2 report rewrite click-testiran na oba realna multi-story capturea (upload, 4 stanja story tabova, toggles, 3 export gumba; DXF brojevi entiteta 56/72 točno).
6. **Jev trijaža (dnevnik 2026-09-22):** 14 stvarnih Drawing-Bridge dijagnostičkih poruka kroz `jev choice` ("znači li ovo da će crtežu nedostajati vidljivi sadržaj") → smislen rang p=0.97 (layout/view ownership) do p=0.19 (dimension source flag bit). Zaključak: Jev kao **brzi filter/prioritizator** lossy napomena, ne zamjena za strojne provjere (SHA-256, ODA usporedbe). Tada je otkriven i popravljen bug: `jev --state` prije podnaredbe bio tiho pregazen → svi pozivi vraćali isti besmislen odgovor; ispravljeno, i zato `jev-review.js` šalje `--state` **nakon** podkomande.

### D4. Web moduli iz istog repoa (kontekst bitan za oba skilla)

- `web/roomplan-core.js` (308 linija) — dijeljeni browser decode + architectural alignment. **Razlike od konvertera:** `detectFormat` testira `label_automated`/`vertices_x` (+ `format_version===1 && walls`); model drži `format`, elemente s `roomIdx`, `storyOrigins` (za cross-story alignment); optimized `decodeRoomOptimized` koristi `category: record.category || 'Other'`, `floorHeight` opcionalan, `ceiling` umjesto `ceilingLidar*`.
- `web/dxf-export.js` (163 linije) — AC1015 ručni writer (vidi B1/B5), `convertRoomPlanToDXF` + `buildDXFPlan` (izložen za report-model).
- `web/report-model.js` (366) — unificirani per-story model (`format`, `stories[]`, `totals`, `warnings[]`); svaki wall/opening/object već nosi plan-space `(x,y)`; `assignRoomMembership()` point-in-polygon (zidovi rubom + tolerancija, namještaj centroidom) — jer nijedan format ne bilježi kojoj sobi pripada koji element.
- `web/room-inference.js` (352) — **procjena** soba (raster flood-fill, furniture-vote klasifikacija) + korekcija kosih zidova; svaka procjena `estimated:true`; za raw format jer RoomPlan ne bilježi granice soba. Kosi zid: Y-spread `polygonCorners` >5 cm i razlika od `dimensions.y` >5 cm. Optimized se ne dira.
- `web/story-alignment.js` (345) — **samo raw multi-story**, display-only: (1) shared-origin provjera `referenceOriginTransform`; (2) anchor `stairs` (mora biti točno jedan po paru katova) + yaw iz dominantnih smjerova zidova (modulo 90°, 4 kandidata), centroid samo kao seed; (3) cross-check IoU na rasteru, **prag 35%**, ispod → REJECT i fallback na neporavnato uz upozorenje. **Nikad ne dira DXF/JSON/CSV geometriju.**
- `web/plan-renderer.js` (332) — blueprint SVG; **otvori bez swing arca** (nema hinđe/strane otvaranja u podacima), prozor double-tick; `computeDisplaySnapAngle()`/`rotateStoriesForDisplay()` samo za prikaz.
- `cad-viewer.js` (386) pan/zoom/layer/inspect/measure; `layer-tree.js` hijerarhijski `Kat/Soba/Zidovi|Namjestaj|Otvori`; `workspace-store.js`+`workspace-app.js` IndexedDB knjižnica projekata; `report-export.js` JSON/CSV; `app.js`/`geometry.js`/`style.css` = **originalni v0.1 viewer**, ne linkan iz `index.html`.

### D5. Odluke koje su i danas važeće

- Geometrijska pravila "load-bearing" (README): `(x, -z)`; `polygonCorners` samo za podove; zid raw thickness→footprint else centerline; optimized zid uvijek footprint; door/window/opening uvijek centerline; object footprint; room (optimized) polyline + label; story per-room s 0.8 m klasteriranjem.
- `lossy: true` u manifestu uvijek; svaka praznina/dijagnostika ima strojni `code` + ljudsku poruku.
- DXF R2018/AC1032 + `ezdxf` round-trip + audit; `$INSUNITS=6`; lineweight po sloju (`WALL=35` najdeblji).
- **Bez swing arca / pretpostavljenog smjera otvaranja** u izvozu (RoomPlan ne bilježi hinđu).
- Verificirati s `compare_entities.py` pri svakoj promjeni `align.js`, `dxf-writer.js`, `transform.js`, `decode-raw.js`, `decode-optimized.js`.
- Cross-story alignment (web) nikad ne dira izvoz, prag IoU 35%, fail-safe filozofija ("A tool feeding BOQ/measurement numbers should fail safe, not fail quiet").

### D6. Odluke koje su nadjačane

- **Ime/rebranding:** radni naziv "archi-alpine" → **ArchiDrawing** (v0.5, commit `38c6f8a`, 2026-09-23); provjereno da "ArchiDrawing" nije registrirani trademark za softver.
- **`web` v0.1 viewer** (`app.js` + `geometry.js`) shvaćao je samo jedan raw `CapturedRoom` (`json.rooms[0]`) i pucao na oba realna capturea → **nadjačan** v0.2 rebuildom (`roomplan-core.js`/`report-model.js`/`plan-renderer.js`), commit `ea855a3` (2026-09-22).
- **Door swing arc:** dodan s orijentacijom prema najbližoj sobi u `ea855a3`, pa **potpuno uklonjen** u `ff03466` (2026-09-22) jer RoomPlan ne bilježi hinđu — "invented convention, not measured geometry". Danas vrijedi: nema arca.
- **Display snap:** `computeDisplaySnapAngle`/`rotateStoriesForDisplay` dodani (isti commit `ff03466`) jer alignment mean ostavlja ~0.7° rezidual koji na renderiranom crtežu "izgleda krivo"; **samo prikaz**, izvoz netaknut.
- **Repo je arhiviran** (commit `4806a3c`, 2026-09-27): "This repository preserves the RoomPlan/DXF conversion and viewing research; it is not the active ArchiPlan application." Aktivni projekt je **ArchiPlan** (vodič `archi.md`, grana `ux/context-toolbar`, NE pretpostavljati da je production-ready).
- **Verzija nedosljednost:** `package.json` `version: "0.5.0"`, a README ima "Status (v0.6)" i git ima commit "v0.6" (`f7f55e9`). `package.json` nije bumpan.
- **`cad-first-plan.md` (ArchiPlan, 2026-09-28)** — design checkpoint, NIJE implementirano u konverteru: prelazak na "CAD-first" (eksplicitni `Floor.cad` primitivi LINE/POLYLINE/ARC/CIRCLE, geometrija u **cm**, layer/provenance/constraints); zid iz CAD-a referencira source path/side/offset/join; RoomPlan import ostaje nepromijenjen (measured thickness, doors, windows) i **nikad se ne prepisuje tiho**. DXF plan: početi s ASCII LINE + straight LWPOLYLINE kao non-destructive underlay, selektivno promovirati; "Full AutoCAD parity is neither necessary nor currently implemented." Do milestones 2–5 "edge-reference wall drafting is a transitional convenience, not a CAD kernel."

---

## E. NEPROVJERENO

Sljedeće nisam mogao potvrditi iz koda/docs/dnevnika (izričito neprovjereno):

1. **`meshInfo`** — spominje se samo u `detectFormat` (converter i web), nikad se ne dekodira; struktura i značenje nepoznati.
2. **`$EXTMIN`/`$EXTMAX`** — komentar u `dxf-emit.py` tvrdi da ezdxf "recomputes/ignores a manually-set $EXTMIN/$EXTMAX on save", ali snimljeni izlaz ima `1e+20`/`-1e+20`. Ne mogu potvrditi da AutoCAD to ispravno preračuna na otvaranju (nije testirano u AutoCAD-u, samo ezdxf audit). Kontradikcija komentar-vs-izlaz.
3. **`transform.js rotationY()` vs matrica u `align.js`** — predznaci se razlikuju (`[c,0,-s; s,0,c]` vs `[c,0,s; -s,0,c]`); nije provjereno koja je "ispravna" niti da su ekvivalentne u upotrebi.
4. **`edges` (optimized room)** — parsira se, ali `dxf-writer` ga ne koristi; namjena nepoznata.
5. **`ceilingLidarAverageDifference`/`ceilingLidarValidFraction`/`ceiling`** — parsiraju se, nigdje se ne koriste.
6. **`parentIdentifier` "chain"** — README spominje "parentIdentifier chain", ali kod samo sprema jedno polje; ne razrješava lanac.
7. **Raw `surfaces`/`objects` na top-levelu** — `detectFormat` prihvaća `json.objects`/`json.surfaces`, ali `roomRecords` gleda samo `root.walls`/`rooms`/`captureSessions`; takav ulaz bi završio kao `[root]` s praznim surfaces. Nije testirano.
8. **`source` polje optimized formata** (`"polycam"`) — ne čita se.
9. **`meta.roomCount` (converter) vs `roomSessionCount` (web)** — nejednaka imena; nije provjereno koji se gdje očekuje.
10. **Stvarna AutoCAD kompatibilnost** — dokaz je `ezdxf.readfile` + `Auditor` (0 grešaka), **nije** otvaranje u pravom AutoCAD-u. Ne tvrditi više od toga.
11. **`jev-review.js classifyAmbiguousZone()`** — izvezen, ali ga `roomplan-to-dxf.js` **nikad ne poziva** (poziva se samo `triageWarnings`). Nije provjereno je li ikad integriran.
12. **Testni fixturei** (`test/test_scan.json`, `test/optimized_2floor.json`) su mali/sintetički; nisu isti kao "real captures" (56/72 entiteta) iz VERIFICATION.md, koji nisu u repou (samo u dnevniku).
13. **`--jev` end-to-end** — traži `TYPESAFE_API_KEY`; nisam ga pokretao (nije postavljen u ovoj sesiji dostupan? nije testirano).
14. **iSH Node `--jitless` na velikim captureima** — performanse/proizvodnost nisu mjerene; nema ograničenja u kodu.
15. **Točna boja/lineweight slojeva `OPENING` i `LABEL`** u konverteru nisu definirane u dictovima → padaju na default (`7` boja, `13` lineweight); to je zaključak iz koda, nije eksplicitno dokumentirano.
16. **`README.md` "Status (v0.5)/(v0.6)" i `package.json` 0.5.0** — ne mogu potvrditi koja je "prava" verzija.
