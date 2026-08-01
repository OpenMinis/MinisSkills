"""
test_auth.py
验证当前 ytmusic 认证文件是否可用。
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/var/minis/skills/ytmusic-hub/scripts")

from ytmusic_client import get_client


def main() -> int:
    try:
        yt = get_client()
        playlists = yt.get_library_playlists(limit=5)
        print(f"✅ 认证验证成功：已读取到 {len(playlists)} 个歌单（最多显示前 5 个）。")
        for idx, pl in enumerate(playlists[:5], 1):
            print(f"{idx}. {pl.get('title', '未命名歌单')} [{pl.get('playlistId', 'NO_ID')}]")
        return 0
    except Exception as exc:
        print(f"❌ 认证验证失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
