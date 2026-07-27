---
name: tg-hub
description: >
  A skill for reading and writing Telegram data with Python and UV. It depends only on Telethon and uses a local-first architecture: messages are synced to
  SQLite and then queried offline. On first use, you must log in from the terminal with a phone number verification code. After that, the session is persisted and you do not need to log in again.
  Supports syncing group and channel messages locally, keyword search, multi-keyword filtering, today's messages, recent messages, speaker rankings, timeline statistics, and more.
  This skill must be triggered whenever the user mentions "Telegram", "TG", "Telegram", "tg-hub", "sync Telegram messages", "search TG groups",
  "Telegram keywords", "get TG messages", or any scenario that requires programmatically reading or writing Telegram data.
---

# tg-hub

> **Based on**: [jackwener/tg-cli](https://github.com/jackwener/tg-cli) (Apache-2.0)
>
> This skill simplifies the original repository as follows:
> - Removed the `click` / `rich` / `python-dotenv` / `pyyaml` dependencies
> - Kept only `telethon` as a third-party dependency
> - Removed the CLI layer and encapsulated all functionality as a synchronous Python API
> - Changed the default session/db path to `/var/minis/workspace/tg-hub/`
> - Changed configuration to read environment variables directly, with no `.env` file required

---

## Architecture: Local-First

```
Telegram MTProto (telethon)
    ↓  sync / refresh (incremental)
Local SQLite  ~/.tg-hub/messages.db
    ↓  search / today / recent / filter (offline)
Structured data
```

- **Read operations** (search/today/recent): query the local SQLite database, with **no network access**, and respond in milliseconds
- **Write operations** (sync/refresh): connect to Telegram to fetch new messages and write them incrementally to SQLite
- Session file: `~/.tg-hub/tg_hub.session`

---

## File Structure

```
/var/minis/skills/tg-hub/
├── SKILL.md
├── pyproject.toml          # telethon only
└── scripts/
    ├── __init__.py
    ├── config.py           # Configuration (environment variables / default paths)
    ├── db.py               # SQLite message storage
    ├── exceptions.py       # Structured exceptions
    └── client.py           # TGClient core class (all APIs)
```

---

## First-Time Login (Must Be Done in Terminal)

tg-hub uses the **MTProto protocol** (not the Bot API), so you need to log in with your Telegram account.

> **Recommendation**: Use your own `TG_API_ID` / `TG_API_HASH` whenever possible.
> I have synced the upstream tg-cli anti-risk-control implementation: it uses a Telegram Desktop 5.x fingerprint and prints a warning if you continue using the default `api_id=2040`. The public app ID is only a fallback. Using your own credentials is still recommended for long-term use.

```
1. Open Terminal
2. (Recommended) Set your own TG_API_ID / TG_API_HASH first
3. cd /var/minis/skills/tg-hub
4. uv run python -c "
   import sys; sys.path.insert(0,'.')
   from scripts.client import TGClient
   me = TGClient().login()
   print('Login successful:', me)
   "
5. Enter your phone number when prompted (in +86XXXXXXXXXX format)
6. Enter the verification code received in the Telegram app
7. After login succeeds, the session is saved automatically and future logins are not required
```

> If you do not have your own credentials for now, you can log in with the built-in public credentials first. If you encounter login or fetch errors, switch to your own APP ID first.

[Open Terminal to log in](minis://open_terminal?init_command=cd%20%2Fvar%2Fminis%2Fskills%2Ftg-hub%20%26%26%20uv%20run%20python%20-c%20%22import%20sys%3B%20sys.path.insert(0%2C'.')%3B%20from%20scripts.client%20import%20TGClient%3B%20TGClient().login()%22)

---

## Quick Start

### Environment Setup

```bash
cd /var/minis/skills/tg-hub
uv sync
```

### Python Usage

```python
import sys
sys.path.insert(0, "/var/minis/skills/tg-hub")
from scripts.client import TGClient

client = TGClient()

# View the current account
me = client.whoami()
print(me["name"], me["phone"])

# List all conversations (fetched from TG in real time)
chats = client.list_chats()
for c in chats[:10]:
    print(f"  [{c['type']}] {c['name']}  Unread: {c['unread']}")

# Incrementally sync a single group
n = client.sync("Group name or username", limit=1000)
print(f"Added {n} messages")

# Quickly refresh all groups (up to 500 new messages per group)
# Slight throttling is enabled by default; you can also limit this round to only the first 30 chats
result = client.refresh(delay=1.0, max_chats=30)
for name, count in result.items():
    if count > 0:
        print(f"  {name}: +{count}")

# Search by keyword
msgs = client.search("Python", hours=48)
for m in msgs:
    print(f"[{m['chat_name']}] {m['sender_name']}: {m['content'][:80]}")

# Multi-keyword filtering (OR logic)
msgs = client.filter("hiring,remote,part-time", hours=24)

# Today's messages
msgs = client.today()

# Messages from the last 12 hours
msgs = client.recent(hours=12, limit=200)

# Speaker rankings
top = client.top_senders(hours=24)
for t in top[:5]:
    print(f"  {t['sender_name']}: {t['msg_count']} messages")

# Timeline statistics
tl = client.timeline(granularity="hour", hours=48)

# Local database statistics
stats = client.stats()
print(f"{stats['total']} local messages across {len(stats['chats'])} groups")
```

---

## API Quick Reference

### Authentication

| Method | Description |
|------|------|
| `login()` | Interactive login (first time, requires terminal) |
| `whoami()` | Get current account information |

### Sync (Online)

| Method | Description |
|------|------|
| `list_chats(chat_type=None)` | List all conversations (real time) |
| `sync(chat, limit=5000)` | Sync a single group to local SQLite |
| `sync_all(limit_per_chat=5000, delay=1.0, max_chats=None)` | Sync all groups (with throttling/count limit) |
| `refresh(limit_per_chat=500, delay=1.0, max_chats=None)` | Quick incremental refresh (recommended for daily use) |

### Query (Local, Offline)

| Method | Description |
|------|------|
| `search(keyword, *, chat, sender, hours, regex, limit)` | Keyword/regex search |
| `filter(keywords, *, chat, hours)` | Multi-keyword OR filtering |
| `today(chat=None)` | Today's messages |
| `recent(hours=24, *, chat, sender, limit)` | Messages from the last N hours |
| `top_senders(chat, hours, limit)` | Speaker rankings |
| `timeline(chat, hours, granularity)` | Timeline statistics |
| `stats()` | Database statistics |
| `local_chats()` | List of locally synced groups |
| `delete_chat(chat)` | Delete local messages for a group |

---

## Environment Variables

| Variable | Default Value | Description |
|------|--------|------|
| `TG_API_ID` | `2040` (fallback only) | **Recommended: replace with your own** API ID |
| `TG_API_HASH` | Built in (fallback only) | **Recommended: replace with your own** API Hash |
| `TG_SESSION_NAME` | `tg_hub` | Session filename |
| `TG_DATA_DIR` | `~/.tg-hub` | Data directory |
| `TG_DB_PATH` | `{TG_DATA_DIR}/messages.db` | SQLite path |
| `TG_DEVICE_MODEL` | `Desktop` | Telethon client device model |
| `TG_SYSTEM_VERSION` | `macOS 15.3` | Telethon client system version |
| `TG_APP_VERSION` | `5.12.1` | Telethon client version |
| `TG_LANG_CODE` | `en` | Client language code |
| `TG_SYSTEM_LANG_CODE` | `en-US` | System language code |

---

## Account Security Recommendations

1. **Use your own API credentials whenever possible**: Go to `https://my.telegram.org`, create an application, and then set `TG_API_ID` / `TG_API_HASH`.
2. **Control sync frequency**: Avoid repeatedly running `refresh()` at high frequency.
3. **Use `delay` and `max_chats`**: For daily incremental refreshes, we recommend limiting the number of chats synced per round and keeping an interval between chats.
4. **Do not be too aggressive with the first full sync**: tg-hub automatically applies a lower fetch limit for the first sync of each chat.
5. **Prefer read operations**: Local queries such as search and statistics do not use the network, so they are much lower risk than frequent syncs.

---

## Notes

- The first login must be completed in an interactive terminal (a verification code is required).
- **Using your own `TG_API_ID` / `TG_API_HASH` is strongly recommended** to avoid risk-control issues caused by abuse of the public APP ID.
- tg-hub is aligned with the upstream tg-cli Telegram Desktop 5.x client fingerprint and retains environment variable overrides to reduce the risk of abnormal fingerprints.
- If you are still using the default `api_id=2040`, a warning is printed during connection to remind you to switch to your own `TG_API_ID` / `TG_API_HASH`.
- The session file is stored at `/var/minis/workspace/tg-hub/tg_hub.session`. Keep it safe.
- The first run of `sync_all` may take a long time, depending on the number of groups and the amount of historical messages.
- We recommend using `refresh()` for daily incremental updates and `sync(chat, limit=10000)` for the initial full sync.
- Telegram applies rate limits to API requests. During large syncs, Telethon automatically handles flood waits.
