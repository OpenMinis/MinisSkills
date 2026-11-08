# DXF — izrada, provjera i ograničenja

# DXF — pisanje, čitanje i provjera

## Prvo pravilo: koristi `ezdxf`, nikad ručno pisan ASCII

Ručno sastavljanje DXF teksta "izgleda jednostavno" i **nije sigurno za pravi AutoCAD**: treba točne subclass markere (`AcDbEntity`, `AcDbPolyline`, `AcDbLine`, `AcDbText`), sekvencijalne handleove, `owner` (330), i punu tablicu slojeva. Greška se ne vidi dok datoteka ne dođe u AutoCAD — dakle tiho.

```bash
apk search py3-ezdxf     # prvo provjeri trenutačni Alpine repo
# Ako je dostupan: apk add py3-ezdxf
# Ako nije, uz instaliran python3 + py3-pip:
python3 -m pip install --break-system-packages ezdxf
```

> ⚠️ **iSH reset briše pip pakete.** Nakon reseta: prvo provjeri `apk search py3-ezdxf` i preferiraj apk paket. Ako ga nema: `apk add --no-cache python3 py3-pip` → `python3 -m pip install --break-system-packages ezdxf` (svjesno zaobilazi externally-managed zaštitu; izolirani venv je sigurnija alternativa). Provjera: `python3 -c "import ezdxf; print(ezdxf.__version__)"` (bilo 1.4.4).

## Provjera valjanosti — dvije razine

```python
import ezdxf
from ezdxf import audit

doc = ezdxf.readfile("izlaz.dxf")          # round-trip: pada ako se ne može pročitati
auditor = audit.Auditor(doc)
auditor.run()
print("greške:", len(auditor.errors))      # cilj: 0
print("upozorenja:", len(auditor.fixes))
```

**Round-trip nakon svakog pisanja** — `saveas()` pa odmah `readfile()`. Ako se ne može ponovno pročitati, datoteka nije valjana, bez obzira što je `saveas` prošao bez greške.

## RoomPlan izlazne konvencije

Specijalističke verzije, slojevi, jedinice, boje/debljine, oznake soba i JSON plan→emit su u [roomplan/references/dxf-output.md](../roomplan/references/dxf-output.md). Za sken prvo učitaj [roomplan](../roomplan/SKILL.md), pretvori lokalno, zatim ovdje provjeri DXF round-trip i audit. Ne primjenjuj RoomPlan konvencije na proizvođačke ili proizvoljne DXF-ove.

## Čitanje i usporedba

```python
msp = doc.modelspace()
for e in msp:
    if e.dxftype() == "LWPOLYLINE":
        pts = [(round(p[0], 2), round(p[1], 2)) for p in e.get_points("xy")]
    elif e.dxftype() == "LINE":
        a, b = e.dxf.start, e.dxf.end
```

Za usporedbu dvaju DXF-ova (npr. protiv referentnog izlaza) koristi `compare_entities.py` — ugrađen je u skill `roomplan` (`/var/minis/skills/roomplan/scripts/compare_entities.py`): izvlači `(tip, sloj, zaokružene koordinate)`, **skida prefikse `RP_`/`OPT_`** s imena slojeva (da se Swift i Node izlaz mogu parirati 1:1) i vraća **exit 1 ako ima razlika**.

> Uvijek usporedi i **numeričke granice** (`$EXTMIN`/`$EXTMAX` ili min/max koordinate), ne samo broj entiteta. Zrcaljenje cijelog tlocrta ima isti broj entiteta i isti izgled u malom pregledu — a vidi se samo na granicama.

## Knauf i drugi referentni DXF-ovi

Katalozi detalja (npr. `W131de-*` protupožarni zidovi) su **gotovi crteži**, ne nešto što generiramo. Za njih: čitaj slojeve i entitete s `ezdxf`, ne pretvaraj ih u naš format — mjerne jedinice i konvencije slojeva su proizvođačeve i ne poklapaju se s našima.
