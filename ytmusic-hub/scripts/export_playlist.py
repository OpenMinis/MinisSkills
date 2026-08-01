from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "/var/minis/skills/ytmusic-hub/scripts")
from ytmusic_client import get_client


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("用法：python3 export_playlist.py <playlistId> [输出文件路径]", file=sys.stderr)
        return 1

    playlist_id = argv[1]
    output = Path(argv[2]) if len(argv) >= 3 else None

    yt = get_client()
    playlist = yt.get_playlist(playlist_id, limit=500)

    lines = [f"# {playlist.get('title', '未命名歌单')}", ""]
    desc = playlist.get("description")
    if desc:
        lines.append(f"> {desc}")
        lines.append("")

    for idx, track in enumerate(playlist.get("tracks", []), 1):
        artists = ", ".join(a.get("name", "未知艺人") for a in track.get("artists", []))
        lines.append(f"{idx}. **{track.get('title', '未知曲目')}** — {artists}")

    text = "\n".join(lines)
    if output:
        output.write_text(text, encoding="utf-8")
        print(f"✅ 已导出到：{output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
