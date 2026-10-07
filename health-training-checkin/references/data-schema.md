# Data Schema & Check-in Form Spec

## 1. sessions.jsonl — canonical session record

One JSON object per line, one line per training session. Minimum viable record
first; add fields only when confirmed.

```json
{
  "date": "2026-09-29T18:30:00+08:00",
  "kind": "mixed",
  "goal": ["fat_loss", "health"],
  "cardio": {
    "mode": "treadmill_incline_walk",
    "duration_min": 11,
    "distance_km": 1.0,
    "active_energy_kcal": 65,
    "kcal_source": "machine",
    "notes": "5 km/h, incline 6"
  },
  "strength": [
    {
      "exercise": "smith_incline_press",
      "equipment_id": "EQ-004",
      "weight_kg": 10,
      "per_side": true,
      "sets": 3,
      "reps_per_set": [12, 12, 11],
      "rir": [3, 3, 2],
      "pain": null,
      "status": "done"
    }
  ],
  "warmup": true,
  "stretch": true,
  "notes": ""
}
```

Field notes:

| Field | Rule |
|-------|------|
| `exercise` | Stable snake_case id. Never rename ids silently — records join on it |
| `weight_kg` + `per_side` | `per_side: true` = kg loaded on **each side** (Smith/barbell). Bar weight is unknown and stays unknown |
| `reps_per_set` | List of exact per-set reps (preferred). An int means all sets equal |
| `rir` | Last set RIR is the minimum requirement; a list is per-set. If unconfirmed, omit — do not estimate |
| `pain` | `null` or short string ("left_knee_mild"). Pain ≠ RPE |
| `status` | `done` / `skipped` / `cancelled` |
| `kcal_source` | `machine` (measured) or `estimate` — required whenever `active_energy_kcal` is set |
| assist machines | Use `assistance_kg`; **lower = harder**, progression reduces it |

Legacy variants the parser tolerates but new records should avoid: `reps` as a
range string ("10-12" = unverified band), `plate_load_each_side_kg`,
`smith_bar_load_kg`, `total_added_plate_load_kg`, `estimated_rpe` (convert:
RIR ≈ 10 − RPE), and `set_details` (segment list; only the heaviest is judged).

## 2. write-ledger.jsonl — Apple Health idempotency

One line per Health write. Before writing, hash `type|date|value` and skip if
already present.

```json
{"ts": "2026-09-29T19:40:00+08:00", "type": "active_energy_kcal",
 "date": "2026-09-29", "value": 175, "source": "workout"}
```

Mapping rules:

- Active energy: machine value or labeled estimate → `activeEnergyBurned`.
- Treadmill distance → walking/running distance sample.
- Elliptical "distance" is virtual → never mapped to walking distance.

## 3. Check-in Form Spec (single page, zero typing)

Purpose: capture a workout between sets on a phone, with **no keyboard input**.

Structure:

1. **Header** — date, rotation day (D1–D4 chip), planned duration, editable
   only via taps.
2. **Cardio block** — machine chips (rotated, pre-selected), duration stepper
   (±1 min), optional distance/level steppers, "machine kcal" field.
3. **Exercise cards** (one per planned lift, in order):
   - Title + preset `weight × sets × reps` (from plan/progression prefill).
   - Per-set reps steppers (±1, long-press ±5), quick buttons ("all = preset").
   - Last-set RIR chips: 0 / 1 / 2 / 3 / 4+ ("力竭 / 剩1 / 剩2 / 剩3 / 轻松").
   - Pain toggle: ✓ / mild / sharp (sharp shows a stop warning).
   - Optional folded "form cues" section (text cues; media only if licensed).
4. **Footer** — warmup ✓, stretch ✓, notes chips (preset common phrases),
   "完成并导出" button.

Behavior:

- Autosave every change to `localStorage` under `training-checkin:<YYYY-MM-DD>`;
  restore on reopen (a session interrupted mid-workout must not be lost).
- Export = one fenced text block, stable line format:
  `exercise | weight(unit) | sets x reps(list) | RIR n | pain: none|...`
  plus cardio line and header line. Designed for copy-paste back to the agent.
- Every control must be ≥44px tap target; contrast readable in gym lighting;
  no external network requests (works offline on gym wifi-less phones).

Data flow: prefill (agent) → form (user taps) → export text → parse (agent) →
`sessions.jsonl` → Apple Health → `scripts/progression.py` → next prefill.
