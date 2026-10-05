#!/usr/bin/env python3
"""Quick profile inspector for high-value defaults used in planning."""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path('/var/minis/skills/shortcuts-playground-minis/data')
PRIMARY = DATA_DIR / 'user_profile.json'
FALLBACK = DATA_DIR / 'user_profile.example.json'
IMPORTANT_PATHS = [
    ('system_targets', 'default_note_identifier'),
    ('system_targets', 'default_reminder_list'),
    ('external_targets', 'default_app'),
    ('external_targets', 'default_target_identifier'),
    ('external_targets', 'supports_uri_write'),
    ('permissions', 'allow_third_party_signing'),
    ('delivery_mode',),
]


def get_nested(obj, path):
    cur = obj
    for key in path:
        cur = cur.get(key, None) if isinstance(cur, dict) else None
    return cur


def main() -> int:
    chosen = PRIMARY if PRIMARY.is_file() else FALLBACK
    data = json.loads(chosen.read_text(encoding='utf-8'))
    extracted = {'.'.join(path): get_nested(data, path) for path in IMPORTANT_PATHS}
    print(json.dumps({'profile_path': str(chosen), 'summary': extracted}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
