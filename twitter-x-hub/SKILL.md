---
name: twitter-x-hub
description: >
  Skill for reading and writing Twitter/X data with Python + UV, with zero third-party dependencies (pure standard library), by directly passing
  the auth_token + ct0 cookies for authentication. In the Minis environment, cookies can be retrieved automatically with the browser_use tool
  by navigating to x.com and then using the get_cookies action, with no manual copying required. Supports scraping the home timeline, following list,
  bookmarks (including bookmark folders), search, user profiles, user tweets, likes, tweet details (single tweet or with replies), List timelines,
  followers/following lists, and write operations such as posting, deleting, liking, retweeting, and bookmarking. This skill must be triggered when the user mentions "scraping Twitter data,"
  "get X tweets," "Twitter timeline," "X bookmarks," "search tweets," "twitter-x-hub,"
  "request Twitter with cookies," "Twitter GraphQL," or any scenario that requires programmatic reading or writing of Twitter/X
  data.
---

# twitter-x-hub

> **Modified from**: [public-clis/twitter-cli](https://github.com/public-clis/twitter-cli) (formerly jackwener/twitter-cli)
> This skill simplifies the original repository as follows: it removes the `browser-cookie3`/`rich`/`click`/`PyYAML`/`curl_cffi`/
> `xclienttransaction`/`beautifulsoup4` dependencies and replaces them with a pure standard library implementation; authentication now uses directly supplied cookies
> instead of automatic browser extraction; Twitter Article rendering and image upload functionality have been removed.

---

## File Structure

```
/var/minis/skills/twitter-x-hub/
├── SKILL.md
├── pyproject.toml              # UV project configuration (zero third-party dependencies)
└── scripts/
    ├── __init__.py
    ├── models.py               # Data models (Tweet, Author, Metrics, UserProfile, BookmarkFolder)
    ├── parser.py               # GraphQL response parsing (split from client.py, synced from upstream v0.8.6)
    ├── client.py               # GraphQL client (core logic)
    └── cli.py                  # Command-line entry point (argparse)
```

---

## Authentication

The Twitter/X internal GraphQL API uses two cookies for authentication:

| Cookie | Description |
|--------|-------------|
| `auth_token` | User login credential (OAuth Session Token) |
| `ct0` | CSRF Token, also used as the `X-Csrf-Token` request header |

### Method 1: Retrieve automatically with the `browser_use` tool (recommended, preferred in the Minis environment)

In Minis, you can use the `browser_use` tool to navigate directly to x.com, then use the `get_cookies` action to read cookies,
with no manual copying required. **After retrieval, store them in environment variables immediately** to avoid exposing plaintext values in the conversation context.

Steps:
1. Use `browser_use navigate` to open `https://x.com` and confirm you are logged in.
2. Use `browser_use get_cookies` to retrieve all cookies.
   - The tool returns an offload env file path, such as `/var/minis/offloads/env_cookies_xxx.sh`.
   - **Raw cookie values will not appear in the conversation.**
3. Load the file, then use the cookies:
```bash
. /var/minis/offloads/env_cookies_xxx.sh
export TWITTER_AUTH_TOKEN="$COOKIE_AUTH_TOKEN"
export TWITTER_CT0="$COOKIE_CT0"
```

### Method 2: Set environment variables manually

Copy `auth_token` and `ct0` from browser DevTools -> Application -> Cookies -> `https://x.com`,
then store them in Minis environment variables (Settings -> Environments): `TWITTER_AUTH_TOKEN` + `TWITTER_CT0`

### Passing credentials (three methods, in descending priority)

1. Environment variables: `TWITTER_AUTH_TOKEN` + `TWITTER_CT0` (recommended)
2. CLI parameters: `--auth-token <value> --ct0 <value>`
3. Pass directly in code: `TwitterClient(auth_token=..., ct0=...)`

---

## Quick Start

### Environment Setup

```bash
# Confirm UV is available
which uv || pip install uv

# Enter the skill directory
cd /var/minis/skills/twitter-x-hub
```

### CLI Usage

```bash
# Scrape the home For-You timeline (20 items by default)
uv run python -m scripts.cli feed

# Scrape the Following timeline, 30 items, JSON output
uv run python -m scripts.cli feed --type following --max 30 --json

# Search tweets (Top/Latest/Photos/Videos)
uv run python -m scripts.cli search "Claude Code" --tab Latest --max 20

# Bookmarks
uv run python -m scripts.cli bookmarks --max 50

# Bookmark folder list (new)
uv run python -m scripts.cli bookmark-folders

# User profile
uv run python -m scripts.cli user elonmusk

# User tweets
uv run python -m scripts.cli user-posts elonmusk --max 20

# User likes
uv run python -m scripts.cli user-likes elonmusk --max 20

# Tweet details (including reply thread)
uv run python -m scripts.cli tweet 1234567890

# Quickly retrieve a single tweet (new, faster than the tweet command)
uv run python -m scripts.cli tweet-by-id 1234567890

# List timeline
uv run python -m scripts.cli list 1539453138322673664

# Followers / following lists (first use the user command to get user_id)
uv run python -m scripts.cli followers <user_id> --max 50
uv run python -m scripts.cli following <user_id> --max 50

# Post a tweet / reply
uv run python -m scripts.cli post "Hello from twitter-x-hub!"
uv run python -m scripts.cli post "reply text" --reply-to 1234567890

# Like / retweet / bookmark
uv run python -m scripts.cli like 1234567890
uv run python -m scripts.cli retweet 1234567890
uv run python -m scripts.cli bookmark 1234567890
```

### Use environment variables to avoid passing credentials each time

```bash
export TWITTER_AUTH_TOKEN="xxxx"
export TWITTER_CT0="yyyy"

uv run python -m scripts.cli feed --max 30 --json
```

### Call as a Python library

```python
import os, json, dataclasses
from scripts.client import TwitterClient

client = TwitterClient(
    auth_token=os.environ["TWITTER_AUTH_TOKEN"],
    ct0=os.environ["TWITTER_CT0"],
)

# Scrape the home timeline
tweets = client.fetch_home_timeline(count=20)
for t in tweets:
    print(f"@{t.author.screen_name}: {t.text[:80]}")
    print(f"  ❤️ {t.metrics.likes}  🔁 {t.metrics.retweets}  👁 {t.metrics.views}  🔖 {t.metrics.bookmarks}")

# Search (Latest tab)
results = client.fetch_search("AI agent", count=10, product="Latest")

# Single tweet (quick, no replies)
tweet = client.fetch_tweet_by_id("1234567890")

# Bookmark folders
folders = client.fetch_bookmark_folders()

# User profile
user = client.fetch_user("elonmusk")
print(user.id, user.followers_count)

# JSON serialization
data = [dataclasses.asdict(t) for t in tweets]
print(json.dumps(data, ensure_ascii=False, indent=2))
```

---

## Core Implementation Principles

### Authentication Mechanism
Uses browser cookies (`auth_token` + `ct0`) plus a hard-coded public Bearer Token
to impersonate a Chrome browser request to Twitter's internal GraphQL API.

### Three-level QueryId resolution (automatically handles API changes)
```
1. In-memory cache (fastest)
2. Hard-coded FALLBACK_QUERY_IDS (constant fallback)
   → If 404, the queryId has expired; proceed to the next level
3. Fetch the latest queryId from github.com/fa0311/twitter-openapi
   → If it is still unavailable, scan the x.com JS Bundle and extract it with a regular expression
```

### URL Optimization (synced from upstream v0.8)
- Keys with a value of `False` in the `features` dictionary are not sent, avoiding overly long URLs (414 errors).

### Pagination & Rate Limiting
- Each response includes a `cursor`; pages are fetched automatically until the `count` limit is reached.
- The default request interval is 1.5 seconds + ±30% random jitter. HTTP 429 triggers exponential backoff and retry.
- Write operations use a random delay of 1.5 to 4 seconds.

### Parser Split (synced from upstream v0.7+)
- `parser.py` was split out from `client.py` and includes independent functions such as `parse_tweet_result`, `parse_timeline_response`,
  and `parse_user_result`, making unit testing and reuse easier.

---

## CLI Subcommand Quick Reference

| Subcommand | Description | Key Parameters |
|------------|-------------|----------------|
| `feed` | Home timeline | `--type for-you\|following`, `--max`, `--json` |
| `bookmarks` | Bookmarks | `--max`, `--json` |
| `bookmark-folders` | Bookmark folder list ⭐ New | `--json` |
| `search` | Search | `query`, `--tab Top\|Latest\|Photos\|Videos`, `--max`, `--json` |
| `user` | User profile | `screen_name`, `--json` |
| `user-posts` | User tweets | `screen_name`, `--max`, `--json` |
| `user-likes` | User likes | `screen_name`, `--max`, `--json` |
| `tweet` | Tweet details + replies | `tweet_id`, `--max`, `--json` |
| `tweet-by-id` | Single tweet (quick) ⭐ New | `tweet_id`, `--json` |
| `list` | List timeline | `list_id`, `--max`, `--json` |
| `followers` | Followers list | `user_id`, `--max`, `--json` |
| `following` | Following list | `user_id`, `--max`, `--json` |
| `post` | Post a tweet | `text`, `--reply-to` |
| `delete` | Delete a tweet | `tweet_id` |
| `like` / `unlike` | Like/unlike | `tweet_id` |
| `retweet` / `unretweet` | Retweet/unretweet | `tweet_id` |
| `bookmark` / `unbookmark` | Bookmark/unbookmark | `tweet_id` |

All subcommands support the `--auth-token` / `--ct0` parameters, which can also be replaced with environment variables.

---

## Change Log (synced from upstream)

### v0.8.6 Sync (2026-04-08)
- **Full QueryId update**: Real-time scanning from the x.com JS bundle (main.0e98bc8a.js) updated
  all IDs, including HomeTimeline, HomeLatestTimeline, UserTweets, SearchTimeline, Likes, TweetDetail,
  TweetResultByRestId, ListLatestTweetsTimeline, Followers, Following, CreateTweet, and others.
- **New QueryIds**: `TweetResultByRestId`, `BookmarkFoldersSlice`, `BookmarkFolderTimeline`
- **New commands**: `tweet-by-id` (quick single-tweet retrieval), `bookmark-folders` (bookmark folders)
- **models.py**: Added the `bookmarks` field to `Metrics`; added the `article_title`,
  `article_text`, and `is_subscriber_only` fields to `Tweet`; added the `BookmarkFolder` dataclass.
- **parser.py**: Split from `client.py` into an independent module; fixed the new API structure (`core.name`/`core.screen_name`);
  `parse_tweet_result` supports full text from `note_tweet` (long tweets with "Show more");
  added `_unwrap_visibility` to handle `TweetWithVisibilityResults`;
  fixed `parse_user_result` so the `joined` date is read from `core.created_at`.
- **URL optimization**: `False` values in `features` are not sent, avoiding 414 errors.
- **SearchTimeline restriction**: Starting in late 2025, X requires the `x-client-transaction-id` header.
  This header is generated by `xclienttransaction` (a C extension), which cannot be installed in the iSH/Alpine environment.
  Therefore, the `search` command is temporarily unavailable in this environment. Alternative: use `browser_use` to navigate to the search page and extract the DOM.

---

## Notes

- Cookies are typically valid for several weeks to several months. After they expire, they must be retrieved from the browser again.
- Use a dedicated secondary account to reduce the risk of your main account being flagged by risk controls.
- Write operations, such as posting tweets and liking tweets, carry a higher risk of triggering risk controls than read operations. Use them at your discretion.
- `max_count` has a hard limit of 500 to prevent accidentally sending a large number of requests.
- Upstream uses `curl_cffi` for TLS fingerprint spoofing. This skill uses stdlib `urllib` instead.
  If you encounter risk controls, you can try passing the complete cookie string through the `cookie_string` parameter to strengthen the fingerprint.
