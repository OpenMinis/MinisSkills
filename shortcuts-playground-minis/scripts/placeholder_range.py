#!/usr/bin/env python3
"""Compute attachmentsByRange positions for WFTextTokenString templates.

Examples:
  python3 placeholder_range.py 'app://write?target=default&data=￼'
  python3 placeholder_range.py 'Hello ￼ world ￼'
"""

from __future__ import annotations

import argparse
import json
import sys

PLACEHOLDER = "￼"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("template")
    args = parser.parse_args()

    text = args.template
    ranges = []
    for idx, ch in enumerate(text):
        if ch == PLACEHOLDER:
            ranges.append({"range_key": f"{{{idx}, 1}}", "index": idx})

    result = {
        "placeholder": PLACEHOLDER,
        "count": len(ranges),
        "ranges": ranges,
        "template": text,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
