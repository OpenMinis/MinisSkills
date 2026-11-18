# RoomPlan → DXF: specijalistički izlaz

Kanonska referenca za izlaz ugrađenog [RoomPlan convertera](../SKILL.md). Opći DXF format, ezdxf i audit ostaju u [dxf](../../dxf/SKILL.md). Ovo nije specifikacija Apple JSON-a niti uputa za spajanje ArchiPlan web importera s exporterom.

## Geometrija po elementu — pravila

| Element | Kako se crta |
|---|---|
| floor | zatvorena polilinija iz `polygonCorners` (preskočen ako ih je < 3) |
| wall (raw, `z > 0`) | footprint `dužina × debljina` |
| wall (raw, `z <= 0`) | **centerline** — nema izmjerenu debljinu |
| wall (optimized) | **uvijek footprint**: zadani opis `wall_thickness ?? dimensions.z ?? 0.1`; precizna implementacija: `wallThickness != null ? wallThickness : (dimensions.z > 0 ? dimensions.z : 0.1)` |
| door / window / opening | **uvijek centerline** iz `dimensions.x` |
| object (namještaj) | pravokutnik `x × z` (nema `polygonCorners`) |
| room (optimized) | polilinija iz `vertices_x/vertices_z` + tekstualna oznaka |

Koordinate ostaju lokalne do projekcije: prvo lokalni `surface.transform`, zatim poravnanje, pa **`(x, y) = (x, -z)`**. Minus na Z ne smije se izgubiti. Zidovni poligoni i zakrivljenosti nisu potpuno sačuvani; manifest ostaje `lossy:true`, s upozorenjima i `sourceSHA256`. Raw/optimized, katovi i izvorne transformacije detaljno su u RoomPlan skillu.

## Konvencije u našim izlazima (RoomPlan converter)

| | Konverter (Node + ezdxf) | Web writer |
|---|---|---|
| Verzija | `ezdxf.new("R2018", setup=True)` → **AC1032** | **AC1015** (R2000) |
| Mjerne jedinice | `$INSUNITS = 6` (metri) | isto |
| Lineweight | `$LWDISPLAY = 1`, po sloju | **nema** |
| Slojevi | `S<n>_<KIND>` | isto |
| Validacija | round-trip + audit | audit |

**Dva različita writeera u istom repou daju različite formate** — ne pretpostavljaj koji je korišten, provjeri `$ACADVER`. Web stupac je dokumentirani povijesni kontrast, ne nova provjera drugog proizvoda.

### Slojevi

Ime: **`S<kat>_<TIP>`** (npr. `S0_WALL`, `S1_LABEL`). Tipovi: `WALL`, `FLOOR`, `DOOR`, `WINDOW`, `OPENING`, `OBJECT`, `ROOM`, `LABEL`.

> Kat se umeće izravno. Ranija tvrdnja „raw single-room daje `Snull_WALL`” vrijedi **samo kad površina nema numerički `story`**. Single-room zadržava per-element `story` ako postoji, pa numerički `0` daje `S0_WALL`. Provjereno u `decode-raw.js` (`storyAssignments`, `decodeSurface`) i `dxf-writer.js` (`layerFor`); `Snull_*` nije automatski bug niti univerzalni izlaz svake jednokatne snimke.

| Tip | Boja | Lineweight (1/100 mm) |
|---|---|---|
| WALL | 7 | 35 |
| FLOOR | 8 | 13 |
| DOOR | 3 (zeleno) | 35 |
| WINDOW | 5 (plavo) | 35 |
| OPENING | 6 (magenta) | 35 |
| OBJECT | 9 | 9 |
| ROOM | 2 | 13 |
| LABEL | 7 (default) | 13 (default) |

Boja i lineweight se u konverteru izvode **iz imena sloja** (`split("_", 1)[-1]`), pa neispravno ime sloja tiho daje default. Lineweight se upisuje u samu tablicu slojeva (`layer.dxf.lineweight`) — ranija inačica je pisala običan atribut i svi su slojevi završavali na `-3` (ByLayer).

### Redoslijed crtanja: otvori iznad zidova (od 2026-11-08)

