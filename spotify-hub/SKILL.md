---
name: spotify-hub
version: 1.0.0
description: 使用 Python + spotipy 控制 Spotify 播放的技能。支持播放/暂停/切歌/音量/随机、搜索歌曲并播放、按关键词混合生成歌单（如抖音热歌、某风格、某歌手）、查看当前播放状态和设备列表。当用户提到"Spotify"、"播放音乐"、"切歌"、"暂停"、"搜索歌曲"、"换歌单"、"spotify-hub"，或任何需要控制 Spotify 播放的场景，必须触发本技能。
---

# Spotify Hub

通过 spotipy 库调用 Spotify Web API，控制播放并搜索音乐。

## 依赖

两个脚本均使用 **uv inline script** 声明依赖（`spotipy>=2.26.0`），用 `uv run` 执行时自动安装，无需手动 pip install，开箱即用。

## 环境要求

必须设置以下环境变量（未设置则引导用户创建）：
- `SPOTIPY_CLIENT_ID` — [设置](minis://settings/environments?create_key=SPOTIPY_CLIENT_ID&create_value=)
- `SPOTIPY_CLIENT_SECRET` — [设置](minis://settings/environments?create_key=SPOTIPY_CLIENT_SECRET&create_value=)
- `SPOTIPY_REDIRECT_URI` — [设置](minis://settings/environments?create_key=SPOTIPY_REDIRECT_URI&create_value=http://127.0.0.1:8888/callback)

凭证申请：https://developer.spotify.com/dashboard → Create App → Redirect URI 填 `http://127.0.0.1:8888/callback`

## 授权流程（首次或 Token 失效时）

Token 保存在 `~/.config/spotify/cache`，含 refresh_token，正常情况下永久有效，无需重复授权。

**需要授权时**，在后台启动授权服务器，获取 URL 后直接给用户点击：

```python
# 后台启动授权服务器
import subprocess, time
subprocess.Popen(["uv", "run", "--script", "--cache-dir", "/root/.cache/uv",
                              "/var/minis/skills/spotify-hub/scripts/spotify_auth.py"],
                 stdout=open("/tmp/spotify_auth.log", "w"), stderr=subprocess.STDOUT)
time.sleep(2)
url = open("/tmp/spotify_auth_url.txt").read().strip()
print(url)
```

然后在回复中给用户提供可点击的授权链接：
`[👉 点击授权 Spotify](<url>)`

授权完成后浏览器显示"✅ Spotify 授权成功！"，用户告知后即可继续操作。

## 核心脚本

所有操作通过 `/var/minis/skills/spotify-hub/scripts/spotify.py` 执行：

```bash
uv run --script --cache-dir /root/.cache/uv /var/minis/skills/spotify-hub/scripts/spotify.py <cmd> [args]
```

| 命令 | 说明 |
|------|------|
| `status` | 当前播放状态 + 设备列表 |
| `play` / `pause` | 播放 / 暂停 |
| `next` / `prev` | 下一首 / 上一首 |
| `volume <0-100>` | 设置音量 |
| `shuffle on/off` | 随机播放开关 |
| `repeat off/track/context` | 循环模式 |
| `seek <秒或mm:ss>` | 跳转进度 |
| `search <关键词>` | 搜索并播放 |
| `play-track <id/uri>` | 播放指定歌曲 |
| `play-playlist <id/uri>` | 播放指定歌单 |
| `save` / `unsave` | 收藏 / 取消收藏当前歌曲 |
| `liked [数量]` | 查看已收藏歌曲 |
| `recent [数量]` | 最近播放记录 |
| `top [tracks/artists] [数量]` | 最常听歌曲 / 艺术家 |
| `playlists` | 查看我的歌单列表 |
| `create-playlist <名称>` | 新建歌单 |
| `add-to-playlist <id>` | 当前歌曲加入歌单 |
| `follow <艺术家名>` | 关注艺术家 |
| `following` | 查看关注的艺术家 |

## 热门歌单场景（如"抖音热歌"、"某风格"）

第三方公开歌单会返回 403，**不要尝试读取歌单**，改用多关键词搜索混合播放：

```python
from scripts.spotify import get_sp, search_multi_and_play

sp = get_sp()
keywords = ["抖音热门", "douyin trending", "tiktok viral 2024", "抖音神曲"]
search_multi_and_play(sp, keywords, count_each=10, market="HK")
```

或直接用 shell_execute 调用 spotify.py search：
```bash
uv run --script --cache-dir /root/.cache/uv /var/minis/skills/spotify-hub/scripts/spotify.py search "抖音热门"
```

## 注意事项

- 播放控制需要设备处于活跃状态（手机/电脑已打开 Spotify 并播放过）
- `market="HK"` 可搜到更多中文歌曲
- spotipy 已预装（`pip show spotipy` 可验证）
- Development Mode 下第三方公开歌单 403 是正常限制，用搜索代替
