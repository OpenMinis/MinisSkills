#!/usr/bin/env python3
"""
find_node.py — Smart UI element location for Android Accessibility.

Wraps `android-a11y-cli ui dump` and returns the best-matching node(s) for a
query. Unlike a raw "tap by exact text", this script:

  * decodes the JSON envelope and flattens the node tree;
  * scores every node by how well it matches on text OR contentDescription,
    both exact and fuzzy (substring), with clickable nodes preferred;
  * supports regex matching;
  * returns ranked candidates so the caller can verify before acting.

This is the layer that turns a brittle "find this button" into a robust
"find the most likely button" — essential for apps that label UI inconsistently.
"""

import argparse
import json
import re
import subprocess
import sys


def dump_tree() -> list:
    """Call android-a11y-cli ui dump and return the node list."""
    proc = subprocess.run(
        ["android-a11y-cli", "ui", "dump", "--compact"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"android-a11y-cli dump failed: {proc.stderr.strip()}")
    payload = proc.stdout
    # The CLI may print a "proot info" line before the JSON. Jump to first '{'.
    start = payload.find("{")
    if start == -1:
        raise RuntimeError("android-a11y-cli returned no JSON")
    try:
        data = json.loads(payload[start:])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"android-a11y-cli returned invalid JSON: {e}")
    if not data.get("ok"):
        raise RuntimeError(data.get("error", {}).get("message", "dump failed"))
    return data["data"].get("nodes", [])


def node_text(node: dict) -> str:
    """Join text and contentDescription for matching."""
    parts = []
    for key in ("text", "contentDesc"):
        val = node.get(key)
        if val and val.strip():
            parts.append(val.strip())
    return " ".join(parts)


def score_node(node: dict, query_lower: str, regex) -> int:
    """Return a heuristic score; higher == better match."""
    txt = node_text(node).lower()
    if not txt:
        return -1

    score = 0
    if regex:
        if regex.search(txt):
            score += 100
        else:
            return -1
    else:
        if txt == query_lower:
            score += 100  # exact
        elif query_lower in txt:
            score += 60   # substring
        elif txt in query_lower:
            score += 30   # node is a fragment of the query
        else:
            return -1

    # Clickable nodes are what we want to act on — boost them.
    if node.get("clickable"):
        score += 10
    return score


def find(query: str, use_regex: bool = False, top_k: int = 5,
         must_be_clickable: bool = False):
    """Return ranked node candidates matching the query."""
    query_lower = query.lower()
    regex = re.compile(query) if use_regex else None

    nodes = dump_tree()
    scored = []
    for node in nodes:
        s = score_node(node, query_lower, regex)
        if s < 0:
            continue
        if must_be_clickable and not node.get("clickable"):
            continue
        scored.append((s, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "score": s,
            "nodeId": n.get("nodeId"),
            "center": n.get("center"),
            "clickable": n.get("clickable"),
            "text": n.get("text") or "",
            "contentDesc": n.get("contentDesc") or "",
        }
        for s, n in scored[:top_k]
    ]


def main():
    p = argparse.ArgumentParser(description="Locate a UI node by fuzzy match.")
    p.add_argument("query", help="Text or contentDescription to match")
    p.add_argument("--regex", action="store_true", help="Treat query as regex")
    p.add_argument("--top", type=int, default=5, help="Max candidates to return")
    p.add_argument("--clickable-only", action="store_true",
                   help="Only return clickable nodes")
    p.add_argument("--jsonlines", action="store_true",
                   help="Print one JSON object per line")
    a = p.parse_args()

    results = find(a.query, use_regex=a.regex, top_k=a.top,
                   must_be_clickable=a.clickable_only)
    if not results:
        print("NO_MATCH", file=sys.stderr)
        sys.exit(1)
    if a.jsonlines:
        for r in results:
            print(json.dumps(r, ensure_ascii=False))
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
