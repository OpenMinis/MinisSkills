#!/usr/bin/env python3
"""Render clarification questions + recommended flow from preflight analysis."""

from __future__ import annotations

import argparse
import json
from request_utils import analyze_prompt

QUESTION_BANK = {
    "trigger": ("Where will this shortcut be started from?", {"A": "Run manually", "B": "Run after receiving content from the share sheet", "C": "Widget, automation, or another entry point"}),
    "input": ("What is the main input method?", {"A": "Show a prompt and type manually", "B": "Read the clipboard or the current selection", "C": "Receive external input such as a URL, image, or file"}),
    "target": ("Where should the content be written or output?", {"A": "A built-in system app", "B": "A third-party app", "C": "A file, a URL, or the share sheet", "D": "Not decided yet; please recommend"}),
    "write_mode": ("How should the target content be handled?", {"A": "Create a new item or object", "B": "Write to a fixed object", "C": "Choose the object each time, then write", "D": "Recommend the most reliable option"}),
    "completion": ("What should happen when it finishes?", {"A": "End immediately", "B": "Show the result, then end", "C": "Continue to open the target, jump to a page, or run the next step", "D": "Stay on a result preview first"}),
    "hybrid": ("If a pure Shortcut is unreliable, accept an alternative route?", {"A": "Pure Shortcut only", "B": "Shortcut + URL scheme / third-party action", "C": "Shortcut + Minis / external service (Hybrid)"}),
}

ROUTE_TO_FLOW = {
    "shortcut-native": "Confirm boundaries -> plan the action chain -> generate the XML draft -> validate locally -> sign and deliver if needed",
    "shortcut-hybrid": "Confirm boundaries -> plan the Shortcut entry point and hand-off -> generate the XML draft -> validate locally -> sign and deliver if needed",
    "not-shortcut-first": "First confirm whether to run directly in Minis instead -> if still using Shortcuts, downgrade to a launcher or Hybrid entry",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    args = parser.parse_args()

    analysis = analyze_prompt(args.prompt)
    lines = []
    lines.append(f"My understanding of the flow: {ROUTE_TO_FLOW[analysis.route_label]}")
    lines.append("")

    qn = 1
    for key in analysis.missing_dimensions:
        if key not in QUESTION_BANK:
            continue
        question, options = QUESTION_BANK[key]
        lines.append(f"{qn}. {question}")
        for label, text in options.items():
            lines.append(f"• {label}: {text}")
        lines.append("")
        qn += 1

    lines.append(f"Recommended flow: {ROUTE_TO_FLOW[analysis.route_label]}")
    lines.append("Copy to confirm: fill in the options above, then proceed with the recommended flow.")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
