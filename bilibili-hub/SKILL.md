---
name: bilibili-hub
description: >
  A skill for reading and writing Bilibili data with Python + UV, using bilibili-api-python + aiohttp.
  It automatically obtains cookies through `browser_use get_cookies` for authentication, so no manual copying is required.
  Supports video details, subtitles, AI summaries, comments, user profiles, search, popular videos/rankings, following dynamics feed,
  favorites, Watch Later, viewing history, interactions (likes, coins, triple action), publishing and deleting dynamics, and more.
  When a user mentions "Bilibili," "bilibili," "Bilibili videos," "Bilibili popular," "bilibili-hub,"
  "get Bilibili data," "Bilibili subtitles," "Bilibili comments," "Bilibili favorites," "Bilibili dynamics,"
  or any scenario that requires programmatically reading or writing Bilibili content, this skill must be triggered.
---

# bilibili-hub

> **Modified from**: [jackwener/bilibili-cli](https://github.com/jackwener/bilibili-cli) (Apache-2.0)
>
> This skill simplifies and modifies the original repository as follows:
> - Removed the `browser-cookie3` / `click` / `rich` / `PyYAML` / `qrcode` dependencies
> - Changed cookie authentication to accept a `dict` directly or read from environment variables, without automatic browser extraction
> - Removed the CLI layer (`commands/`), QR login, formatters, and related components
> - Kept all API methods and wrapped them uniformly as synchronous interfaces (`asyncio.run`)
> - Core dependency: `bilibili-api-python`, a third-party SDK that reverse engineers the Bilibili API
> - In the Minis environment, cookies are obtained automatically through `browser_use get_cookies`

---

## File Structure

```
/var/minis/skills/bilibili-hub/
├── SKILL.md
├── pyproject.toml          # bilibili-api-python + aiohttp
└── scripts/
    ├── __init__.py
    ├── exceptions.py       # 6 structured exception types
    ├── payloads.py         # Data structure normalization (normalize_* functions)
    └── client.py           # BiliClient core class (all API methods)
```

---

## Authentication Methods

The Bilibili Web API uses three key cookies:

| Cookie | Description |
|--------|------|
| `SESSDATA` | User session (required for read operations) |
| `bili_jct` | CSRF token (required for write operations: likes, coins, posting dynamics, etc.) |
| `DedeUserID` | User ID (recommended) |
| `buvid3` | Device ID (recommended; reduces the likelihood of triggering risk control) |

### Method 1: Automatically retrieve via `browser_use` (preferred in Minis environments)

1. Use `browser_use navigate` to open `https://www.bilibili.com` and confirm that you are logged in.
2. Use `browser_use get_cookies` to retrieve cookies (raw values do not appear in the conversation).
3. Load the offload env file:

```bash
. /var/minis/offloads/env_cookies_www_bilibili_com_xxx.sh
export BILI_SESSDATA="$COOKIE_SESSDATA"
export BILI_JCT="$COOKIE_BILI_JCT"
export BILI_USERID="$COOKIE_DEDEUSERID"
export BILI_BUVID3="$COOKIE_BUVID3"
```

> **Note**: `get_cookies` only applies to the current page's domain. Navigate to `https://www.bilibili.com` before calling it.

### Method 2: Manually retrieve from browser DevTools

1. Log in to Bilibili, then open DevTools -> Application -> Cookies -> `https://www.bilibili.com`.
2. Find the values of `SESSDATA`, `bili_jct`, and `DedeUserID`.
3. Store them in the Minis environment variables: `BILI_SESSDATA` / `BILI_JCT` / `BILI_USERID`.

### Ways to pass cookies (three methods)

```python
# Method 1: From environment variables (recommended)
client = BiliClient.from_env()

# Method 2: Pass a dict directly
client = BiliClient({
    "SESSDATA":   os.environ["BILI_SESSDATA"],
    "bili_jct":   os.environ["BILI_JCT"],
    "DedeUserID": os.environ["BILI_USERID"],
})

# Method 3: Read-only operations (no write permissions required)
client = BiliClient({"SESSDATA": os.environ["BILI_SESSDATA"]})
```

---

## Quick Start

### Environment setup

```bash
cd /var/minis/skills/bilibili-hub
uv sync
```

### Calling as a Python library

```python
import os, json, sys
sys.path.insert(0, "/var/minis/skills/bilibili-hub")
from scripts.client import BiliClient

client = BiliClient.from_env()

# Current user information
me = client.whoami()
print("User:", me.get("name"), "UID:", me.get("mid"))

# Search videos
videos = client.search_videos("Python Tutorial", count=5)
for v in videos:
    print(f"  {v['bvid']} {v['title']} ({v['duration']})")

# Get video details (including subtitles)
detail = client.get_video("BV1xx411c7mD", subtitle=True)
print(detail["video"]["title"])
print(detail["subtitle"]["text"][:200])

# Popular videos
hot = client.get_hot(count=10)
for v in hot:
    print(f"  {v['bvid']} {v['title']} 👁{v['stats']['view']}")
```

---

## API Method Quick Reference

### Account

| Method | Description |
|------|------|
| `whoami()` | Get information about the currently logged-in user |

### Video

| Method | Description |
|------|------|
| `get_video(bvid, *, subtitle, subtitle_timeline, ai_summary, comments, related)` | Get video details (optional subtitles/AI summary/comments/related videos) |

`bvid` supports a BV number or full URL and is extracted automatically.

### Users

| Method | Description |
|------|------|
| `get_user(uid)` | Get user profile information + following/follower counts |
| `get_user_videos(uid, count=20)` | Get videos posted by a user |

### Search

| Method | Description |
|------|------|
| `search_videos(keyword, page=1, count=20)` | Search videos |
| `search_users(keyword, page=1)` | Search users |

### Discover

| Method | Description |
|------|------|
| `get_hot(page=1, count=20)` | Site-wide popular videos |
| `get_rank(day=3, count=50)` | Site-wide rankings (`day`: 1/3/7) |
| `get_feed(offset=0)` | Following dynamics feed (login required) |
| `get_my_dynamics(offset=0)` | Dynamics I published (login required) |
| `post_dynamic(text)` | Post a text dynamic (login + `bili_jct` required) |
| `delete_dynamic(dynamic_id)` | Delete a dynamic (login + `bili_jct` required) |

### Favorites / History

| Method | Description |
|------|------|
| `get_favorites()` | Get the favorites folder list (login required) |
| `get_favorites(folder_id)` | Get videos in a favorites folder |
| `get_following(page=1)` | Get the following list (login required) |
| `get_watch_later()` | Get the Watch Later list (login required) |
| `get_history()` | Get viewing history (login required) |

### Download

| Method | Description |
|------|------|
| `download_video(bvid, output_dir, filename=None)` | Download the full video (`mp4`), automatically handling DASH merging |
| `download_audio(bvid, output_dir, filename=None)` | Download only the audio stream (`m4a`), suitable for ASR transcription |

**Download process**:
- DASH streams (common): download the video stream and audio stream separately -> merge with `ffmpeg copy` -> if merging fails, keep the silent video
- FLV/MP4 streams (rare): download directly, no merging required
- Without logging in, downloads are limited to 480P; after logging in, 1080P is available (premium members can download higher quality)

| Method | Description |
|------|------|
| `like(bvid)` / `like(bvid, undo=True)` | Like / unlike (requires `bili_jct`) |
| `coin(bvid, num=1)` | Give 1 or 2 coins (requires `bili_jct`) |
| `triple(bvid)` | Perform the one-click triple action (requires `bili_jct`) |
| `unfollow(uid)` | Unfollow a user (requires `bili_jct`) |

---

## Error Handling

```python
from scripts.exceptions import (
    AuthenticationError,  # Cookie missing or expired
    RateLimitError,       # Triggered risk control (412)
    NotFoundError,        # Video/user does not exist
    NetworkError,         # Network/timeout error
    InvalidBvidError,     # Invalid BV number format
    BiliError,            # Other API error (base class)
)

try:
    detail = client.get_video("BV1xx411c7mD")
except AuthenticationError:
    print("Cookie has expired. Please retrieve it again.")
except RateLimitError:
    print("Risk control triggered. Try again later.")
except NotFoundError:
    print("Video does not exist.")
except BiliError as e:
    print(f"API error: {e}")
```

---

## Important Notes

- `SESSDATA` is the minimum requirement for read operations. Write operations (likes, coins, posting dynamics) also require `bili_jct`.
- Cookies are usually valid for several days to several weeks. After they expire, retrieve them again through `browser_use get_cookies`.
- Bilibili applies risk control to high-frequency requests (HTTP 412). An operation interval of at least 1 second is recommended.
- `bilibili-api-python` is a community-maintained reverse-engineering project, and its interfaces may break when Bilibili updates.
- Write operations (coins, triple action, etc.) cannot be reversed. Use them with caution.
