#!/usr/bin/env python3
"""Double-progression engine for gym strength training.

Reads a sessions.jsonl (one JSON object per training session) and suggests the
next working weight / sets / reps for each exercise, using deterministic
double-progression rules:

  * SUCCESS — every working set reaches the top of the target rep range AND
    the tightest RIR (reps in reserve) is >= 2 -> progress after 2 successes
  * DELOAD — first working set below the bottom of the range, or first-set
    RIR <= 1 (RPE >= 9) -> drop one step
  * HOLD — anything else -> keep the weight, add reps first

Usage:
  python3 progression.py sessions.jsonl                   # all exercises
  python3 progression.py sessions.jsonl --exercise squat  # one exercise
  python3 progression.py sessions.jsonl --json            # machine readable
  python3 progression.py sessions.jsonl --inc 2.5         # step size in kg

Canonical strength entry (write new records like this):
  {"date": "2026-09-29T18:30:00+08:00",
   "strength": [
     {"exercise": "smith_squat", "weight_kg": 15, "per_side": true,
      "sets": 2, "reps_per_set": [10, 10], "rir": [3, 2]}
   ]}

Tolerated legacy variants (parsed, never guessed):
  - reps_per_set as a range string ("10-12") or the `reps` field ->
    judged conservatively and flagged unverified
  - weight via plate_load_each_side_kg (per side), smith_bar_load_kg,
    total_added_plate_load_kg, or assistance_kg (assist machines: lower
    assist = harder; progression there should DECREASE the number)
  - RIR via estimated_rpe (RIR ~= 10 - RPE) or a bare `rir` int
  - set_details: list of segments; only the heaviest segment is judged
  - entries with status "skipped"/"cancelled" are ignored

Bar weight is never guessed: Smith machine loads are recorded per side and
suggestions are printed as kg/side.
"""

import argparse
import json
import sys
from collections import OrderedDict

DEFAULT_RANGE = (8, 12)        # compound lifts
ACCESSORY_RANGE = (12, 15)     # isolation / small muscles
ACCESSORY_KEYWORDS = (
    "lateral", "raise", "curl", "pushdown", "extension", "fly",
    "reverse", "abduction", "adduction", "calf", "pallof", "crunch",
)
SKIP_STATUS = ("skipped", "cancelled", "canceled", "not_done")


# ---------- tolerant field parsing ----------

def parse_reps(entry):
    """Return (exact_list|None, lo, hi, verified)."""
    v = entry.get("reps_per_set", entry.get("reps"))
    if v is None:
        return None, None, None, False
    items = v if isinstance(v, list) else [v]
    exact, los, his, verified = [], [], [], True
    for item in items:
        if isinstance(item, bool):
            verified = False
            continue
        if isinstance(item, (int, float)):
            exact.append(int(item))
            los.append(int(item))
            his.append(int(item))
            continue
        s = str(item).strip().replace("—", "-").replace("~", "-")
        if "-" in s:
            a, _, b = s.partition("-")
            try:
                los.append(int(float(a)))
                his.append(int(float(b)))
            except ValueError:
                verified = False
        else:
            try:
                n = int(float(s))
                exact.append(n)
                los.append(n)
                his.append(n)
            except ValueError:
                verified = False
        verified = False if s.count("-") == 1 and s.replace("-", "").replace(".", "").isdigit() else verified
    if not los:
        return None, None, None, False
    lo, hi = min(los), max(his)
    return (exact if verified else None), lo, hi, verified


def parse_weight(entry):
    """Return (weight|None, per_side, source)."""
    if entry.get("weight_kg") is not None and not isinstance(entry.get("weight_kg"), str):
        return float(entry["weight_kg"]), bool(entry.get("per_side")), "weight_kg"
    for key, per_side in (("plate_load_each_side_kg", True),
                          ("smith_bar_load_kg", False),
                          ("total_added_plate_load_kg", False),
                          ("assistance_kg", False)):
        v = entry.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v), per_side, key
    return None, False, None


def parse_rir(entry):
    """Return (tightest_rir|None, source). Never invents a value."""
    for key in ("rir", "rir_per_set"):
        v = entry.get(key)
        if v is None:
            continue
        items = v if isinstance(v, list) else [v]
        nums = [int(x) for x in items if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if nums:
            return min(nums), key
    rpe = entry.get("estimated_rpe")
    if rpe is not None:
        s = str(rpe).strip().lstrip("<=>").strip()
        try:
            return 10 - int(float(s)), f"estimated_rpe={rpe}"
        except ValueError:
            pass
    return None, None


# ---------- judgement ----------

def load_sessions(path):
    sessions = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                sessions.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"warn: line {lineno} skipped ({e})", file=sys.stderr)
    return sessions


def target_range(exercise):
    key = exercise.lower()
    return ACCESSORY_RANGE if any(k in key for k in ACCESSORY_KEYWORDS) else DEFAULT_RANGE


def expand_segments(entry):
    segs = entry.get("set_details")
    if isinstance(segs, list) and segs:
        out = []
        for seg in segs:
            if isinstance(seg, dict):
                merged = dict(entry)
                merged.update(seg)
                out.append(merged)
        return out or [entry]
    return [entry]


