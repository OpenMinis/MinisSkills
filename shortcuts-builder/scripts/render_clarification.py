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

# Recommended option per question: used as the `user_ask` default, i.e. what to proceed with on timeout.
# Chosen as the most reliable / least surprising route, never as something irreversible.
DEFAULT_OPTION = {"trigger": "A", "input": "A", "target": "D", "write_mode": "D", "completion": "B", "hybrid": "B"}
HEADERS = {"trigger": "Entry", "input": "Input", "target": "Target", "write_mode": "Write mode", "completion": "Finish", "hybrid": "Route"}

# Short card labels (<= 12 chars) per option; the full wording goes into `description`.
SHORT = {
    "trigger": {"A": "Manual", "B": "Share sheet", "C": "Other entry"},
    "input": {"A": "Ask me", "B": "Clipboard", "C": "External"},
    "target": {"A": "System app", "B": "Third-party", "C": "File / URL", "D": "You pick"},
    "write_mode": {"A": "New item", "B": "Fixed item", "C": "Choose each", "D": "You pick"},
    "completion": {"A": "End", "B": "Show result", "C": "Continue", "D": "Preview"},
    "hybrid": {"A": "Shortcut only", "B": "URL / app", "C": "With Minis"},
}

ROUTE_TO_FLOW = {
    "shortcut-native": "Confirm boundaries -> plan the action chain -> generate the XML draft -> validate locally -> sign and deliver if needed",
    "shortcut-hybrid": "Confirm boundaries -> plan the Shortcut entry point and hand-off -> generate the XML draft -> validate locally -> sign and deliver if needed",
    "not-shortcut-first": "First confirm whether to run directly in Minis instead -> if still using Shortcuts, downgrade to a launcher or Hybrid entry",
}


def build_user_ask(missing: list[str]) -> list[dict]:
    """Questions in the `user_ask` tool shape. One call takes at most 4 questions; the caller
    splits longer lists. `default` is the 0-based index of the recommended option."""
    out = []
    for key in missing:
        if key not in QUESTION_BANK:
            continue
        question, options = QUESTION_BANK[key]
        labels = list(options)
        rec = DEFAULT_OPTION.get(key, labels[0])
        ordered = [rec] + [x for x in labels if x != rec]  # recommended first: the card marks the first one
        out.append({
            "type": "options",
            "header": HEADERS.get(key, key)[:12],
            "question": question,
            "options": [{"label": SHORT.get(key, {}).get(x, options[x][:12]), "description": options[x]} for x in ordered[:4]],
            "default": "0",
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--json", action="store_true",
                        help="emit `user_ask` questions (recommended option first and set as default)")
    args = parser.parse_args()

    analysis = analyze_prompt(args.prompt)
    if args.json:
        qs = build_user_ask(analysis.missing_dimensions)
        print(json.dumps({"route": analysis.route_label, "flow": ROUTE_TO_FLOW[analysis.route_label],
                          "batches": [qs[i:i + 4] for i in range(0, len(qs), 4)]}, ensure_ascii=False, indent=2))
        return 0
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
