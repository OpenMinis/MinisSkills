---
name: health-training-checkin
description: >
  Gym strength-training closed loop: plan the session from real history, generate
  a zero-typing check-in form, parse the workout back into structured records,
  suggest the next weight via deterministic double progression, and write workout
  data to Apple Health. Trigger on: planning a gym session ("今天练什么/练哪天",
  "安排今天的训练"), logging a workout ("记录训练/记一下今天的训练", "log my workout",
  "training check-in"), weight progression questions ("该加重量了吗", "下次用什么重量",
  "increase weight?"), parsing exported training text or screenshots into records,
  periodic training review ("这周训练怎么样", "training review", deload questions),
  and writing workouts/calories to Apple Health ("写入健康", "log workout to Health").
  Also trigger when the user describes a completed workout in text or voice and
  wants it saved. Not for exercise form advice alone, non-gym sports tracking,
  or one-off calorie estimates without recording.
compatibility: python3 (stdlib only)
---

# Health Training Check-In

A closed loop for gym strength training: **history-driven plan → zero-typing
check-in → structured records → deterministic weight progression → Apple Health**.

The value is not the training plan content (that is commodity); it is the loop
that makes the plan *alive*: every session updates the next session's numbers.

## The Loop (run in this order)

```
setup (once)  →  prefill (before session)  →  check-in form  →  user fills & exports
     →  parse export  →  append sessions.jsonl  →  write Apple Health
     →  progression suggestion  →  (periodically) review & plan update
```

## 1. Setup (first run only)

Create a training directory (e.g. `shared/health-training/`) with:

| File | Purpose |
|------|---------|
| `equipment-catalog.md` | Gym machines the user actually has (id, name, photo ref) |
| `training-plan.md` | Versioned plan: rotation days, exercises, target sets/reps, baseline weights, rules |
| `sessions.jsonl` | One JSON object per session (see `references/data-schema.md`) |
| `write-ledger.jsonl` | Idempotency ledger for Apple Health writes (type+date+value hash) |

Ask the user for: goal (fat loss / muscle / health), weekly availability, any
pain/injury limits, and their gym's machines (photos optional but useful).
Seed the first plan conservatively: unknown weights are tested, not guessed.

## 2. Prefill (before each session)

Read `training-plan.md` + `sessions.jsonl` + `equipment-catalog.md`, then decide
today's default and prefill everything the user would otherwise type:

- **Which day**: rolling rotation (e.g. D1 squat / D2 push / D3 pull / D4 hip
  hinge) — continue in order, never "make up" skipped days.
- **Weights/sets/reps**: from plan baselines + `scripts/progression.py` output.
- **Cardio**: mode, duration, machine (rotate machines; never the same one 3x in a row).
- **Recovery guardrails**: same muscle group ≥48h apart; any rolling 7 days
  capped (default 3–4 strength sessions); 2 consecutive training days → prefer
  rest or low-intensity walk; pain/sleep-debt → reduce, don't push.

## 3. Check-in Form (zero typing)

Generate a single-page HTML form (spec in `references/data-schema.md`, working
skeleton in `assets/checkin-template.html`) and open it via `minis-open`.

Requirements: all inputs are taps/clicks (steppers, chips, quick buttons) — no
keyboard needed during a workout; each exercise card shows preset weight × sets
× reps and captures per-set actual reps + last-set RIR + pain flag; autosaves to
localStorage (survives refresh, keyed by date); exports one copy-paste text
block. Keep it one page — the user is between sets, not at a desk.

## 4. Parse the Export → sessions.jsonl

Parse the exported text back into the canonical schema (see
`references/data-schema.md`). Rules:

- **Unknown stays unknown.** Never infer reps/weights the user did not confirm.
- If the export conflicts with the prefill, the user's numbers win.
- Ranges recorded as strings ("10-12") stay unverified — the engine treats
  them conservatively.
- Smith machine loads are per-side plates; bar weight is **never** guessed.
- Append one JSON line per session; keep `date`, `kind`, `cardio`, `strength`.

## 5. Apple Health Write

Use `apple-healthkit`. Respect the write-ledger for idempotency (skip if the
same type+date+value was already written).

- Active energy: machine-reported kcal when available (note "machine measured"),
  otherwise estimate from duration + intensity and **label it as an estimate**.
- Treadmill distance → walking/running distance; elliptical "distance" is
  virtual — do NOT map it to walking distance.
- Do not chase write types the user lacks permission for; active energy is
  enough.

## 6. Progression (the core value)

Run `scripts/progression.py sessions.jsonl` and explain the suggestion in one
sentence (rule + evidence). Double progression rules (deterministic — code,
not vibes):

- Target rep range (compound 8–12, accessory 12–15).
- **Progress**: all sets reach the range top AND last-set RIR ≥ 2, twice in a
  row at the same weight → add one step (default 2.5 kg; per-side on Smith).
- **Deload**: first work below the range bottom, or RIR ≤ 1 (RPE ≥ 9) → drop
  one step.
- **Hold**: otherwise → same weight, add reps first.
- Back-off structure is allowed (heavy sets + lighter back-off); only the
  heaviest segment is judged.
- Assist machines (pull-up/dip assist) progress by *reducing* assistance.

## 7. Periodic Review (weekly / every 4–6 weeks)

- Training density vs the cap; same-muscle spacing; pain trends; progression
  stalls (same weight >3 sessions).
- Every 4–6 weeks: update baselines in `training-plan.md`, bump its version,
  and keep a one-paragraph changelog (what changed and why — evidence-based).
- Include a deload week (cut working sets 30–40%, keep weights) at week 6.

## Pitfalls (learned the hard way)

- **Pain is not a training signal.** Sharp pain / chest pain / dizziness /
  unusual breathlessness → stop immediately; soreness → reduce, don't skip
  recording.
- Don't let the plan drift into "whatever machine is free" — plan from the
  equipment catalog.
- Don't add exercises just because they exist; fix the main lifts first.
- Record per-set reps, not just totals — progression rules need them.
- Estimated calories must be labeled as estimates when written to Health.
- Exercise GIFs: do NOT bundle copyrighted demo media (e.g. commercial
  datasets) in a distributed skill — use text cues or user-provided media.

## Validation

- After parsing, re-read the appended line and diff it against the export text
  (weights × sets × reps must match exactly).
- Sanity-check `progression.py` output against the user's known state before
  presenting it; if the log looks inconsistent (renamed exercise ids, mixed
  legacy fields), say so instead of silently suggesting.
