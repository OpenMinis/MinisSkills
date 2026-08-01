#!/usr/bin/env -S uv run --script --cache-dir /root/.cache/uv
# /// script
# requires-python = ">=3.10"
# dependencies = ["spotipy>=2.26.0"]
# ///

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os, sys, random

SCOPE = " ".join([
    "user-read-playback-state", "user-modify-playback-state",
    "user-read-currently-playing", "streaming",
    "user-library-read", "user-library-modify",
    "playlist-read-private", "playlist-read-collaborative",
    "playlist-modify-public", "playlist-modify-private",
    "user-read-private", "user-read-email",
    "user-top-read", "user-read-recently-played",
    "user-follow-read", "user-follow-modify",
])
CACHE_PATH = os.path.expanduser("~/.config/spotify/cache")

def get_sp():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.environ["SPOTIPY_CLIENT_ID"],
        client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
        redirect_uri=os.environ["SPOTIPY_REDIRECT_URI"],
        scope=SCOPE, cache_path=CACHE_PATH, open_browser=False,
    ))

def get_active_device(sp):
    devices = sp.devices()["devices"]
    if not devices:
        print("❌ 没有活跃设备，请先打开 Spotify 并播放任意歌曲")
        return None
    return next((d["id"] for d in devices if d["is_active"]), devices[0]["id"])

def fmt_duration(ms):
    s = ms // 1000
    return f"{s//60}:{s%60:02d}"

# ── 播放状态 ──────────────────────────────────────────────
def cmd_status(sp):
    cur = sp.current_playback()
    if cur and cur.get("item"):
        t = cur["item"]
        state = "▶" if cur["is_playing"] else "⏸"
        print(f"{state} {t['name']}")
        print(f"   🎤 {', '.join(a['name'] for a in t['artists'])}")
        print(f"   💿 {t['album']['name']}")
        print(f"   ⏱ {fmt_duration(cur['progress_ms'])} / {fmt_duration(t['duration_ms'])}")
        print(f"   🔀 随机: {'开' if cur.get('shuffle_state') else '关'}  "
              f"🔁 循环: {cur.get('repeat_state','off')}")
    else:
        print("⏹ 当前没有播放任何内容")
    print()
    devices = sp.devices()["devices"]
    if devices:
        print("📱 设备：")
        for d in devices:
            print(f"  {'▶ ' if d['is_active'] else '  '}{d['name']} ({d['type']}) 音量:{d['volume_percent']}%")

# ── 基础控制 ──────────────────────────────────────────────
def cmd_play(sp):    sp.start_playback();  print("▶ 已播放")
def cmd_pause(sp):   sp.pause_playback();  print("⏸ 已暂停")
def cmd_next(sp):    sp.next_track();      print("⏭ 下一首")
def cmd_prev(sp):    sp.previous_track();  print("⏮ 上一首")

def cmd_volume(sp, args):
    vol = int(args[0])
    sp.volume(vol)
    print(f"🔊 音量设为 {vol}%")

def cmd_shuffle(sp, args):
    state = args[0].lower() in ("on", "1", "true", "开")
    sp.shuffle(state)
    print(f"🔀 随机播放: {'开启' if state else '关闭'}")

def cmd_repeat(sp, args):
    # 模式: off / track / context
    mode = args[0].lower() if args else "track"
    alias = {"off":"off","关":"off","single":"track","单曲":"track","track":"track","list":"context","context":"context","列表":"context"}
    mode = alias.get(mode, "track")
    sp.repeat(mode)
    labels = {"off":"关闭","track":"单曲循环","context":"列表循环"}
    print(f"🔁 循环模式: {labels[mode]}")

def cmd_seek(sp, args):
    # 支持秒数或 mm:ss
    pos = args[0]
    if ":" in pos:
        m, s = pos.split(":")
        ms = (int(m) * 60 + int(s)) * 1000
    else:
        ms = int(pos) * 1000
    sp.seek_track(ms)
    print(f"⏩ 跳转到 {pos}")