def collect_performances(sessions, exercise):
    perfs = []
    for s in sessions:
        if str(s.get("status", "")).lower() in SKIP_STATUS:
            continue
        segs = []
        for e in s.get("strength", []):
            if e.get("exercise") == exercise:
                segs.extend(expand_segments(e))
        judged = [x for x in segs if parse_weight(x)[0] is not None]
        if not judged:
            continue
        judged.sort(key=lambda x: parse_weight(x)[0], reverse=True)
        main = judged[0]
        w, per_side, src = parse_weight(main)
        exact, lo, hi, verified = parse_reps(main)
        n_sets = main.get("sets")
        if isinstance(n_sets, list):
            n_sets = len(n_sets)
        rir, rir_src = parse_rir(main)
        perfs.append({
            "date": str(s.get("date", "?"))[:10],
            "weight_kg": w,
            "per_side": per_side,
            "weight_source": src,
            "sets": n_sets,
            "reps_exact": exact,
            "reps_lo": lo,
            "reps_hi": hi,
            "reps_verified": verified,
            "tightest_rir": rir,
            "rir_source": rir_src,
        })
    perfs.sort(key=lambda p: p["date"])
    return perfs


def judge(perf, lo, hi):
    """Return (verdict, reason). verdict in {success, deload, hold}."""
    rlo, rhi = perf["reps_lo"], perf["reps_hi"]
    if rlo is None:
        return "hold", "no reps recorded"
    tightest = perf["tightest_rir"]
    first_ok = rlo >= lo
    all_top = rhi >= hi if not perf["reps_verified"] else all(r >= hi for r in perf["reps_exact"])
    if not first_ok or (tightest is not None and tightest <= 1 and not all_top):
        why = "first work below range" if not first_ok else "RIR<=1 on first work (RPE>=9)"
        return "deload", why
    if all_top and (tightest is None or tightest >= 2):
        note = "" if perf["reps_verified"] else " (reps recorded as range)"
        return "success", f"all sets reached {hi}+ reps{note}"
    return "hold", "in range — add reps first"


def suggest(perfs, lo, hi, inc):
    if not perfs:
        return None, "no-data", "not trained in this log"
    verdicts = [judge(p, lo, hi) for p in perfs[-2:]]
    last = perfs[-1]
    unit = "kg/side" if last["per_side"] else "kg"
    w = last["weight_kg"]
    if last["weight_source"] == "assistance_kg":
        if verdicts[-1][0] == "success":
            return w - inc, "progress", f"assist machine: reduce assistance by {inc}"
        return w, "hold", "assist machine: reduce assistance when all sets top the range"
    if len(verdicts) == 2 and all(v == "success" for v in verdicts):
        return w + inc, "progress", f"2 consecutive successes at {w} {unit}"
    if verdicts[-1][0] == "deload":
        return max(0.0, w - inc), "deload", verdicts[-1][1]
    if verdicts[-1][0] == "success":
        return w, "hold", f"one success at {w} {unit} — repeat to confirm"
    return w, "hold", f"{verdicts[-1][1]} at {w} {unit}"


def main():
    ap = argparse.ArgumentParser(description="Double-progression suggestions from sessions.jsonl")
    ap.add_argument("sessions", help="path to sessions.jsonl")
    ap.add_argument("--exercise", help="only judge this exercise id")
    ap.add_argument("--inc", type=float, default=2.5, help="step size in kg (default 2.5)")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args()

    sessions = load_sessions(args.sessions)
    exercises = OrderedDict()
    for s in sessions:
        for e in s.get("strength", []):
            if e.get("exercise"):
                exercises.setdefault(e["exercise"], None)
    if args.exercise:
        if args.exercise not in exercises:
            sys.exit(f"exercise '{args.exercise}' not found in {args.sessions}")
        exercises = OrderedDict([(args.exercise, None)])

    rows = []
    for ex in exercises:
        perfs = collect_performances(sessions, ex)
        lo, hi = target_range(ex)
        nxt, status, detail = suggest(perfs, lo, hi, args.inc)
        rows.append({
            "exercise": ex,
            "target_reps": f"{lo}-{hi}",
            "sessions": len(perfs),
            "last": perfs[-1] if perfs else None,
            "next_weight_kg": nxt,
            "status": status,
            "detail": detail,
        })

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    for r in rows:
        last = r["last"] or {}
        unit = "kg/side" if last.get("per_side") else "kg"
        reps = (last.get("reps_exact") or
                (f"{last.get('reps_lo')}-{last.get('reps_hi')}" if last.get("reps_lo") else "?"))
        rir = last.get("tightest_rir")
        print(f"{r['exercise']:<28} target {r['target_reps']:>5} | "
              f"{r['sessions']:>2} sessions | last {last.get('weight_kg', '?')}{unit} "
              f"x {reps} RIR{rir if rir is not None else '-'}")
        print(f"{'':<28} -> next: {r['next_weight_kg']} {unit} [{r['status']}] {r['detail']}")


if __name__ == "__main__":
    main()
