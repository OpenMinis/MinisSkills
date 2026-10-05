#!/usr/bin/env python3
"""Validate availability of core local assets for shortcuts-playground-minis."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/var/minis/skills/shortcuts-playground-minis')
REQUIRED = [
    'SKILL.md',
    'ROUTING_FRAMEWORK.md',
    'CLARIFICATION_TEMPLATES.md',
    'COMMON_PATTERNS.md',
    'ACTION_RECIPES.md',
    'BUILD_CHECKLIST.md',
    'XML_SNIPPET_PATTERNS.md',
    'scripts/validate_shortcut.py',
    'scripts/sign_shortcut.py',
    'scripts/sign_shortcut_via_hubsign.py',
    'scripts/placeholder_range.py',
    'scripts/load_env_profile.py',
    'data/user_profile.example.json',
]


def main() -> int:
    missing = []
    present = []
    for rel in REQUIRED:
        p = ROOT / rel
        if p.exists():
            present.append(rel)
        else:
            missing.append(rel)
    print(json.dumps({
        'ok': not missing,
        'present_count': len(present),
        'missing_count': len(missing),
        'missing': missing,
    }, ensure_ascii=False, indent=2))
    return 0 if not missing else 1


if __name__ == '__main__':
    raise SystemExit(main())
