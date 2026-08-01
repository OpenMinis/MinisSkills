from __future__ import annotations

import sys

sys.path.insert(0, "/var/minis/skills/ytmusic-hub/scripts")
from ytmusic_client import get_client


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("用法：python3 search_and_add.py <搜索词> <playlistId>", file=sys.stderr)
        return 1

    query = argv[1]
    playlist_id = argv[2]

    yt = get_client()
    songs = yt.search(query, filter="songs")
    if not songs:
        print("未找到匹配歌曲。", file=sys.stderr)
        return 2

    song = songs[0]
    yt.add_playlist_items(playlist_id, [song["videoId"]])
    artists = ", ".join(a.get("name", "未知艺人") for a in song.get("artists", []))
    print(f"✅ 已加入歌单：{song.get('title', '未知曲目')} — {artists}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
