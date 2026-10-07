#!/usr/bin/env python3
"""Find golden shortcuts most similar to a given action list or pattern list.

Usage:
  python3 scripts/match_golden.py --actions "is.workflow.actions.ask,is.workflow.actions.text.replace"
  python3 scripts/match_golden.py --patterns "ask_text,text_replace,clipboard_out"
  python3 scripts/match_golden.py --actions "..." --patterns "..." --top 3

Returns top-N matches ranked by Jaccard similarity of action sets and/or pattern sets.
"""

import argparse
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = SKILL_ROOT / "golden-shortcuts" / "index.jsonl"


def jaccard(set_a, set_b):
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def main():
    parser = argparse.ArgumentParser(description="Match golden shortcuts by similarity")
    parser.add_argument("--actions", type=str, default="",
                        help="Comma-separated action identifiers")
    parser.add_argument("--patterns", type=str, default="",
                        help="Comma-separated pattern names")
    parser.add_argument("--top", type=int, default=3,
                        help="Number of top matches to return")
    args = parser.parse_args()

    query_actions = set(a.strip() for a in args.actions.split(",") if a.strip())
    query_patterns = set(p.strip() for p in args.patterns.split(",") if p.strip())

    if not query_actions and not query_patterns:
        print("Error: provide --actions and/or --patterns", file=sys.stderr)
        sys.exit(1)

    entries = []
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    scored = []
    for entry in entries:
        entry_actions = set(entry.get("actions", []))
        entry_patterns = set(entry.get("patterns", []))

        score = 0.0
        components = 0
        if query_actions:
            score += jaccard(query_actions, entry_actions) * 0.6
            components += 1
        if query_patterns:
            score += jaccard(query_patterns, entry_patterns) * 0.4
            components += 1

        # Bonus: how many of the query actions are covered
        if query_actions and entry_actions:
            coverage = len(query_actions & entry_actions) / len(query_actions)
            score += coverage * 0.2

        scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, entry in scored[:args.top]:
        if score <= 0:
            continue
        results.append({
            "score": round(score, 3),
            "title": entry.get("title", ""),
            "id": entry.get("id", ""),
            "category": entry.get("category", ""),
            "purpose": entry.get("purpose", ""),
            "xml": entry.get("xml", ""),
            "matched_actions": sorted(set(entry.get("actions", [])) & query_actions) if query_actions else [],
            "matched_patterns": sorted(set(entry.get("patterns", [])) & query_patterns) if query_patterns else [],
            "wiring_highlights": entry.get("wiring_highlights", []),
        })

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
