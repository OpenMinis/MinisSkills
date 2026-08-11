#!/usr/bin/env python3
"""
tap_and_verify.py — Tap a located node and then PROVE the tap had its effect,
with bounded retries.

Why this script instead of a raw `tap xy`:
  A raw tap is fire-and-forget; the UI may be mid-animation, or the node may
  have drifted after a relayout. This script:

    * taps by node id or by a fuzzy query (via find_node.py);
    * waits for the DOM to stabilize after the tap;
    * optionally verifies a "success marker" appears (e.g. a pause button, a
      title, a toast) — this is how we confirm "it actually started playing";

  This is the difference between "I clicked something" and "I know it worked".
"""

import argparse
import json
import subprocess
import time
import sys


def _cli(*args) -> dict:
    proc = subprocess.run(
        ["android-a11y-cli", *args, "--compact"],
        capture_output=True, text=True, timeout=20,
    )
    payload = proc.stdout
    start = payload.find("{")
    if start == -1:
        raise RuntimeError(f"no JSON from android-a11y-cli {args}")
    data = json.loads(payload[start:])
    if not data.get("ok"):
        raise RuntimeError(data.get("error", {}).get("message", "unknown"))
    return data["data"]


def tap_node(node_id: str) -> dict:
    return _cli("tap", "node", node_id)


def _node_text() -> list:
    """Return all visible text/contentDesc as one string for marker search."""
    data = _cli("ui", "dump")
    parts = []
    for n in data.get("nodes", []):
        for k in ("text", "contentDesc"):
            v = n.get(k)
            if v and v.strip():
                parts.append(v.strip())
    return parts


def node_by_query(query: str, clickable_only: bool = True) -> dict | None:
    """Reuse find_node.py to locate a node, return top result or None."""
    import find_node
    results = find_node.find(query, must_be_clickable=clickable_only, top_k=1)
    return results[0] if results else None


def wait_stable(timeout: float = 3.0) -> None:
    try:
        _cli("wait", "stable")
    except Exception:
        time.sleep(1.0)


def verify_marker(marker: str | None, timeout: float = 5.0) -> bool:
    """Poll the UI text until `marker` appears (case-insensitive)."""
    if not marker:
        return True
    m = marker.lower()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            texts = _node_text()
        except Exception:
            texts = []
        if any(m in t.lower() for t in texts):
            return True
        time.sleep(0.5)
    return False


def tap_and_verify(query: str = None, node_id: str = None,
                   marker: str = None, retries: int = 2,
                   marker_timeout: float = 5.0) -> dict:
    """Tap a node (by id or query) and verify an effect marker appears."""
    if not node_id:
        node = node_by_query(query)
        if not node:
            return {"ok": False, "error": f"no node found for '{query}'"}
        node_id = node["nodeId"]

    attempts = 0
    while attempts <= retries:
        attempts += 1
        try:
            tap_node(node_id)
        except Exception as e:
            return {"ok": False, "error": f"tap failed: {e}"}
        wait_stable()
        if verify_marker(marker, timeout=marker_timeout):
            return {"ok": True, "nodeId": node_id, "attempts": attempts}
        # Relocate in case the tree changed after the first tap.
        if query:
            refreshed = node_by_query(query)
            if refreshed:
                node_id = refreshed["nodeId"]

    return {
        "ok": False,
        "nodeId": node_id,
        "attempts": attempts,
        "error": f"success marker '{marker}' never appeared",
    }


def main():
    p = argparse.ArgumentParser(description="Tap a node and verify the effect.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--query", help="fuzzy text to locate the node")
    g.add_argument("--node", help="explicit node id to tap")
    p.add_argument("--marker", help="text that must appear to confirm success")
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--marker-timeout", type=float, default=5.0)
    a = p.parse_args()

    result = tap_and_verify(query=a.query, node_id=a.node, marker=a.marker,
                            retries=a.retries, marker_timeout=a.marker_timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
