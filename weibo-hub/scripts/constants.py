"""Constants for weibo-hub — API endpoints, headers, config paths."""

from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────
DATA_DIR = Path("/var/minis/workspace/weibo-hub")
CREDENTIAL_FILE = DATA_DIR / "credential.json"
CREDENTIAL_TTL_DAYS = 7

# ── Base URLs ────────────────────────────────────────────────────────
BASE_URL = "https://weibo.com"
MOBILE_BASE_URL = "https://m.weibo.cn"

# ── API Endpoints ────────────────────────────────────────────────────
# Public (no auth required)
HOT_SEARCH_URL = "/ajax/side/hotSearch"
HOT_BAND_URL = "/ajax/statuses/hot_band"
SEARCH_BAND_URL = "/ajax/side/searchBand"
HOT_TIMELINE_URL = "/ajax/feed/hottimeline"
FEED_GROUPS_URL = "/ajax/feed/allGroups"

# Auth required
FRIENDS_TIMELINE_URL = "/ajax/feed/friendstimeline"
PROFILE_INFO_URL = "/ajax/profile/info"
MY_MBLOG_URL = "/ajax/statuses/mymblog"
STATUSES_SHOW_URL = "/ajax/statuses/show"
BUILD_COMMENTS_URL = "/ajax/statuses/buildComments"
REPOST_TIMELINE_URL = "/ajax/statuses/repostTimeline"
FRIENDS_URL = "/ajax/friendships/friends"
GET_CONFIG_URL = "/ajax/config/get_config"

# Mobile search
MOBILE_SEARCH_URL = "/api/container/getIndex"

# ── Request Headers (Chrome 145, macOS) ──────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": f"{BASE_URL}/",
}

MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{MOBILE_BASE_URL}/",
    "X-Requested-With": "XMLHttpRequest",
}

# ── Response codes ────────────────────────────────────────────────────
REQUIRED_COOKIES = {"SUB", "SUBP"}
