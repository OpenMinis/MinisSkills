from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/var/minis/skills/ytmusic-hub/scripts")
from ytmusic_client import get_client


DEFAULT_TITLE = "为你推荐・近期相似风格"
DEFAULT_DESC = "基于你的 Liked Music 收藏风格生成的推荐歌单。由 Minis AI 辅助整理。"


def artist_names(track: dict) -> list[str]:
    return [a.get("name", "").strip() for a in track.get("artists", []) if a.get("name")]


def collect_profile(tracks: list[dict]) -> dict:
    artist_counter = Counter()
    liked_ids = set()
    samples = []
    for t in tracks:
        vid = t.get("videoId")
        if vid:
            liked_ids.add(vid)
        names = artist_names(t)
        artist_counter.update(names)
        if len(samples) < 12:
            samples.append({
                "title": t.get("title", "未知曲目"),
                "artists": names,
            })
    top_artists = [name for name, _ in artist_counter.most_common(8)]
    return {
        "liked_ids": liked_ids,
        "top_artists": top_artists,
        "artist_counter": artist_counter,
        "samples": samples,
    }


def build_queries(profile: dict) -> list[str]:
    top = profile["top_artists"]
    queries = []
    if top:
        for name in top[:5]:
            queries.append(name)
            queries.append(f"{name} similar")
            queries.append(f"{name} 推荐")
    queries += [
        "华语 indie",
        "华语 流行 抒情",
        "mandopop 2024",
        "indie pop 2024",
        "j-pop 2024",
    ]
    # 去重保序
    seen = set()
    deduped = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            deduped.append(q)
    return deduped


def search_candidates(yt, queries: list[str], liked_ids: set[str], limit_per_query: int = 5) -> list[dict]:
    picked = []
    seen_vids = set(liked_ids)
    artist_seen = Counter()

    for q in queries:
        try:
            results = yt.search(q, filter="songs")
        except Exception:
            continue
        for item in results[:limit_per_query]:
            vid = item.get("videoId")
            if not vid or vid in seen_vids:
                continue
            names = artist_names(item)
            main_artist = names[0] if names else "未知艺人"
            if artist_seen[main_artist] >= 2:
                continue
            seen_vids.add(vid)
            artist_seen[main_artist] += 1
            picked.append({
                "videoId": vid,
                "title": item.get("title", "未知曲目"),
                "artists": names,
                "source_query": q,
            })
            if len(picked) >= 20:
                return picked
    return picked


def format_report(title: str, profile: dict, songs: list[dict], playlist_id: str) -> str:
    lines = [
        f"# 🎧 已创建歌单：{title}",
        "",
        f"- Playlist ID: `{playlist_id}`",
        f"- 你的高频艺人：{', '.join(profile['top_artists'][:6]) or '未识别'}",
        "",
        "## 风格样本",
    ]
    for s in profile["samples"][:8]:
        lines.append(f"- {s['title']} — {', '.join(s['artists']) or '未知艺人'}")
    lines += ["", "## 推荐结果", "", "| # | 歌曲 | 歌手 | 搜索来源 |", "|---|---|---|---|"]
    for idx, song in enumerate(songs, 1):
        lines.append(
            f"| {idx} | {song['title']} | {', '.join(song['artists']) or '未知艺人'} | {song['source_query']} |"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="根据点赞歌曲生成相似风格推荐歌单")
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--desc", default=DEFAULT_DESC)
    parser.add_argument("--liked-limit", type=int, default=100)
    parser.add_argument("--max-songs", type=int, default=14)
    parser.add_argument("--report", default="/var/minis/workspace/ytmusic_recommend_report.md")
    args = parser.parse_args(argv[1:])

    yt = get_client()
    liked = yt.get_liked_songs(limit=args.liked_limit)
    tracks = liked.get("tracks", [])
    if not tracks:
        print("未读取到点赞歌曲，无法生成推荐。", file=sys.stderr)
        return 1

    profile = collect_profile(tracks)
    queries = build_queries(profile)
    random.shuffle(queries)
    candidates = search_candidates(yt, queries, profile["liked_ids"])[: args.max_songs]
    if not candidates:
        print("未搜索到可用推荐歌曲。", file=sys.stderr)
        return 2

    playlist_id = yt.create_playlist(args.title, args.desc, privacy_status="PRIVATE")
    yt.add_playlist_items(playlist_id, [c["videoId"] for c in candidates])

    report = format_report(args.title, profile, candidates, playlist_id)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(f"✅ 已创建歌单：{args.title}")
    print(f"Playlist ID: {playlist_id}")
    print(f"推荐歌曲数：{len(candidates)}")
    print(f"报告文件：{report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
