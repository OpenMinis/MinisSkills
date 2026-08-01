from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, '/var/minis/skills/ytmusic-hub/scripts')
from ytmusic_client import get_client

SEED = '周杰伦'
TITLE = '为你推荐・周杰伦向'
DESC = '基于周杰伦风格做的冷启动推荐歌单，由 Minis AI 生成。'
REPORT = Path('/var/minis/workspace/ytmusic_jay_playlist_report.md')

QUERIES = [
    '周杰伦',
    'Jay Chou',
    'mandopop 周杰伦 similar',
    '华语流行 周杰伦风格',
    '周杰伦 similar songs',
    '华语经典流行',
    '华语抒情流行',
]


def artist_names(track: dict) -> list[str]:
    return [a.get('name', '').strip() for a in track.get('artists', []) if a.get('name')]


def main() -> int:
    yt = get_client()
    picked = []
    seen = set()
    artist_count = {}

    for q in QUERIES:
        results = yt.search(q, filter='songs')
        for item in results[:8]:
            vid = item.get('videoId')
            if not vid or vid in seen:
                continue
            artists = artist_names(item)
            if not artists:
                continue
            main_artist = artists[0]
            if artist_count.get(main_artist, 0) >= 2:
                continue
            seen.add(vid)
            artist_count[main_artist] = artist_count.get(main_artist, 0) + 1
            picked.append({
                'title': item.get('title', '未知曲目'),
                'videoId': vid,
                'artists': artists,
                'query': q,
            })
            if len(picked) >= 14:
                break
        if len(picked) >= 14:
            break

    if not picked:
        print('未搜到可用歌曲。', file=sys.stderr)
        return 1

    playlist_id = yt.create_playlist(TITLE, DESC, privacy_status='PRIVATE')
    yt.add_playlist_items(playlist_id, [x['videoId'] for x in picked])

    lines = [f'# 🎧 已创建歌单：{TITLE}', '', f'- Playlist ID: `{playlist_id}`', f'- 种子风格：{SEED}', '', '| # | 歌曲 | 歌手 | 来源搜索词 |', '|---|---|---|---|']
    for i, x in enumerate(picked, 1):
        lines.append(f"| {i} | {x['title']} | {', '.join(x['artists'])} | {x['query']} |")
    REPORT.write_text('\n'.join(lines), encoding='utf-8')

    print(f'✅ 已创建歌单：{TITLE}')
    print(f'Playlist ID: {playlist_id}')
    print(f'歌曲数：{len(picked)}')
    print(f'报告：{REPORT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
