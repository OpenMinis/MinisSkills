"""Twitter/X internal GraphQL API client.

Adapted from https://github.com/jackwener/twitter-cli
Changes:
  - Removed browser-cookie3 dependency; auth_token + ct0 must be passed directly.
  - Removed optional xclienttransaction / requests / beautifulsoup4 dependencies.
  - Removed rich/click/PyYAML; zero third-party dependencies (stdlib only).
  - Simplified to pure fetch logic usable as a library or via cli.py.
"""

from __future__ import annotations

import json
import logging
import math
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .models import Author, Metrics, Tweet, TweetMedia, UserProfile

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

# Public Bearer Token embedded in Twitter's web JS (shared by all browser sessions).
# Source: https://github.com/jackwener/twitter-cli/blob/main/twitter_cli/constants.py
BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

SEC_CH_UA = '"Chromium";v="133", "Not(A:Brand";v="99", "Google Chrome";v="133"'
SEC_CH_UA_MOBILE = "?0"
SEC_CH_UA_PLATFORM = '"macOS"'

# Fallback queryIds for known GraphQL operations.
# These can go stale when Twitter rotates them; live-lookup kicks in on 404.
# Source: https://github.com/jackwener/twitter-cli/blob/main/twitter_cli/client.py
FALLBACK_QUERY_IDS: Dict[str, str] = {
    "HomeTimeline":             "c-CzHF1LboFilMpsx4ZCrQ",
    "HomeLatestTimeline":       "BKB7oi212Fi7kQtCBGE4zA",
    "Bookmarks":                "VFdMm9iVZxlU6hD86gfW_A",
    "UserByScreenName":         "1VOOyvKkiI3FMmkeDNxM9A",
    "UserTweets":               "E3opETHurmVJflFsUBVuUQ",
    "SearchTimeline":           "nWemVnGJ6A5eQAR5-oQeAg",
    "Likes":                    "lIDpu_NWL7_VhimGGt0o6A",
    "TweetDetail":              "xd_EMdYvB9hfZsZ6Idri0w",
    "ListLatestTweetsTimeline": "RlZzktZY_9wJynoepm8ZsA",
    "Followers":                "IOh4aS6UdGWGJUYTqliQ7Q",
    "Following":                "zx6e-TLzRkeDO_a7p4b3JQ",
    "CreateTweet":              "IID9x6WsdMnTlXnzXGq8ng",
    "DeleteTweet":              "VaenaVgh5q5ih7kvyVjgtg",
    "FavoriteTweet":            "lI07N6Otwv1PhnEgXILM7A",
    "UnfavoriteTweet":          "ZYKSe-w7KEslx3JhSIk5LA",
    "CreateRetweet":            "ojPdsZsimiJrUGLR1sjUtA",
    "DeleteRetweet":            "iQtK4dl5hBmXewYZuEOKVw",
    "CreateBookmark":           "aoDbu3RHznuiSkQ9aNM67Q",
    "DeleteBookmark":           "Wlmlj2-xzyS1GN3a6cj-mQ",
}

# Community-maintained live queryId source (fallback when hardcoded IDs expire).
TWITTER_OPENAPI_URL = (
    "https://raw.githubusercontent.com/fa0311/twitter-openapi/"
    "main/src/config/placeholder.json"
)

# GraphQL features flags sent with every timeline request.
FEATURES: Dict[str, Any] = {
    "rweb_video_screen_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "communities_web_enable_tweet_community_results_fetch": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
    "verified_phone_label_enabled": False,
    "premium_content_api_read_enabled": False,
}

_ABSOLUTE_MAX_COUNT = 500

# Module-level queryId cache (single-threaded CLI; no locking needed).
_cached_query_ids: Dict[str, str] = {}
_bundles_scanned = False

# Shared SSL context — avoids re-reading CA certs on every request.
_SSL_CTX = ssl.create_default_context()


# ── QueryId resolution ───────────────────────────────────────────────────────

