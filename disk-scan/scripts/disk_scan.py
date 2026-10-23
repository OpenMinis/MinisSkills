#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""disk-scan - show what is actually eating space in a directory tree.

Read-only. Answers "what is big here" with the largest files and the largest
subdirectories, so you can decide what to move or clean instead of guessing, or of
waiting on a graphical tool that never finishes.

Design notes worth knowing:

  One pass. Sizes are accumulated in a single os.walk. Summing each directory
  separately would re-walk every subtree, which turns a large tree (a phone's media
  folder, a project with node_modules) into minutes of pure I/O for the same answer.

  Nothing is deleted or modified, ever. There is no --apply and no cleanup mode.
  Cleaning is a separate decision that deserves its own confirmation.

  Unreadable entries are skipped rather than fatal. A scan of /sdcard or a sandbox
  root will meet permission errors; those are reported as a count, not a crash.

Stdlib only, no network.

Usage:
  disk_scan.py --dir PATH [--top N] [--min-mb M] [--exclude NAME[,NAME...]] [--json]

Exit codes: 0 = scanned; 2 = bad path or usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def human(n: int) -> str:
    step = 1024.0
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < step or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= step
    return f"{value:.1f} TB"


def scan(top: str, excludes: set) -> dict:
    """Accumulate subtree sizes in one pass; O(files x depth)."""
    dir_bytes = {}
    top_bytes = 0
    file_count = 0
    skipped = 0
    biggest = []

    def is_excluded(rel_parts) -> bool:
        return any(part in excludes for part in rel_parts)

    for root, dirs, files in os.walk(top, followlinks=False):
        rel = os.path.relpath(root, top)
        parts = [] if rel == "." else rel.split(os.sep)
        dirs[:] = [d for d in dirs if d not in excludes]
        if is_excluded(parts):
            continue
        for name in files:
            path = os.path.join(root, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                skipped += 1
                continue
            file_count += 1
            top_bytes += size
            biggest.append((size, os.path.join(rel, name) if rel != "." else name))
            cursor = rel
            while True:
                dir_bytes[cursor] = dir_bytes.get(cursor, 0) + size
                if cursor == ".":
                    break
                parent = os.path.dirname(cursor)
                cursor = parent if parent else "."

    return {
        "top_bytes": top_bytes,
        "file_count": file_count,
        "skipped": skipped,
        "dir_bytes": dir_bytes,
        "biggest": biggest,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Read-only directory size report: largest subdirectories and files."
    )
    ap.add_argument("--dir", default=".", help="directory to scan (default: current)")
    ap.add_argument("--top", type=int, default=15, help="rows to show per section (default 15)")
    ap.add_argument(
        "--min-mb",
        type=float,
        default=0.0,
        help="hide files smaller than this many MB (default 0)",
    )
    ap.add_argument(
        "--exclude",
        default="",
        help="comma-separated directory names to skip, e.g. .git,node_modules",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()

    top = os.path.abspath(os.path.expanduser(a.dir))
    if not os.path.isdir(top):
        print(f"[!] not a directory: {a.dir}", file=sys.stderr)
        return 2
    if a.top < 1:
        print("[!] --top must be at least 1", file=sys.stderr)
        return 2

    excludes = {s.strip() for s in a.exclude.split(",") if s.strip()}
    data = scan(top, excludes)

    floor = int(a.min_mb * 1048576)
    files = sorted((f for f in data["biggest"] if f[0] >= floor), reverse=True)[: a.top]
    dirs = sorted(
        ((k, v) for k, v in data["dir_bytes"].items() if k != "."), key=lambda kv: -kv[1]
    )[: a.top]

    if a.json:
        print(
            json.dumps(
                {
                    "root": top,
                    "total_bytes": data["top_bytes"],
                    "total_human": human(data["top_bytes"]),
                    "file_count": data["file_count"],
                    "skipped_entries": data["skipped"],
                    "excluded_dir_names": sorted(excludes),
                    "largest_files": [
                        {"path": p, "bytes": s, "human": human(s)} for s, p in files
                    ],
                    "largest_dirs": [
                        {"path": k, "bytes": v, "human": human(v)} for k, v in dirs
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"root: {top}")
    print(
        f"total: {human(data['top_bytes'])} in {data['file_count']} files"
        + (f" ({data['skipped']} unreadable entries skipped)" if data["skipped"] else "")
    )
    if excludes:
        print(f"excluded: {', '.join(sorted(excludes))}")

    print(f"\nlargest directories ({len(dirs)}):")
    if not dirs:
        print("  (no subdirectories)")
    for name, size in dirs:
        print(f"  {human(size):>10}  {name}")

    print(f"\nlargest files ({len(files)}):")
    if not files:
        print("  (none above the size floor)")
    for size, name in files:
        print(f"  {human(size):>10}  {name}")

    print("\nread-only scan; nothing was changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
