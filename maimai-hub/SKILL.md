---
name: maimai-hub
description: Retrieves data from the Colleague Circle and Career Insights sections of Maimai (maimai.cn). Supports: posts from a specific company's Colleague Circle, the site-wide Career Insights feed (hot/latest/following), the Colleague Circle popularity ranking, and looking up a webcid by company name. This skill must be triggered whenever the user mentions "Maimai," "Colleague Circle," "Career Insights," "maimai," "maimai-hub," or any scenario that requires reading Maimai content.
---

# maimai-hub

## Authentication Process

Before each use, retrieve the latest cookies with `browser_use get_cookies`. **This must be done on the desktop version of the page** because the mobile version does not include `csrftoken`:

```
1. browser_use set_user_agent → desktop_safari
2. browser_use navigate → https://maimai.cn/web/search_center
3. browser_use get_cookies → save to env file
4. Confirm that the env file contains COOKIE_CSRFTOKEN (otherwise, retry steps 2-3)
```

Example ENV file path: `/var/minis/offloads/env_cookies_maimai_cn_XXXXXXXX.sh`

## Colleague Circle Fallback Plan (When the API Is Unavailable)

When the script returns an empty array or HTTP 404, automatically switch to **reading the page content directly in the browser**:

```
Colleague Circle page URL format:
https://maimai.cn/company/gossip_discuss?webcid=<WEBCID>

Note: The old paths /web/gossip_discuss and /community/gossip_discuss now both return 404.
You must use /company/gossip_discuss.
```

**Fallback steps:**
```
1. browser_use navigate → https://maimai.cn/company/gossip_discuss?webcid=<WEBCID>
2. Scroll multiple times to load more content (scroll down × 4~6, 800px each time)
3. Extract post text with browser_use get_readable or execute_js:
   document.querySelectorAll('[class*="content"],[class*="text"],[class*="body"]')
   Filter criteria: length 15~800, exclude noise such as "Maimai", "illegal", and "Colleague Circle popularity"
4. Deduplicate the extracted results, then compile and summarize them
```

## Script Invocation

Script: `/var/minis/skills/maimai-hub/scripts/maimai.py`

```bash
# Colleague Circle posts (must be an employee of that company)
python3 /var/minis/skills/maimai-hub/scripts/maimai.py gossip_circle \
  --webcid 9AG14xzt --count 20 --env <ENV_FILE>

# Look up a Colleague Circle by company name (automatically finds webcid)
python3 /var/minis/skills/maimai-hub/scripts/maimai.py gossip_circle \
  --company Ant Group --count 20 --env <ENV_FILE>

# Site-wide Career Insights feed
python3 /var/minis/skills/maimai-hub/scripts/maimai.py gossip_feed \
  --tab hot --count 20 --env <ENV_FILE>
  # tab: hot(Trending) | new(Latest) | follow(Following) | recommend(Recommended)

# Colleague Circle popularity ranking (gets popular company webcids)
python3 /var/minis/skills/maimai-hub/scripts/maimai.py circle_rank \
  --env <ENV_FILE>

# Look up webcid by company name
python3 /var/minis/skills/maimai-hub/scripts/maimai.py search_company \
  --name ByteDance --env <ENV_FILE>
```

## How to Obtain the webcid

Priority:
1. **URL provided by the user** → extract with regex: `webcid=([A-Za-z0-9]+)`
2. **Current user's company** → visit `https://maimai.cn/web/search_center`, then execute JS:
   ```js
   window.share_data.data.mycard.web_cid  // returns the webcid directly; .company is the full company name
   ```
3. **Company name matching** → built-in script cache + dynamic ranking lookup (`circle_rank` command)

Colleague Circle page URL (for browser fallback): `https://maimai.cn/company/gossip_discuss?webcid=<WEBCID>`

Built-in webcid cache (major tech companies):

| Company | webcid |
|------|--------|
| ByteDance | jYZTTwkX |
| Pinduoduo | 1cDwhLvjW |
| Tencent | 167PEUToR |
| Alibaba | EnT6guJz |
| Ant Group | 9AG14xzt |
| Baidu | mWqfo5EX |
| Meituan | 5DDx3ANi |
| Xiaomi | KvzN4IGA |
| JD.com | SJdjsQ5S |
| Kuaishou | RO3MvtaT |

## Permissions

- **Colleague Circle**: Access is limited to employees of that company. `error_code: 21003` indicates no permission.
- **Site-wide Career Insights**: Accessible to all logged-in users.
- **Ranking**: Accessible to all logged-in users.

## Output Format

The script returns JSON. Fields for each post: `id, time, text, likes, cmts, spreads, ip_loc`

When summarizing, sort by engagement (likes + cmts), identify the main topics, and do not list the original text item by item.

## Frequently Asked Questions

- **Returns an empty array**: No permission for the Colleague Circle (not an employee of that company). Switch to site-wide Career Insights.
- **Missing csrftoken**: Make sure to access the site with a desktop UA before calling `get_cookies`.
- **Cannot find the webcid for a company name**: Ask the user to provide the Colleague Circle URL directly (`https://maimai.cn/company/gossip_discuss?webcid=xxx`).
- **API returns empty / 404**: Automatically switch to the browser fallback plan. See the "Colleague Circle Fallback Plan (When the API Is Unavailable)" section.
