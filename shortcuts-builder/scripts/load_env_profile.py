#!/usr/bin/env python3
"""Load effective user profile for shortcuts-builder.

Search order:
1. /var/minis/skills/shortcuts-builder/data/user_profile.json
2. /var/minis/skills/shortcuts-builder/data/user_profile.example.json
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path('/var/minis/skills/shortcuts-builder/data')
PRIMARY = DATA_DIR / 'user_profile.json'
FALLBACK = DATA_DIR / 'user_profile.example.json'


def main() -> int:
    chosen = PRIMARY if PRIMARY.is_file() else FALLBACK
    data = json.loads(chosen.read_text(encoding='utf-8'))
    print(json.dumps({
        'profile_path': str(chosen),
        'profile': data,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
