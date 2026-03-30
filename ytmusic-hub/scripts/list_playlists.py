from __future__ import annotations

import sys

sys.path.insert(0, "/var/minis/skills/ytmusic-hub/scripts")
from ytmusic_client import get_client


def main() -> int:
    yt = get_client()
    playlists = yt.get_library_playlists(limit=100)
    if not playlists:
        print("未读取到任何歌单。")
        return 0
    for idx, pl in enumerate(playlists, 1):
        print(f"{idx}. {pl.get('title', '未命名歌单')}\t{pl.get('playlistId', 'NO_ID')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
