---
name: xiaohongshu-hub
description: >
  Skill for reading and writing Xiaohongshu (XHS) data using Python + UV. It depends only on httpx + pycryptodome,
  automatically retrieves cookies via `browser_use get_cookies` to complete authentication, and requires no manual copying.
  It supports searching notes, users, and topics; reading note details and comments; recommendation feeds; trending lists;
  social actions (follow/favorite); interactions (like/comment/reply); notification queries; creator note management; and more.
  This skill must be triggered when the user mentions "Xiaohongshu," "XHS," "scraping Xiaohongshu," "searching Xiaohongshu notes," "Xiaohongshu comments,"
  "xiaohongshu-hub," "reading Xiaohongshu data," "Xiaohongshu Cookie,"
  or any scenario that requires programmatically reading or writing Xiaohongshu content.
---

# xiaohongshu-hub

> **Modified from**: [jackwener/xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli) (Apache-2.0)
>
> This skill simplifies and modifies the original repository as follows:
> - Removes the `browser-cookie3` / `click` / `rich` / `PyYAML` / `qrcode` dependencies
> - Changes Cookie authentication to pass a `dict` directly or read from environment variables, without automatic browser extraction
> - Removes the CLI layer (`commands/`) and QR login module (`qr_login.py`)
> - Keeps the complete reverse-engineered signing algorithm in `signing.py`, implemented with the standard library only and no third-party dependencies
> - Keeps AES-128-CBC signing in `creator_signing.py` (depends on pycryptodome)
> - In the Minis environment, cookies are automatically retrieved through `browser_use get_cookies`

---

## File Structure

```
/var/minis/skills/xiaohongshu-hub/
├── SKILL.md
├── pyproject.toml          # UV project configuration (httpx + pycryptodome only)
└── scripts/
    ├── __init__.py
    ├── constants.py        # Constants (Host, UA, SDK version, etc.)
    ├── exceptions.py       # Structured exceptions (6 error types)
    ├── signing.py          # Main API signing (x-s / x-s-common / x-t), standard library only
    ├── creator_signing.py  # Creator API signing (AES-128-CBC)
    └── client.py           # XhsClient core class (all API methods)
```

---

## Authentication Methods

The Xiaohongshu Web API uses three key cookies:

| Cookie | Description |
|--------|-------------|
| `a1` | User identity identifier and core signing algorithm parameter (required) |
| `web_session` | Login session (required) |
| `webId` | Device ID (recommended) |

### Method 1: Automatically Retrieve with `browser_use` (Preferred in the Minis Environment)

In Minis, you can use the `browser_use` tool to navigate to Xiaohongshu, then use `get_cookies` to read the cookies automatically.
**Raw Cookie values will not appear in the conversation**. They are passed securely through an offload env file.

Steps:
1. Use `browser_use navigate` to open `https://www.xiaohongshu.com` and confirm that you are logged in.
2. Use `browser_use get_cookies` to retrieve `a1`, `web_session`, and `webId` separately.
   - The tool returns an offload env file path, such as `/var/minis/offloads/env_cookies_xxx.sh`.
   - Raw Cookie values do not appear in the conversation context.
3. Load the env file before use:

```bash
. /var/minis/offloads/env_cookies_xxx.sh
# The file exports variables such as COOKIE_A1 / COOKIE_WEB_SESSION / COOKIE_WEBID
export XHS_A1="$COOKIE_A1"
export XHS_WEB_SESSION="$COOKIE_WEB_SESSION"
export XHS_WEBID="$COOKIE_WEBID"
```

> **Note**: `get_cookies` only applies to the current page's domain. Navigate to `https://www.xiaohongshu.com` before calling it.

### Method 2: Manually Retrieve Cookies from Browser DevTools

1. Log in to Xiaohongshu and open DevTools -> Application -> Cookies -> `https://www.xiaohongshu.com`.
2. Find the values for `a1`, `web_session`, and `webId`.
3. Save them to Minis environment variables (Settings -> Environments): `XHS_A1` / `XHS_WEB_SESSION` / `XHS_WEBID`.

### Ways to Pass Cookies (Three Methods, Highest to Lowest Priority)

1. **Environment variables**: `XHS_A1` + `XHS_WEB_SESSION` + `XHS_WEBID` (recommended)
2. **Pass directly in code**: `XhsClient({"a1": ..., "web_session": ..., "webId": ...})`
3. **Script arguments**: Pass through arguments such as `-a1` / `--web-session`

---

## Quick Start

### Set Up the Environment

```bash
cd /var/minis/skills/xiaohongshu-hub
uv sync
```

### Call as a Python Library (Recommended)

```python
import os, json, sys
sys.path.insert(0, "/var/minis/skills/xiaohongshu-hub")
from scripts.client import XhsClient

# Method 1: Build from environment variables (recommended)
client = XhsClient.from_env()

# Method 2: Pass a Cookie dict directly
client = XhsClient({
    "a1":          os.environ["XHS_A1"],
    "web_session": os.environ["XHS_WEB_SESSION"],
    "webId":       os.environ["XHS_WEBID"],
})

with client:
    # Current user information
    me = client.get_self_info()
    print("User:", me.get("nickname"))

    # Search notes
    results = client.search_notes("Food", page=1)
    for item in results.get("items", [])[:5]:
        note = item.get("note_card", {})
        print(f"  - {note.get('display_title', '')}")

    # Recommendation feed
    feed = client.get_home_feed()
    print(f"Recommendation feed: {len(feed.get('items', []))} items")

    # Trending notes (travel)
    hot = client.get_hot_feed("homefeed.travel_v3")
    print(f"Trending travel: {len(hot.get('items', []))} items")
```

