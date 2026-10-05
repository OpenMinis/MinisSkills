#!/usr/bin/env python3
"""Preflight shortcut request analyzer.

Given a natural-language request, classify route, family, likely recipes,
and what must be clarified before generation.
"""

from __future__ import annotations

import argparse
import json
from request_utils import analyze_prompt


QUESTION_BANK = {
    "trigger": {
        "question": "Where will this shortcut be started from?",
        "options": {"A": "Run manually", "B": "Run after receiving content from the share sheet", "C": "Widget, automation, or another entry point"},
    },
    "input": {
        "question": "What is the main input method?",
        "options": {"A": "Show a prompt and type manually", "B": "Read the clipboard or the current selection", "C": "Receive external input such as a URL, image, or file"},
    },
    "target": {
        "question": "Where should the content be written or output?",
        "options": {"A": "A built-in system app", "B": "A third-party app", "C": "A file, a URL, or the share sheet", "D": "Not decided yet; please recommend"},
    },
    "write_mode": {
        "question": "How should the target content be handled?",
        "options": {"A": "Create a new item or object", "B": "Write to a fixed object", "C": "Choose the object each time, then write", "D": "Recommend the most reliable option"},
    },
    "completion": {
        "question": "What should happen when it finishes?",
        "options": {"A": "End immediately", "B": "Show the result, then end", "C": "Continue to open the target, jump to a page, or run the next step", "D": "Stay on a result preview first"},
    },
    "hybrid": {
        "question": "If a pure Shortcut is unreliable, accept an alternative route?",
        "options": {"A": "Pure Shortcut only", "B": "Shortcut + URL scheme / third-party action", "C": "Shortcut + Minis / external service (Hybrid)"},
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    args = parser.parse_args()

    analysis = analyze_prompt(args.prompt)
    questions = []
    for key in analysis.missing_dimensions:
        entry = QUESTION_BANK.get(key)
        if entry:
            questions.append({"id": key, **entry})

    result = {
        "prompt": args.prompt,
        "task_family": analysis.task_family,
        "route_label": analysis.route_label,
        "recipes": analysis.recipes,
        "patterns": analysis.patterns,
        "missing_dimensions": analysis.missing_dimensions,
        "questions": questions,
        "reasons": analysis.reasons,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
