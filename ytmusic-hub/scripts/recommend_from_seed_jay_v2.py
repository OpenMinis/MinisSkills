from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, '/var/minis/skills/ytmusic-hub/scripts')
from ytmusic_client import get_client

TITLE = '为你推荐・周杰伦向 v2'
DESC = '更偏周杰伦系华语流行、R&B、青春感与夜色感的冷启动推荐歌单，由 Minis AI 生成。'
REPORT = Path('/var/minis/workspace/ytmusic_jay_v2_report.md')

QUERIES = [
    '周杰伦 songs',
    'Jay Chou songs',
    '方大同 陶喆 林俊杰 王力宏 songs',
    '华语 R&B',
    'mandopop r&b',
    '2000年代 华语流行',
    '青春 校园 华语流行',
]

BLOCK_ARTISTS = {
    'Leo Ku', '古巨基', '王琪', 'en', '大头针 Official', 'CHANYEOL', 'Punch', '邹沛沛', 'Pank'
}
PREFER_ARTISTS = {
    '周杰倫', '周杰伦', '陶喆', '方大同', '林俊傑', '林俊杰', '王力宏', '五月天', '蘇打綠', '苏打绿', '梁静茹', '孫燕姿', '孙燕姿', '潘瑋柏', '潘玮柏'
}
BLOCK_KEYWORDS = ['串烧', '情歌王', 'dj', '慢摇', 'remix']


def artist_names(track: dict) -> list[str]:
    return [a.get('name', '').strip() for a in track.get('artists', []) if a.get('name')]


def score_song(title: str, artists: list[str], query: str) -> int:
    score = 0
    if any(a in PREFER_ARTISTS for a in artists):
        score += 5
    if '周杰' in ''.join(artists) or 'Jay Chou' in ''.join(artists):
        score += 6
    if 'r&b' in query.lower() or 'mandopop' in query.lower():
        score += 2
    if '2000' in query:
        score += 2
    if '青春' in query or '校园' in query:
        score += 1
    if any(k.lower() in title.lower() for k in BLOCK_KEYWORDS):
        score -= 10
    return score


def allowed(title: str, artists: list[str]) -> bool:
    if any(a in BLOCK_ARTISTS for a in artists):
        return False
    low = title.lower()
    if any(k in low for k in [x.lower() for x in BLOCK_KEYWORDS]):
        return False
    return True


def main() -> int:
    yt = get_client()
    candidates = []
    seen = set()

    for q in QUERIES:
        results = yt.search(q, filter='songs')
        for item in results[:12]:
            vid = item.get('videoId')
            if not vid or vid in seen:
                continue
            artists = artist_names(item)
            title = item.get('title', '未知曲目')
            if not artists or not allowed(title, artists):
                continue
            seen.add(vid)
            candidates.append({
                'title': title,
                'videoId': vid,
                'artists': artists,
                'query': q,
                'score': score_song(title, artists, q),
            })

    candidates.sort(key=lambda x: (-x['score'], x['title']))

    picked = []
    artist_cap = {}
    for item in candidates:
        main_artist = item['artists'][0]
        cap = 3 if ('周杰' in main_artist or main_artist in {'陶喆', '方大同', '林俊傑', '林俊杰', '王力宏'}) else 1
        if artist_cap.get(main_artist, 0) >= cap:
            continue
        picked.append(item)
        artist_cap[main_artist] = artist_cap.get(main_artist, 0) + 1
        if len(picked) >= 14:
            break

    if not picked:
        print('未筛出合适歌曲。', file=sys.stderr)
        return 1

    playlist_id = yt.create_playlist(TITLE, DESC, privacy_status='PRIVATE')
    yt.add_playlist_items(playlist_id, [x['videoId'] for x in picked])

    lines = [
        f'# 🎧 已创建歌单：{TITLE}',
        '',
        f'- Playlist ID: `{playlist_id}`',
        '- 风格锚点：周杰伦系、华语 R&B、2000 年代华语流行、青春感与夜色感',
        '',
        '| # | 歌曲 | 歌手 | 分数 | 来源搜索词 |',
        '|---|---|---|---:|---|',
    ]
    for i, x in enumerate(picked, 1):
        lines.append(f"| {i} | {x['title']} | {', '.join(x['artists'])} | {x['score']} | {x['query']} |")
    REPORT.write_text('\n'.join(lines), encoding='utf-8')

    print(f'✅ 已创建歌单：{TITLE}')
    print(f'Playlist ID: {playlist_id}')
    print(f'歌曲数：{len(picked)}')
    print(f'报告：{REPORT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
