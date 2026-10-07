#!/usr/bin/env python3
"""Auto-fix attachmentsByRange positions in WFTextTokenString values.

Scans all WFTextTokenString structures in a Shortcuts XML, recalculates
{position, 1} keys based on actual ￼ (U+FFFC) positions in the string,
and writes the corrected XML.

Usage:
  python3 scripts/fix_placeholder_positions.py /path/to/draft.xml
  python3 scripts/fix_placeholder_positions.py /path/to/draft.xml --dry-run
  python3 scripts/fix_placeholder_positions.py /path/to/draft.xml --output /path/to/fixed.xml

Exit code:
  0 = no fixes needed or fixes applied successfully
  1 = fixes applied (when --dry-run, indicates changes would be made)
  2 = error
"""

import argparse
import plistlib
import re
import sys
from copy import deepcopy
from pathlib import Path

PLACEHOLDER = "\ufffc"  # U+FFFC Object Replacement Character
RANGE_RE = re.compile(r"\{(\d+),\s*(\d+)\}")


def find_placeholder_positions(s):
    """Return list of 0-based positions of ￼ in string s."""
    positions = []
    for i, ch in enumerate(s):
        if ch == PLACEHOLDER:
            positions.append(i)
    return positions


def fix_token_string(value_dict):
    """Fix attachmentsByRange positions in a single WFTextTokenString value dict.

    Returns (fixed_dict, num_fixes) where num_fixes is the count of position corrections.
    """
    if not isinstance(value_dict, dict):
        return value_dict, 0

    string_val = value_dict.get("string", "")
    attachments = value_dict.get("attachmentsByRange")

    if not attachments or not isinstance(attachments, dict):
        return value_dict, 0

    placeholder_positions = find_placeholder_positions(string_val)

    if len(placeholder_positions) != len(attachments):
        # Mismatch between placeholder count and attachment count — don't auto-fix
        return value_dict, 0

    # Sort existing attachments by their current position
    sorted_items = []
    for range_key, attachment_val in attachments.items():
        m = RANGE_RE.match(range_key)
        if m:
            pos = int(m.group(1))
            sorted_items.append((pos, range_key, attachment_val))
        else:
            # Non-standard key, skip
            sorted_items.append((999999, range_key, attachment_val))

    sorted_items.sort(key=lambda x: x[0])

    # Build new attachments with correct positions
    new_attachments = {}
    fixes = 0
    for i, (old_pos, old_key, attachment_val) in enumerate(sorted_items):
        correct_pos = placeholder_positions[i]
        new_key = f"{{{correct_pos}, 1}}"

        if old_key != new_key:
            fixes += 1

        new_attachments[new_key] = attachment_val

    if fixes > 0:
        result = dict(value_dict)
        result["attachmentsByRange"] = new_attachments
        return result, fixes

    return value_dict, 0


def walk_and_fix(obj, stats):
    """Recursively walk plist structure and fix WFTextTokenString values."""
    if isinstance(obj, dict):
        serialization_type = obj.get("WFSerializationType")
        if serialization_type == "WFTextTokenString":
            value = obj.get("Value")
            if isinstance(value, dict):
                fixed_value, num_fixes = fix_token_string(value)
                if num_fixes > 0:
                    obj["Value"] = fixed_value
                    stats["fixes"] += num_fixes
                    stats["tokens_fixed"] += 1
            stats["tokens_scanned"] += 1
        else:
            for key, val in obj.items():
                walk_and_fix(val, stats)

    elif isinstance(obj, list):
        for item in obj:
            walk_and_fix(item, stats)


def main():
    parser = argparse.ArgumentParser(
        description="Auto-fix WFTextTokenString placeholder positions in Shortcuts XML"
    )
    parser.add_argument("input", help="Path to Shortcuts XML file")
    parser.add_argument("--output", "-o", help="Output path (default: overwrite input)")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Report fixes without writing")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(2)

    try:
        with open(input_path, "rb") as f:
            plist_data = plistlib.load(f)
    except Exception as e:
        print(f"Error parsing {input_path}: {e}", file=sys.stderr)
        sys.exit(2)

    stats = {"tokens_scanned": 0, "tokens_fixed": 0, "fixes": 0}
    walk_and_fix(plist_data, stats)

    print(f"Scanned {stats['tokens_scanned']} WFTextTokenString values")
    print(f"Fixed {stats['fixes']} position(s) in {stats['tokens_fixed']} token(s)")

    if stats["fixes"] == 0:
        print("No fixes needed.")
        sys.exit(0)

    if args.dry_run:
        print("Dry run — no file written.")
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path
    try:
        with open(output_path, "wb") as f:
            plistlib.dump(plist_data, f, fmt=plistlib.FMT_XML, sort_keys=False)
        print(f"Written to {output_path}")
    except Exception as e:
        print(f"Error writing {output_path}: {e}", file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