def _url_fetch(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    req = urllib.request.Request(url)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as r:
        return r.read().decode("utf-8")


def _fetch_from_github(operation_name: str) -> Optional[str]:
    """Try to fetch a fresh queryId from the community-maintained openapi file."""
    try:
        data = json.loads(_url_fetch(TWITTER_OPENAPI_URL))
        qid = data.get(operation_name, {}).get("queryId")
        return qid if isinstance(qid, str) and qid else None
    except Exception as exc:
        logger.debug("GitHub queryId lookup failed: %s", exc)
        return None


def _scan_bundles() -> None:
    """Scan x.com JS bundles and populate _cached_query_ids."""
    global _bundles_scanned
    if _bundles_scanned:
        return
    _bundles_scanned = True
    try:
        html = _url_fetch("https://x.com", {"user-agent": USER_AGENT})
        urls = re.findall(
            r'(?:src|href)=["\']'
            r'(https://abs\.twimg\.com/responsive-web/client-web[^"\']+\.js)'
            r'["\']',
            html,
        )
    except Exception as exc:
        logger.warning("Bundle scan failed: %s", exc)
        return
    for url in urls:
        try:
            bundle = _url_fetch(url)
            for m in re.finditer(
                r'queryId:\s*"([A-Za-z0-9_-]+)"[^}]{0,200}operationName:\s*"([^"]+)"',
                bundle,
            ):
                _cached_query_ids.setdefault(m.group(2), m.group(1))
        except Exception:
            continue
    logger.info("Bundle scan complete — cached %d queryIds", len(_cached_query_ids))


def _resolve_query_id(operation_name: str, prefer_fallback: bool = True) -> str:
    if (cached := _cached_query_ids.get(operation_name)):
        return cached
    fallback = FALLBACK_QUERY_IDS.get(operation_name)
    if prefer_fallback and fallback:
        _cached_query_ids[operation_name] = fallback
        return fallback
    if (live := _fetch_from_github(operation_name)):
        _cached_query_ids[operation_name] = live
        return live
    _scan_bundles()
    if (cached := _cached_query_ids.get(operation_name)):
        return cached
    if fallback:
        _cached_query_ids[operation_name] = fallback
        return fallback
    raise RuntimeError(f'Cannot resolve queryId for "{operation_name}"')


def _invalidate_query_id(operation_name: str) -> None:
    _cached_query_ids.pop(operation_name, None)


# ── URL builder ──────────────────────────────────────────────────────────────

def _build_graphql_url(
    query_id: str,
    operation_name: str,
    variables: Dict[str, Any],
    features: Dict[str, Any],
    field_toggles: Optional[Dict[str, Any]] = None,
) -> str:
    url = (
        f"https://x.com/i/api/graphql/{query_id}/{operation_name}"
        f"?variables={urllib.parse.quote(json.dumps(variables, separators=(',', ':')))}"
        f"&features={urllib.parse.quote(json.dumps(features, separators=(',', ':')))}"
    )
    if field_toggles:
        url += f"&fieldToggles={urllib.parse.quote(json.dumps(field_toggles, separators=(',', ':')))}"
    return url


# ── Helpers ──────────────────────────────────────────────────────────────────

def _deep_get(data: Any, *keys: Any) -> Any:
    cur = data
    for key in keys:
        if isinstance(key, int):
            cur = cur[key] if isinstance(cur, list) and 0 <= key < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def _extract_cursor(content: Dict[str, Any]) -> Optional[str]:
    return content.get("value") if content.get("cursorType") == "Bottom" else None


def _extract_media(legacy: Dict[str, Any]) -> List[TweetMedia]:
    media = []
    for item in _deep_get(legacy, "extended_entities", "media") or []:
        mtype = item.get("type", "")
        if mtype == "photo":
            media.append(TweetMedia(
                type="photo",
                url=item.get("media_url_https", ""),
                width=_deep_get(item, "original_info", "width"),
                height=_deep_get(item, "original_info", "height"),
            ))
        elif mtype in {"video", "animated_gif"}:
            variants = [v for v in item.get("video_info", {}).get("variants", [])
                        if v.get("content_type") == "video/mp4"]
            variants.sort(key=lambda v: v.get("bitrate", 0), reverse=True)
            media.append(TweetMedia(
                type=mtype,
                url=variants[0]["url"] if variants else item.get("media_url_https", ""),
                width=_deep_get(item, "original_info", "width"),
                height=_deep_get(item, "original_info", "height"),
            ))
    return media


def _extract_author(user_data: Dict[str, Any], user_legacy: Dict[str, Any]) -> Author:
    core = user_data.get("core", {})
    return Author(
        id=user_data.get("rest_id", ""),
        name=core.get("name") or user_legacy.get("name") or "Unknown",
        screen_name=core.get("screen_name") or user_legacy.get("screen_name") or "unknown",
        profile_image_url=(
            user_data.get("avatar", {}).get("image_url")
            or user_legacy.get("profile_image_url_https", "")
        ),
        verified=bool(user_data.get("is_blue_verified") or user_legacy.get("verified", False)),
    )


# ── Error type ───────────────────────────────────────────────────────────────

class TwitterAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


# ── Main client ──────────────────────────────────────────────────────────────

class TwitterClient:
    """Twitter/X GraphQL client.

    Auth is provided directly as ``auth_token`` and ``ct0`` (the two cookies
    Twitter's web app uses). Obtain them from your browser's DevTools or a
    cookie-export extension — this library does NOT extract them automatically.

    Adapted from https://github.com/jackwener/twitter-cli
    """

    def __init__(
        self,
        auth_token: str,
        ct0: str,
        request_delay: float = 1.5,
        max_retries: int = 3,
        retry_base_delay: float = 5.0,
        max_count: int = 200,
    ) -> None:
        self._auth_token = auth_token
        self._ct0 = ct0
        self._request_delay = request_delay
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._max_count = min(max_count, _ABSOLUTE_MAX_COUNT)

    # ── Public read API ──────────────────────────────────────────────────────

    def fetch_home_timeline(self, count: int = 20) -> List[Tweet]:
        """Fetch For-You home timeline."""
        return self._fetch_timeline(
            "HomeTimeline", count,
            lambda d: _deep_get(d, "data", "home", "home_timeline_urt", "instructions"),
        )

    def fetch_following_feed(self, count: int = 20) -> List[Tweet]:
        """Fetch chronological Following timeline."""
        return self._fetch_timeline(
            "HomeLatestTimeline", count,
            lambda d: _deep_get(d, "data", "home", "home_timeline_urt", "instructions"),
        )

    def fetch_bookmarks(self, count: int = 50) -> List[Tweet]:
        """Fetch saved bookmarks."""
        def get_instructions(d: Any) -> Any:
            r = _deep_get(d, "data", "bookmark_timeline", "timeline", "instructions")
            return r or _deep_get(d, "data", "bookmark_timeline_v2", "timeline", "instructions")
        return self._fetch_timeline("Bookmarks", count, get_instructions)

    def fetch_search(self, query: str, count: int = 20, product: str = "Top") -> List[Tweet]:
        """Search tweets. product: Top | Latest | Photos | Videos"""
        return self._fetch_timeline(
            "SearchTimeline", count,
            lambda d: _deep_get(
                d, "data", "search_by_raw_query", "search_timeline", "timeline", "instructions"
            ),
            extra_variables={"rawQuery": query, "querySource": "typed_query", "product": product},
            override_base_variables=True,
        )

    def fetch_user(self, screen_name: str) -> UserProfile:
        """Fetch user profile by screen name."""
        features = {
            "hidden_profile_subscriptions_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "highlights_tweets_tab_ui_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
        }
        data = self._graphql_get(
            "UserByScreenName",
            {"screen_name": screen_name, "withSafetyModeUserFields": True},
            features,
        )
        result = _deep_get(data, "data", "user", "result")
        if not result:
            raise RuntimeError(f"User @{screen_name} not found")
        legacy = result.get("legacy", {})
        return UserProfile(
            id=result.get("rest_id", ""),
            name=legacy.get("name", ""),
            screen_name=legacy.get("screen_name", screen_name),
            bio=legacy.get("description", ""),
            location=legacy.get("location", ""),
            url=_deep_get(legacy, "entities", "url", "urls", 0, "expanded_url") or "",
            followers_count=_parse_int(legacy.get("followers_count")),
            following_count=_parse_int(legacy.get("friends_count")),
            tweets_count=_parse_int(legacy.get("statuses_count")),
            likes_count=_parse_int(legacy.get("favourites_count")),
            verified=bool(result.get("is_blue_verified") or legacy.get("verified", False)),
            profile_image_url=legacy.get("profile_image_url_https", ""),
            created_at=legacy.get("created_at", ""),
        )

    def fetch_user_tweets(self, user_id: str, count: int = 20) -> List[Tweet]:
        """Fetch tweets posted by a user (requires user_id, not screen_name)."""
        return self._fetch_timeline(
            "UserTweets", count,
            lambda d: _deep_get(d, "data", "user", "result", "timeline_v2", "timeline", "instructions"),
            extra_variables={"userId": user_id, "withQuickPromoteEligibilityTweetFields": True, "withVoice": True, "withV2Timeline": True},
        )

    def fetch_user_likes(self, user_id: str, count: int = 20) -> List[Tweet]:
        """Fetch tweets liked by a user."""
        return self._fetch_timeline(
            "Likes", count,
            lambda d: _deep_get(d, "data", "user", "result", "timeline_v2", "timeline", "instructions"),
            extra_variables={"userId": user_id, "includePromotedContent": False, "withVoice": True},
            override_base_variables=True,
        )

    def fetch_tweet_detail(self, tweet_id: str, count: int = 20) -> List[Tweet]:
        """Fetch a tweet and its reply thread."""
        return self._fetch_timeline(
            "TweetDetail", count,
            lambda d: _deep_get(d, "data", "threaded_conversation_with_injections_v2", "instructions"),
            extra_variables={"focalTweetId": tweet_id, "referrer": "tweet", "with_rux_injections": False, "includePromotedContent": False, "withCommunity": True, "withQuickPromoteEligibilityTweetFields": True, "withBirdwatchNotes": True, "withVoice": True},
            override_base_variables=True,
            field_toggles={"withArticleRichContentState": True, "withArticlePlainText": False, "withGrokAnalyze": False, "withDisallowedReplyControls": False},
        )

    def fetch_list_timeline(self, list_id: str, count: int = 20) -> List[Tweet]:
        """Fetch tweets from a Twitter List."""
        return self._fetch_timeline(
            "ListLatestTweetsTimeline", count,
            lambda d: _deep_get(d, "data", "list", "tweets_timeline", "timeline", "instructions"),
            extra_variables={"listId": list_id},
            override_base_variables=True,
        )

    def fetch_followers(self, user_id: str, count: int = 20) -> List[UserProfile]:
        """Fetch followers of a user."""
        return self._fetch_user_list(
            "Followers", user_id, count,
            lambda d: _deep_get(d, "data", "user", "result", "timeline", "timeline", "instructions"),
        )

    def fetch_following(self, user_id: str, count: int = 20) -> List[UserProfile]:
        """Fetch users that a user is following."""
        return self._fetch_user_list(
            "Following", user_id, count,
            lambda d: _deep_get(d, "data", "user", "result", "timeline", "timeline", "instructions"),
        )

    # ── Public write API ─────────────────────────────────────────────────────

    def create_tweet(self, text: str, reply_to_id: Optional[str] = None) -> str:
        variables: Dict[str, Any] = {
            "tweet_text": text,
            "media": {"media_entities": [], "possibly_sensitive": False},
            "semantic_annotation_ids": [],
            "dark_request": False,
        }
        if reply_to_id:
            variables["reply"] = {"in_reply_to_tweet_id": reply_to_id, "exclude_reply_user_ids": []}
        data = self._graphql_post("CreateTweet", variables, FEATURES)
        result = _deep_get(data, "data", "create_tweet", "tweet_results", "result")
        if result:
            return result.get("rest_id", "")
        raise RuntimeError("Failed to create tweet")

    def delete_tweet(self, tweet_id: str) -> bool:
        self._graphql_post("DeleteTweet", {"tweet_id": tweet_id, "dark_request": False})
        return True

    def like_tweet(self, tweet_id: str) -> bool:
        self._graphql_post("FavoriteTweet", {"tweet_id": tweet_id})
        return True

    def unlike_tweet(self, tweet_id: str) -> bool:
        self._graphql_post("UnfavoriteTweet", {"tweet_id": tweet_id, "dark_request": False})
        return True

    def retweet(self, tweet_id: str) -> bool:
        self._graphql_post("CreateRetweet", {"tweet_id": tweet_id, "dark_request": False})
        return True

    def unretweet(self, tweet_id: str) -> bool:
        self._graphql_post("DeleteRetweet", {"source_tweet_id": tweet_id, "dark_request": False})
        return True

    def bookmark_tweet(self, tweet_id: str) -> bool:
        self._graphql_post("CreateBookmark", {"tweet_id": tweet_id})
        return True

    def unbookmark_tweet(self, tweet_id: str) -> bool:
        self._graphql_post("DeleteBookmark", {"tweet_id": tweet_id})
        return True

    # ── Internal: timeline fetcher ───────────────────────────────────────────

    def _fetch_timeline(
        self,
        operation_name: str,
        count: int,
        get_instructions: Callable[[Any], Any],
        extra_variables: Optional[Dict[str, Any]] = None,
        override_base_variables: bool = False,
        field_toggles: Optional[Dict[str, Any]] = None,
    ) -> List[Tweet]:
        if count <= 0:
            return []
        count = min(count, self._max_count)
        tweets: List[Tweet] = []
        seen_ids: Set[str] = set()
        cursor: Optional[str] = None
        max_attempts = int(math.ceil(count / 20.0)) + 2

        for _ in range(max_attempts):
            if len(tweets) >= count:
                break
            variables: Dict[str, Any] = (
                {"count": min(count - len(tweets) + 5, 40)}
                if override_base_variables
                else {
                    "count": min(count - len(tweets) + 5, 40),
                    "includePromotedContent": False,
                    "latestControlAvailable": True,
                    "requestContext": "launch",
                }
            )
            if extra_variables:
                variables.update(extra_variables)
            if cursor:
                variables["cursor"] = cursor

            data = self._graphql_get(operation_name, variables, FEATURES, field_toggles)
            new_tweets, next_cursor = self._parse_timeline_response(data, get_instructions)

            for t in new_tweets:
                if t.id and t.id not in seen_ids:
                    seen_ids.add(t.id)
                    tweets.append(t)

            if not next_cursor or not new_tweets:
                break
            cursor = next_cursor
            if len(tweets) < count and self._request_delay > 0:
                time.sleep(self._request_delay)

        return tweets[:count]

    def _fetch_user_list(
        self,
        operation_name: str,
        user_id: str,
        count: int,
        get_instructions: Callable[[Any], Any],
    ) -> List[UserProfile]:
        if count <= 0:
            return []
        count = min(count, self._max_count)
        users: List[UserProfile] = []
        seen_ids: Set[str] = set()
        cursor: Optional[str] = None
        max_attempts = int(math.ceil(count / 20.0)) + 2

        for _ in range(max_attempts):
            if len(users) >= count:
                break
            variables: Dict[str, Any] = {"userId": user_id, "count": min(count - len(users) + 5, 40)}
            if cursor:
                variables["cursor"] = cursor
            data = self._graphql_get(operation_name, variables, FEATURES)
            new_users, next_cursor = self._parse_user_list_response(data, get_instructions)
            for u in new_users:
                if u.id and u.id not in seen_ids:
                    seen_ids.add(u.id)
                    users.append(u)
            if not next_cursor or not new_users:
                break
            cursor = next_cursor
            if len(users) < count and self._request_delay > 0:
                time.sleep(self._request_delay)

        return users[:count]

    # ── Internal: HTTP ───────────────────────────────────────────────────────

    def _build_headers(self, url: str = "", method: str = "GET") -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "Cookie": f"auth_token={self._auth_token}; ct0={self._ct0}",
            "X-Csrf-Token": self._ct0,
            "X-Twitter-Active-User": "yes",
            "X-Twitter-Auth-Type": "OAuth2Session",
            "X-Twitter-Client-Language": "en",
            "User-Agent": USER_AGENT,
            "Referer": "https://x.com",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "sec-ch-ua": SEC_CH_UA,
            "sec-ch-ua-mobile": SEC_CH_UA_MOBILE,
            "sec-ch-ua-platform": SEC_CH_UA_PLATFORM,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        if method == "POST":
            headers["Content-Type"] = "application/json"
        return headers

    def _api_request(self, url: str, method: str = "GET", body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = self._build_headers(url, method)
        encoded_body = json.dumps(body).encode() if body else None

        for attempt in range(self._max_retries + 1):
            req = urllib.request.Request(url, data=encoded_body, method=method)
            for k, v in headers.items():
                req.add_header(k, v)
            try:
                with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as resp:
                    payload = resp.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < self._max_retries:
                    wait = self._retry_base_delay * (2 ** attempt)
                    logger.warning("Rate limited (429), retrying in %.1fs", wait)
                    time.sleep(wait)
                    continue
                body_text = exc.read().decode("utf-8", errors="replace")
                raise TwitterAPIError(exc.code, f"Twitter API error {exc.code}: {body_text[:500]}")
            except urllib.error.URLError as exc:
                raise TwitterAPIError(0, f"Network error: {exc.reason}")

            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                raise TwitterAPIError(0, "Twitter API returned invalid JSON")

            if isinstance(parsed, dict) and parsed.get("errors"):
                err = parsed["errors"][0]
                if err.get("code") == 88 and attempt < self._max_retries:
                    wait = self._retry_base_delay * (2 ** attempt)
                    logger.warning("Rate limited (code 88), retrying in %.1fs", wait)
                    time.sleep(wait)
                    continue
                raise TwitterAPIError(0, f"Twitter API error: {err.get('message', 'Unknown')}")
            return parsed

        raise TwitterAPIError(429, f"Rate limited after {self._max_retries} retries")

    def _graphql_get(
        self,
        operation_name: str,
        variables: Dict[str, Any],
        features: Dict[str, Any],
        field_toggles: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        qid = _resolve_query_id(operation_name, prefer_fallback=True)
        url = _build_graphql_url(qid, operation_name, variables, features, field_toggles)
        try:
            return self._api_request(url)
        except TwitterAPIError as exc:
            if exc.status_code == 404 and qid == FALLBACK_QUERY_IDS.get(operation_name):
                logger.info("Retrying %s with live queryId after 404", operation_name)
                _invalidate_query_id(operation_name)
                qid = _resolve_query_id(operation_name, prefer_fallback=False)
                url = _build_graphql_url(qid, operation_name, variables, features, field_toggles)
                return self._api_request(url)
            raise RuntimeError(str(exc))

    def _graphql_post(
        self,
        operation_name: str,
        variables: Dict[str, Any],
        features: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        qid = _resolve_query_id(operation_name, prefer_fallback=True)

        def _do(q: str) -> Dict[str, Any]:
            url = f"https://x.com/i/api/graphql/{q}/{operation_name}"
            body: Dict[str, Any] = {"variables": variables, "queryId": q}
            if features:
                body["features"] = features
            return self._api_request(url, method="POST", body=body)

        try:
            return _do(qid)
        except TwitterAPIError as exc:
            if exc.status_code == 404 and qid == FALLBACK_QUERY_IDS.get(operation_name):
                _invalidate_query_id(operation_name)
                return _do(_resolve_query_id(operation_name, prefer_fallback=False))
            raise RuntimeError(str(exc))

    # ── Internal: response parsers ───────────────────────────────────────────

    def _parse_timeline_response(
        self,
        data: Any,
        get_instructions: Callable[[Any], Any],
    ) -> Tuple[List[Tweet], Optional[str]]:
        tweets: List[Tweet] = []
        next_cursor: Optional[str] = None
        instructions = get_instructions(data)
        if not isinstance(instructions, list):
            return tweets, next_cursor
        for instruction in instructions:
            entries = instruction.get("entries") or instruction.get("moduleItems") or []
            for entry in entries:
                content = entry.get("content", {})
                next_cursor = _extract_cursor(content) or next_cursor
                # Top-level tweet
                result = _deep_get(content, "itemContent", "tweet_results", "result")
                if result:
                    t = self._parse_tweet_result(result)
                    if t:
                        tweets.append(t)
                # Nested items (conversation modules)
                for nested in content.get("items", []):
                    result = _deep_get(nested, "item", "itemContent", "tweet_results", "result")
                    if result:
                        t = self._parse_tweet_result(result)
                        if t:
                            tweets.append(t)
        return tweets, next_cursor

    def _parse_tweet_result(self, result: Dict[str, Any], depth: int = 0) -> Optional[Tweet]:
        if depth > 2:
            return None
        tweet_data = result
        if result.get("__typename") == "TweetWithVisibilityResults" and result.get("tweet"):
            tweet_data = result["tweet"]
        if tweet_data.get("__typename") == "TweetTombstone":
            return None
        legacy = tweet_data.get("legacy")
        core = tweet_data.get("core")
        if not isinstance(legacy, dict) or not isinstance(core, dict):
            return None

        user = _deep_get(core, "user_results", "result") or {}
        user_legacy = user.get("legacy", {})
        user_core = user.get("core", {})

        is_retweet = bool(_deep_get(legacy, "retweeted_status_result", "result"))
        actual_data, actual_legacy, actual_user, actual_user_legacy = tweet_data, legacy, user, user_legacy
        retweeted_by: Optional[str] = None

        if is_retweet:
            retweeted_by = user_core.get("screen_name") or user_legacy.get("screen_name", "unknown")
            rt = _deep_get(legacy, "retweeted_status_result", "result") or {}
            if rt.get("__typename") == "TweetWithVisibilityResults" and rt.get("tweet"):
                rt = rt["tweet"]
            rt_legacy = rt.get("legacy")
            rt_core = rt.get("core")
            if isinstance(rt_legacy, dict) and isinstance(rt_core, dict):
                actual_data = rt
                actual_legacy = rt_legacy
                actual_user = _deep_get(rt_core, "user_results", "result") or {}
                actual_user_legacy = actual_user.get("legacy", {})

        quoted = _deep_get(actual_data, "quoted_status_result", "result")
        return Tweet(
            id=actual_data.get("rest_id", ""),
            text=actual_legacy.get("full_text", ""),
            author=_extract_author(actual_user, actual_user_legacy),
            metrics=Metrics(
                likes=_parse_int(actual_legacy.get("favorite_count")),
                retweets=_parse_int(actual_legacy.get("retweet_count")),
                replies=_parse_int(actual_legacy.get("reply_count")),
                quotes=_parse_int(actual_legacy.get("quote_count")),
                views=_parse_int(_deep_get(actual_data, "views", "count")),
                bookmarks=_parse_int(actual_legacy.get("bookmark_count")),
            ),
            created_at=actual_legacy.get("created_at", ""),
            media=_extract_media(actual_legacy),
            urls=[u.get("expanded_url", "") for u in _deep_get(actual_legacy, "entities", "urls") or []],
            is_retweet=is_retweet,
            retweeted_by=retweeted_by,
            lang=actual_legacy.get("lang", ""),
            quoted_tweet=self._parse_tweet_result(quoted, depth + 1) if isinstance(quoted, dict) else None,
        )

    def _parse_user_list_response(
        self,
        data: Any,
        get_instructions: Callable[[Any], Any],
    ) -> Tuple[List[UserProfile], Optional[str]]:
        users: List[UserProfile] = []
        next_cursor: Optional[str] = None
        instructions = get_instructions(data)
        if not isinstance(instructions, list):
            return users, next_cursor
        for instruction in instructions:
            for entry in instruction.get("entries", []):
                content = entry.get("content", {})
                next_cursor = _extract_cursor(content) or next_cursor
                result = _deep_get(content, "itemContent", "user_results", "result")
                if result:
                    u = self._parse_user_result(result)
                    if u:
                        users.append(u)
        return users, next_cursor

    def _parse_user_result(self, result: Dict[str, Any]) -> Optional[UserProfile]:
        legacy = result.get("legacy", {})
        if not legacy:
            return None
        return UserProfile(
            id=result.get("rest_id", ""),
            name=legacy.get("name", ""),
            screen_name=legacy.get("screen_name", ""),
            bio=legacy.get("description", ""),
            location=legacy.get("location", ""),
            followers_count=_parse_int(legacy.get("followers_count")),
            following_count=_parse_int(legacy.get("friends_count")),
            tweets_count=_parse_int(legacy.get("statuses_count")),
            likes_count=_parse_int(legacy.get("favourites_count")),
            verified=bool(result.get("is_blue_verified") or legacy.get("verified", False)),
            profile_image_url=legacy.get("profile_image_url_https", ""),
            created_at=legacy.get("created_at", ""),
        )