### Call Through a Script (Shell Environment)

```bash
# Search notes and output JSON
cd /var/minis/skills/xiaohongshu-hub
uv run python -c "
import os, json, sys
sys.path.insert(0, '.')
from scripts.client import XhsClient
with XhsClient.from_env() as c:
    r = c.search_notes('Travel', page=1)
    print(json.dumps(r, ensure_ascii=False, indent=2))
"

# Get current user information
uv run python -c "
import os, json, sys
sys.path.insert(0, '.')
from scripts.client import XhsClient
with XhsClient.from_env() as c:
    print(json.dumps(c.get_self_info(), ensure_ascii=False, indent=2))
"
```

---

## API Method Quick Reference

### User

| Method | Description |
|--------|-------------|
| `get_self_info()` | Get information about the currently logged-in user |
| `get_user_info(user_id)` | Get profile information for a specified user |
| `get_user_notes(user_id, cursor="")` | Get a list of notes posted by a user |

### Search

| Method | Description |
|--------|-------------|
| `search_notes(keyword, page=1, sort="general", note_type=0)` | Search notes |
| `search_users(keyword, page=1)` | Search users |
| `search_topics(keyword)` | Search topics/tags |

`sort` options: `"general"` / `"popularity_descending"` / `"time_descending"`
`note_type` options: `0` = all / `1` = video / `2` = image and text

### Notes

| Method | Description |
|--------|-------------|
| `get_note_by_id(note_id, xsec_token="")` | Get note details |
| `get_comments(note_id, cursor="", xsec_token="")` | Get comments (single page) |
| `get_all_comments(note_id, xsec_token="", max_pages=20)` | Automatically page through and get all comments |
| `get_sub_comments(note_id, comment_id, cursor="", xsec_token="")` | Get comment replies |

### Feed / Discover

| Method | Description |
|--------|-------------|
| `get_home_feed(category="homefeed_recommend")` | Recommendation feed |
| `get_hot_feed(category="homefeed.food_v3")` | Trending notes (by category) |

Trending categories: `fashion_v3` / `food_v3` / `cosmetics_v3` / `movie_and_tv_v3` /
`career_v3` / `love_v3` / `household_product_v3` / `gaming_v3` / `travel_v3` / `fitness_v3`

### Social

| Method | Description |
|--------|-------------|
| `follow_user(user_id)` | Follow a user |
| `unfollow_user(user_id)` | Unfollow |
| `get_user_favorites(user_id, cursor="")` | Get a user's favorites |

### Interaction

| Method | Description |
|--------|-------------|
| `like_note(note_id, xsec_token="")` | Like |
| `unlike_note(note_id, xsec_token="")` | Unlike |
| `collect_note(note_id, xsec_token="")` | Favorite |
| `uncollect_note(note_id, xsec_token="")` | Unfavorite |
| `post_comment(note_id, content, xsec_token="")` | Post a comment |
| `reply_comment(note_id, comment_id, content, xsec_token="")` | Reply to a comment |
| `delete_comment(note_id, comment_id)` | Delete your own comment |

### Notifications

| Method | Description |
|--------|-------------|
| `get_unread_count()` | Number of unread notifications |
| `get_notifications_mentions(cursor="")` | Comments / @ notifications |
| `get_notifications_likes(cursor="")` | Like / favorite notifications |
| `get_notifications_connections(cursor="")` | New follower notifications |

### Creator

| Method | Description |
|--------|-------------|
| `get_my_notes(page=0)` | Get a list of notes you posted |
| `delete_note(note_id)` | Delete a note (experimental) |

---

## Error Handling

```python
from scripts.exceptions import (
    NeedVerifyError,    # CAPTCHA triggered (HTTP 461/471)
    SessionExpiredError, # Cookie expired (code -100)
    IpBlockedError,     # IP blocked (code 300012)
    SignatureError,     # Signing failed (code 300015)
    XhsApiError,        # Other API errors (base class)
)

try:
    result = client.search_notes("Food")
except NeedVerifyError:
    print("A CAPTCHA was triggered. Complete verification in the browser and try again.")
except SessionExpiredError:
    print("Cookie has expired. Retrieve it again.")
except IpBlockedError:
    print("IP is blocked. Switch networks.")
except XhsApiError as e:
    print(f"API error: {e} (code={e.code})")
```

---

## Anti-Risk-Control Mechanisms

This skill inherits the complete anti-risk-control implementation from the original repository:

- **Gaussian jitter**: Uses a truncated Gaussian distribution for request intervals (not fixed intervals) to simulate natural browsing rhythms
- **Random long pauses**: About 5% of requests wait an additional 2 to 5 seconds to simulate reading behavior
- **Exponential backoff**: Automatically retries HTTP 429/5xx (up to 3 times)
- **CAPTCHA cooldown**: After a CAPTCHA is triggered, automatically waits 5 -> 10 -> 20 -> 30 seconds and permanently doubles the request interval
- **Browser fingerprint consistency**: macOS Chrome UA, with session-level GPU/resolution/CPU kept fixed
- **Complete signing**: `x-s` / `x-s-common` / `x-t` signing (reverse-engineered from the web client)

---

## Notes

- Cookies are usually valid for several days to several weeks. After they expire, retrieve them again through `browser_use get_cookies`.
- Use a dedicated account to avoid risk-control flags on your main account.
- Write operations (comments, likes, etc.) carry a higher risk-control risk than read operations. Use them with discretion.
- `get_all_comments` pages through up to 20 pages by default. You can adjust this with `max_pages`.