# ── 搜索 & 播放 ───────────────────────────────────────────
def cmd_search(sp, args):
    query = " ".join(args)
    results = sp.search(q=query, type="track", limit=10, market="HK")
    tracks = results["tracks"]["items"]
    if not tracks:
        print(f"❌ 未找到「{query}」"); return
    device_id = get_active_device(sp)
    if not device_id: return
    sp.start_playback(device_id=device_id, uris=[t["uri"] for t in tracks])
    print(f"▶ 正在播放 {len(tracks)} 首「{query}」：")
    for i, t in enumerate(tracks):
        print(f"  {i+1}. {t['name']} - {t['artists'][0]['name']} {fmt_duration(t['duration_ms'])}")

def cmd_search_multi(sp, keywords, count_each=10):
    """多关键词混合搜索播放（热门歌单场景）"""
    tracks, seen = [], set()
    for kw in keywords:
        for t in sp.search(q=kw, type="track", limit=count_each, market="HK")["tracks"]["items"]:
            if t["uri"] not in seen:
                seen.add(t["uri"]); tracks.append(t)
    random.shuffle(tracks)
    device_id = get_active_device(sp)
    if not device_id: return
    sp.start_playback(device_id=device_id, uris=[t["uri"] for t in tracks])
    print(f"▶ 正在播放 {len(tracks)} 首：")
    for i, t in enumerate(tracks):
        print(f"  {i+1}. {t['name']} - {t['artists'][0]['name']}")

def cmd_play_track(sp, args):
    tid = args[0]
    uri = tid if tid.startswith("spotify:") else f"spotify:track:{tid}"
    device_id = get_active_device(sp)
    if device_id:
        sp.start_playback(device_id=device_id, uris=[uri])
        print(f"▶ 正在播放: {tid}")

# ── 音乐库 ────────────────────────────────────────────────
def cmd_save(sp):
    cur = sp.current_playback()
    if not cur or not cur.get("item"):
        print("❌ 当前没有播放任何内容"); return
    t = cur["item"]
    sp.current_user_saved_tracks_add([t["id"]])
    print(f"❤️  已收藏：{t['name']} - {t['artists'][0]['name']}")

def cmd_unsave(sp):
    cur = sp.current_playback()
    if not cur or not cur.get("item"):
        print("❌ 当前没有播放任何内容"); return
    t = cur["item"]
    sp.current_user_saved_tracks_delete([t["id"]])
    print(f"💔 已取消收藏：{t['name']} - {t['artists'][0]['name']}")

def cmd_liked(sp, args):
    limit = int(args[0]) if args else 20
    results = sp.current_user_saved_tracks(limit=limit)
    print(f"❤️  已收藏歌曲（最近 {limit} 首）：")
    for i, item in enumerate(results["items"]):
        t = item["track"]
        print(f"  {i+1}. {t['name']} - {t['artists'][0]['name']}")

def cmd_recent(sp, args):
    limit = int(args[0]) if args else 10
    results = sp.current_user_recently_played(limit=limit)
    print(f"🕐 最近播放（{limit} 首）：")
    for i, item in enumerate(results["items"]):
        t = item["track"]
        print(f"  {i+1}. {t['name']} - {t['artists'][0]['name']}")

def cmd_top(sp, args):
    # top tracks / top artists
    ttype = "artists" if args and args[0] == "artists" else "tracks"
    limit = int(args[1]) if len(args) > 1 else 10
    results = sp.current_user_top_tracks(limit=limit) if ttype == "tracks" else sp.current_user_top_artists(limit=limit)
    label = "歌曲" if ttype == "tracks" else "艺术家"
    print(f"🏆 你最常听的{label}（Top {limit}）：")
    for i, item in enumerate(results["items"]):
        name = item["name"]
        extra = f" - {item['artists'][0]['name']}" if ttype == "tracks" else ""
        print(f"  {i+1}. {name}{extra}")

# ── 歌单管理 ──────────────────────────────────────────────
def cmd_playlists(sp):
    results = sp.current_user_playlists(limit=20)
    print(f"📋 我的歌单（{results['total']} 个）：")
    for i, p in enumerate(results["items"]):
        print(f"  {i+1}. {p['name']} ({p['tracks']['total']} 首) id:{p['id']}")

def cmd_play_playlist(sp, args):
    pid = args[0]
    uri = pid if pid.startswith("spotify:") else f"spotify:playlist:{pid}"
    device_id = get_active_device(sp)
    if device_id:
        sp.start_playback(device_id=device_id, context_uri=uri)
        print(f"▶ 正在播放歌单: {pid}")

