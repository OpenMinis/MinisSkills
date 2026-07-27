---
name: weibo-hub
description: >
  A skill for reading and writing Weibo data with Python + UV. It depends only on httpx and uses `browser_use get_cookies`
  to automatically retrieve cookies and complete authentication, with no manual copying required. It supports trending searches, popular feeds, following feeds, keyword search,
  Weibo post details/comments/reposts, user profiles/posts/following/follower lists, and more.
  This skill must be triggered whenever the user mentions "Weibo", "weibo", "weibo-hub", "Weibo trending searches", "scraping Weibo", "searching Weibo",
  "Weibo comments", "Weibo users", or any scenario that requires programmatic reading or writing of Weibo data.
---

# weibo-hub

> **Adapted from**: [jackwener/weibo-cli](https://github.com/jackwener/weibo-cli) (Apache-2.0)
>
> This skill streamlines the original repository as follows:
> - **Removed** the `click` / `rich` / `browser-cookie3` / `qrcode` / `pyyaml` dependencies
> - **Kept only** `httpx` as a third-party dependency
> - **Removed** the CLI layer; all functionality is encapsulated as a synchronous Python API
> - **Changed authentication to** extracting cookies with `browser_use get_cookies`, then calling `setup_credential()` to save them
> - Changed the data directory to `/var/minis/workspace/weibo-hub/`

---

## File Structure

```
/var/minis/skills/weibo-hub/
├── SKILL.md
├── pyproject.toml          # httpx only
└── scripts/
    ├── __init__.py
    ├── constants.py        # API endpoints, headers, and path constants
    ├── exceptions.py       # WeiboError exception hierarchy
    ├── auth.py             # Credential persistence (no browser-cookie3)
    └── client.py           # WeiboClient core class (all APIs)
```

---

## Authentication Flow (Check Before Each Use)

weibo-hub uses **browser cookie authentication**, extracted from weibo.com with `browser_use get_cookies`.
It does not require `browser-cookie3` or QR code scanning.

### Step 1: Use `browser_use` to Extract Cookies

```python
# Call in the agent:
browser_use(action="navigate", url="https://weibo.com")
# After confirming you are logged in:
browser_use(action="get_cookies", url="https://weibo.com")
# Record the returned offload env file path
```

### Step 2: Read and Save Credentials from the env File

```python
import sys, os, subprocess, json

# Load Cookie environment variables (the path comes from the offload file returned by get_cookies)
env_file = "/var/minis/offloads/env_cookies_xxx.sh"   # Replace with the actual path
result = subprocess.run(
    f". {env_file} && python3 -c \"import os,json; print(json.dumps(dict(os.environ)))\"",
    shell=True, capture_output=True, text=True
)
env = json.loads(result.stdout)

# Parse the Cookie dictionary (variables with the COOKIE_ prefix)
cookies = {
    k[len("COOKIE_"):]: v
    for k, v in env.items()
    if k.startswith("COOKIE_")
}

# Save credentials
sys.path.insert(0, "/var/minis/skills/weibo-hub")
from scripts.client import WeiboClient
WeiboClient.setup_credential(cookies)
```

> **Required Cookies**: `SUB`, `SUBP` (required). The more additional cookies, the better.
> Credentials are saved to `/var/minis/workspace/weibo-hub/credential.json`, valid for 7 days, and an expiration prompt is shown automatically when they expire.

---

## Environment Setup

```bash
cd /var/minis/skills/weibo-hub
uv sync
```

---

## Quick Start

```python
import sys
sys.path.insert(0, "/var/minis/skills/weibo-hub")
from scripts.client import WeiboClient

with WeiboClient() as client:

    # ── Trending searches / trends (no login required)──────────────────────────────
    topics = client.hot_search()          # Trending search list (~52 entries)
    for t in topics[:10]:
        print(f"#{t.get('realtime_hot_show_label','')} {t.get('word','')}")

    band = client.hot_band()              # Full trending search list
    trends = client.trending()            # Real-time search suggestions

    # ── Feeds (popular requires no login; following requires login)─────────────────────
    hot = client.hot_feed(count=10)       # Popular timeline
    home = client.home_feed(count=20)     # Following timeline

    # ── Search (mobile API)────────────────────────────────────
    results = client.search("Artificial Intelligence", page=1)
    for w in results[:5]:
        print(w.get("text", "")[:80])

    # ── Weibo post details / comments / reposts (login required)──────────────────
    wb = client.detail("Qw06Kd98p")
    cmt = client.comments("WeiboID", count=20)
    rep = client.reposts("WeiboID", count=10)

    # ── Users (login required)─────────────────────────────────────
    me = client.me()                      # Currently logged-in user
    user = client.profile("1699432410")   # Specified user profile
    weibos = client.user_weibos("1699432410", page=1)
    following = client.following("1699432410", page=1)
    followers = client.followers("1699432410", page=1)
```

---

## API Quick Reference

### No Login Required (Public APIs)

| Method | Description |
|------|------|
| `hot_search()` | Trending search sidebar (~52 entries) |
| `hot_band()` | Full trending search list |
| `trending()` | Real-time search suggestions |
| `hot_feed(count, max_id)` | Popular timeline |
| `search(keyword, page)` | Keyword search for Weibo posts |

### Login Required (Cookie Authentication)

| Method | Description |
|------|------|
| `me()` | Current logged-in user information |
| `home_feed(count, max_id)` | Following timeline |
| `detail(mblogid)` | Details for a single Weibo post |
| `comments(weibo_id, count, max_id)` | Weibo comment list |
| `reposts(weibo_id, page, count)` | Weibo repost list |
| `profile(uid)` | User profile |
| `user_weibos(uid, page, count)` | User's Weibo post list |
| `following(uid, page)` | User following list |
| `followers(uid, page)` | User follower list |

### Authentication

| Method | Description |
|------|------|
| `WeiboClient.setup_credential(cookies)` | Save Cookie credentials (static method) |

---

## Anti-Abuse Notes

Consistent with the upstream weibo-cli:
- **Gaussian jitter**: Interval between requests = `request_delay + gauss(0.3, 0.15)`, about 1 s
- **5% long pause**: Randomly triggers an additional 2-5 s delay to simulate reading behavior
- **Exponential backoff**: HTTP 429/5xx retries up to 3 times, with a wait time of 2^n seconds
- **Chrome 145 UA**: Desktop User-Agent, consistent with the browser fingerprint

---

## Notes

- Before first use, you must call `WeiboClient.setup_credential(cookies)` to save credentials
- Credential file: `/var/minis/workspace/weibo-hub/credential.json`, permissions 0600
- Required Cookies: `SUB` + `SUBP`; if missing, `setup_credential()` throws `ValueError`
- Cookies automatically prompt as expired after 7 days and must be extracted again
- Trending searches, popular feeds, and search do not require login; `profile`, `detail`, `home_feed`, and similar methods require valid cookies
- `search()` uses the mobile API (`m.weibo.cn`), and the result format is slightly different