DXF u *model spaceu* nema z-red (osim tablice `SORTENTS`, koju ne pišemo), pa preglednici crtaju entityje **redom iz datoteke** i kasniji pokriva raniji. Vrata/prozor/otvor je **jedna tanka središnja linija koja leži NA zidnom footprintu**, pa bi je zid upisan poslije prekrio i tlocrt bi izgledao kao kutija bez otvora. Zato:

- `lib/dxf-writer.js` na kraju `buildDXF` **stabilno sortira** `plan.entities` po `DRAW_ORDER`: `FLOOR 10`, `WALL 20`, `ROOM 30`, `OBJECT 40`, `DOOR/WINDOW/OPENING 50`, `LABEL 60`, `CEILING* 70` (nepoznato: 60 za tekst, inače 65). Redoslijed iz dekodera ostaje nepromijenjen unutar iste razine.
- `lib/dxf-emit.py` primjenjuje **istu tablicu** (`DRAW_ORDER`) prije pisanja, pa i stariji ili ručno složen plan izlazi s otvorima na vrhu. Izvješće emita nosi `drawOrder.openingsAboveWalls`, `firstOpeningIndex`, `lastWallIndex` i `openingColors` (boja po sloju otvora).
- Svi otvori imaju lineweight **35** (isti kao zid), da obojana linija prekrije cijelu debljinu zida, a ne pola; boja ih razlikuje (3/5/6). `OPENING` više ne pada na default 7 — prije je bio bijel kao zid i vizualno nestajao.


### Tekst

Samo oznake soba (optimized format): `"<label>  <area.toFixed(2)> m2"` (dva razmaka), visina **0,18**, stil `Standard` (ne postavlja se eksplicitno).

## Interface prema ezdxf-u

Ako pišeš vlastiti emit korak, najsigurnije je razdvojiti **plan** (JSON, čista geometrija) od **emita**:

```
{ "layers": ["S0_WALL", ...],
  "entities": [
    {"type":"polyline","layer":"S0_WALL","points":[[x,y],...],"closed":true},
    {"type":"line","layer":"S0_DOOR","a":[x,y],"b":[x,y]},
    {"type":"text","layer":"S0_LABEL","pos":[x,y],"height":0.18,"value":"..."} ] }
```

Emit: `add_lwpolyline(pts, close=...)` / `add_line` / `add_text(value, dxfattribs={"height": height}).set_placement(pos)`. Nepoznat tip entiteta → **baci grešku**, ne preskoči tiho.

> `$EXTMIN`/`$EXTMAX` ostaju na `±1e20` u našem izlazu — ezdxf ih sam preračuna. Ne postavljaj ih ručno. Pri usporedbi koristi i stvarne min/max koordinate entiteta, ne oslanjaj se na placeholder granice zaglavlja.

## Provjera izlaza

Nakon pretvorbe pokreni round-trip i `ezdxf.audit`, provjeri verziju, jedinice, slojeve i entity count prema manifestu, `lossy:true`, upozorenja i SHA256 izvora. Samostalne sintetičke provjere opisuje [README](../README.md); opće audit upute su u [Verification guidance](VERIFICATION.md). Broj entiteta nije geometrijska jednakost: usporedi numeričke granice i koordinate uz izričitu projekciju plana `(x, -z)`. Ne uključuj `--jev` u lokalne regresije.

### Više katova (od 2026-11-07)

`plan` sada nosi i `stories[]` (`story`, `entityCount`, `bounds` u lokalnim
koordinatama, `layers`) i `multiSheet`. `dxf-emit.py` tada crta **jedan okvir po
katu**, lijevo→desno uzlazno po broju kata, s razmakom `FRAME_GAP_RATIO` (8 %
najšireg okvira) i zajedničkom donjom linijom; entiteti se samo translatiraju
(`dx`, `dy` po katu), nikad ne skaliraju ni rotiraju. Svaki okvir dobiva svoj
title block (red `Kat`) i svoju strelicu sjevera. `--no-frame` ostaje jedan
zajednički crtež i emitira upozorenje `roomplan.stories-not-separated`.

## Sloj stropnih anotacija

`S<n>_CEILING` postoji po defaultu (`--no-ceilings` ga isključuje). Boja ACI 30 / truecolor
`0xFF8000`, linija `CEILING_DASHED` (0,08 m crtica / 0,04 m praznina),
lineweight 9. Nije konstrukcijska geometrija i ne sudjeluje u količinama;
vidi [heights-ceilings.md](heights-ceilings.md).