def cmd_create_playlist(sp, args):
    name = " ".join(args)
    user = sp.current_user()["id"]
    p = sp.user_playlist_create(user, name, public=False)
    print(f"✅ 已创建歌单：{name}  id:{p['id']}")

def cmd_add_to_playlist(sp, args):
    # add-to-playlist <playlist_id> （将当前歌曲加入歌单）
    pid = args[0]
    cur = sp.current_playback()
    if not cur or not cur.get("item"):
        print("❌ 当前没有播放任何内容"); return
    t = cur["item"]
    sp.playlist_add_items(pid, [t["uri"]])
    print(f"➕ 已将「{t['name']}」加入歌单 {pid}")

# ── 关注 ──────────────────────────────────────────────────
def cmd_follow_artist(sp, args):
    # 搜索艺术家并关注
    query = " ".join(args)
    results = sp.search(q=query, type="artist", limit=1)
    artists = results["artists"]["items"]
    if not artists:
        print(f"❌ 未找到艺术家「{query}」"); return
    a = artists[0]
    sp.user_follow_artists([a["id"]])
    print(f"✅ 已关注：{a['name']} (粉丝:{a['followers']['total']:,})")

def cmd_following(sp):
    results = sp.current_user_followed_artists(limit=20)
    artists = results["artists"]["items"]
    print(f"👥 关注的艺术家（{results['artists']['total']} 位）：")
    for i, a in enumerate(artists):
        print(f"  {i+1}. {a['name']} (粉丝:{a['followers']['total']:,})")

# ── 主入口 ────────────────────────────────────────────────
COMMANDS = {
    # 状态
    "status":           (cmd_status,          False, "当前播放状态 + 设备列表"),
    # 基础控制
    "play":             (cmd_play,            False, "继续播放"),
    "pause":            (cmd_pause,           False, "暂停"),
    "next":             (cmd_next,            False, "下一首"),
    "prev":             (cmd_prev,            False, "上一首"),
    "volume":           (cmd_volume,          True,  "设置音量  volume <0-100>"),
    "shuffle":          (cmd_shuffle,         True,  "随机播放  shuffle on/off"),
    "repeat":           (cmd_repeat,          True,  "循环模式  repeat off/track/context"),
    "seek":             (cmd_seek,            True,  "跳转进度  seek <秒> 或 seek <mm:ss>"),
    # 搜索播放
    "search":           (cmd_search,          True,  "搜索并播放  search <关键词>"),
    "play-track":       (cmd_play_track,      True,  "播放指定歌曲  play-track <id/uri>"),
    "play-playlist":    (cmd_play_playlist,   True,  "播放歌单  play-playlist <id/uri>"),
    # 音乐库
    "save":             (cmd_save,            False, "收藏当前歌曲"),
    "unsave":           (cmd_unsave,          False, "取消收藏当前歌曲"),
    "liked":            (cmd_liked,           True,  "查看已收藏  liked [数量]"),
    "recent":           (cmd_recent,          True,  "最近播放  recent [数量]"),
    "top":              (cmd_top,             True,  "最常听  top [tracks/artists] [数量]"),
    # 歌单管理
    "playlists":        (cmd_playlists,       False, "查看我的歌单"),
    "create-playlist":  (cmd_create_playlist, True,  "新建歌单  create-playlist <名称>"),
    "add-to-playlist":  (cmd_add_to_playlist, True,  "当前歌曲加入歌单  add-to-playlist <id>"),
    # 关注
    "follow":           (cmd_follow_artist,   True,  "关注艺术家  follow <名称>"),
    "following":        (cmd_following,       False, "查看关注的艺术家"),
}

def main():
    sp = get_sp()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    args = sys.argv[2:]

    if cmd not in COMMANDS:
        print("🎵 Spotify Hub 支持的命令：\n")
        for name, (_, _, desc) in COMMANDS.items():
            print(f"  {name:<20} {desc}")
        return

    fn, has_args, _ = COMMANDS[cmd]
    fn(sp, args) if has_args else fn(sp)

if __name__ == "__main__":
    main()
