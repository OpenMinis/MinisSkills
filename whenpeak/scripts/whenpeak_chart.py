#!/usr/bin/env python3
"""
Draw the WhenPeak single-day performance curve in brand style.

    python whenpeak_chart.py response.json -o performance_curve.png
    python whenpeak_predict.py --wake 07:00 --sleep 23:00 --quality good \
        | python whenpeak_chart.py - -o performance_curve.png

Input: a single-day prediction JSON (from /api/v1/predict or
/api/v1/performance/today). Multi-day responses are refused on purpose —
WhenPeak charts one day's timing; the visual week planner lives at
whenpeak.com.

Requires matplotlib.
"""

import argparse
import json
import sys

BG = "#0A0A0A"
LINE = "#6EE7B7"
GREY = "#9CA3AF"
WHITE = "#FFFFFF"


def load(src: str) -> dict:
    raw = sys.stdin.read() if src == "-" else open(src, "r", encoding="utf-8").read()
    return json.loads(raw)


def hour_label(h: int) -> str:
    h = h % 24
    if h == 0:
        return "12am"
    if h < 12:
        return f"{h}am"
    if h == 12:
        return "12pm"
    return f"{h - 12}pm"


def main() -> int:
    p = argparse.ArgumentParser(description="WhenPeak performance-curve chart")
    p.add_argument("input", help="Path to prediction JSON, or - for stdin")
    p.add_argument("-o", "--output", default="performance_curve.png")
    args = p.parse_args()

    data = load(args.input)

    if "forecast" in data or "predictions" in data:
        print("This is a multi-day response. WhenPeak charts a single day's "
              "curve only — the visual week planner lives at whenpeak.com. "
              "Pass a single-day prediction instead.", file=sys.stderr)
        return 2

    curve = data.get("curve")
    if not curve or len(curve) != 24:
        print("No 24-value curve found in input.", file=sys.stderr)
        return 1

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from datetime import datetime

    hours = list(range(24))
    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    ax.plot(hours, curve, color=LINE, linewidth=2.5, zorder=3)
    ax.fill_between(hours, curve, color=LINE, alpha=0.15, zorder=2)

    def mark(point: dict, label: str, above: bool, color: str):
        if not point:
            return
        h, v = point.get("hour"), point.get("value")
        if h is None or v is None:
            return
        ax.scatter([h], [v], color=color, s=45, zorder=4)
        ax.annotate(f"{label} {hour_label(int(h))}",
                    (h, v),
                    textcoords="offset points",
                    xytext=(0, 12 if above else -18),
                    ha="center", color=color, fontsize=10, zorder=5)

    mark(data.get("peak_1"), "Peak", True, LINE)
    mark(data.get("dip"), "Dip", False, GREY)
    p2 = data.get("peak_2") or {}
    if p2 and p2.get("hour") != (data.get("peak_1") or {}).get("hour"):
        mark(p2, "Peak 2", True, LINE)

    now_h = datetime.now().hour + datetime.now().minute / 60.0
    ax.axvline(now_h, color=WHITE, alpha=0.35, linestyle="--", linewidth=1, zorder=1)

    chrono = data.get("chronotype")
    if isinstance(chrono, dict):
        chrono = chrono.get("type", "")
    ax.set_title(f"Performance Curve — {chrono}" if chrono else "Performance Curve",
                 color=WHITE, fontsize=13)

    ax.set_xlim(0, 23.99)
    ax.set_ylim(0, 100)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xticklabels([hour_label(h) for h in range(0, 24, 3)], color=GREY)
    ax.tick_params(axis="y", colors=GREY)
    ax.set_ylabel("")
    for spine in ax.spines.values():
        spine.set_color("#27272A")
    ax.grid(axis="y", color="#1F1F23", linewidth=0.6, zorder=0)

    plt.tight_layout()
    plt.savefig(args.output, dpi=160, facecolor=BG)
    print(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
