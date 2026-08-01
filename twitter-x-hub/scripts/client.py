"""Twitter/X internal GraphQL API client.

Adapted from https://github.com/public-clis/twitter-cli (v0.8.6)
Changes vs upstream:
  - Zero third-party dependencies (stdlib only, no curl_cffi / browser-cookie3 / rich / click)
  - Auth passed directly (auth_token + ct0); no browser auto-extraction
  - No xclienttransaction header generation
  - No image upload / media attach support
  - QueryId resolution: cache → FALLBACK_QUERY_IDS → fa0311/twitter-openapi → JS bundle scan
"""

from __future__ import annotations

import json
import logging
import math
import random
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .models import BookmarkFolder, Tweet, UserProfile
from .parser import (
    _deep_get,
    _parse_int,
    parse_timeline_response,
    parse_tweet_result,
    parse_user_result,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

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

# ── QueryId constants ────────────────────────────────────────────────────
# Synced from upstream v0.8.6 — updated vs our previous version:
#   Bookmarks: VFdMm9iVZxlU6hD86gfW_A → uzboyXSHSJrR-mGJqep0TQ
#   Likes: lIDpu_NWL7_VhimGGt0o6A → RozQdCp4CilQzrcuU0NY5w
#   ListLatestTweetsTimeline: RlZzktZY_9wJynoepm8ZsA → fb_6wmHD2dk9D-xYXOQlgw
#   Followers: IOh4aS6UdGWGJUYTqliQ7Q → Enf9DNUZYiT037aersI5gg
#   Following: zx6e-TLzRkeDO_a7p4b3JQ → ntIPnH1WMBKW--4Tn1q71A
#   CreateTweet: IID9x6WsdMnTlXnzXGq8ng → zkcFc6F-RKRgWN8HUkJfZg
#   DeleteTweet: VaenaVgh5q5ih7kvyVjgtg → nxpZCY2K-I6QoFHAHeojFQ
#   CreateRetweet: ojPdsZsimiJrUGLR1sjUtA → mbRO74GrOvSfRcJnlMapnQ
#   DeleteRetweet: iQtK4dl5hBmXewYZuEOKVw → ZyZigVsNiFO6v1dEks1eWg
# New entries: TweetResultByRestId, BookmarkFoldersSlice, BookmarkFolderTimeline
FALLBACK_QUERY_IDS: Dict[str, str] = {
    # Scanned from x.com JS bundle 2026-04-08 (main.0e98bc8a.js)
    "HomeTimeline":             "J62e-zdBz8cxFVOjBcq1WA",
    "HomeLatestTimeline":       "2ee46L1AFXmnTa0EvUog-Q",
    "Bookmarks":                "uzboyXSHSJrR-mGJqep0TQ",   # not in current bundle, keep upstream
    "UserByScreenName":         "IGgvgiOx4QZndDHuD3x9TQ",
    "UserTweets":               "x3B_xLqC0yZawOB7WQhaVQ",
    "SearchTimeline":           "pCd62NDD9dlCDgEGgEVHMg",
    "Likes":                    "KPuet6dGbC8LB2sOLx7tZQ",
    "TweetDetail":              "rU08O-YiXdr0IZfE7qaUMg",
    "TweetResultByRestId":      "tmhPpO5sDermwYmq3h034A",
    "ListLatestTweetsTimeline": "qcQY-EkEWjJ-wwJhsKdxYQ",
    "Followers":                "-WcGoRt8IQuPm-l1ymgy6g",
    "Following":                "vWCjN9gcTJiXzzMPR5Oxzw",
    "CreateTweet":              "S1qcGUn68_U0lDKdMlYSGg",
    "DeleteTweet":              "nxpZCY2K-I6QoFHAHeojFQ",
    "FavoriteTweet":            "lI07N6Otwv1PhnEgXILM7A",
    "UnfavoriteTweet":          "ZYKSe-w7KEslx3JhSIk5LA",
    "CreateRetweet":            "mbRO74GrOvSfRcJnlMapnQ",
    "DeleteRetweet":            "ZyZigVsNiFO6v1dEks1eWg",
    "CreateBookmark":           "aoDbu3RHznuiSkQ9aNM67Q",
    "DeleteBookmark":           "Wlmlj2-xzyS1GN3a6cj-mQ",
    "BookmarkFoldersSlice":     "i78YDd0Tza-dV4SYs58kRg",   # keep upstream
    "BookmarkFolderTimeline":   "hNY7X2xE2N7HVF6Qb_mu6w",   # keep upstream
}

# Community-maintained live queryId source
TWITTER_OPENAPI_URL = (
    "https://raw.githubusercontent.com/fa0311/twitter-openapi/"
    "refs/heads/main/src/config/placeholder.json"
)

# Feature flags — synced from upstream v0.8.6
# Key change: longform_notetweets_inline_media_enabled True→False removed,
# new flags: tweetypie_unmention_optimization_enabled, rweb_video_timestamps_enabled,
# responsive_web_media_download_video_enabled
# URL optimization: only True values are sent (upstream best practice)
FEATURES: Dict[str, Any] = {
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "responsive_web_media_download_video_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "responsive_web_enhance_cards_enabled": False,
}

_ABSOLUTE_MAX_COUNT = 500

# Module-level caches
_cached_query_ids: Dict[str, str] = {}
_bundles_scanned = False
_SSL_CTX = ssl.create_default_context()


# ── QueryId resolution ───────────────────────────────────────────────────

def _url_fetch(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    req = urllib.request.Request(url)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as r:
        return r.read().decode("utf-8")


def _fetch_from_github(operation_name: str) -> Optional[str]:
    """Try to fetch a fresh queryId from fa0311/twitter-openapi."""
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


# ── URL builder ──────────────────────────────────────────────────────────

def _build_graphql_url(
    query_id: str,
    operation_name: str,
    variables: Dict[str, Any],
    features: Dict[str, Any],
    field_toggles: Optional[Dict[str, Any]] = None,
) -> str:
    # Upstream optimization: omit False-valued features to avoid 414 URI Too Long
    compact_features = {k: v for k, v in features.items() if v is not False}
    url = (
        f"https://x.com/i/api/graphql/{query_id}/{operation_name}"
        f"?variables={urllib.parse.quote(json.dumps(variables, separators=(',', ':')))}"
        f"&features={urllib.parse.quote(json.dumps(compact_features, separators=(',', ':')))}"
    )
    if field_toggles:
        url += f"&fieldToggles={urllib.parse.quote(json.dumps(field_toggles, separators=(',', ':')))}"
    return url


# ── Error type ───────────────────────────────────────────────────────────

class TwitterAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


# ── Main client ──────────────────────────────────────────────────────────

class TwitterClient:
    """Twitter/X GraphQL client (cookie auth, zero third-party deps).

    Adapted from https://github.com/public-clis/twitter-cli
    Auth is passed directly as auth_token + ct0. Optionally pass cookie_string
    (full browser cookie header) for richer fingerprinting.
    """

    def __init__(
        self,
        auth_token: str,
        ct0: str,
        request_delay: float = 1.5,
        max_retries: int = 3,
        retry_base_delay: float = 5.0,
        max_count: int = 200,
        cookie_string: Optional[str] = None,
    ) -> None:
        self._auth_token = auth_token
        self._ct0 = ct0
        self._cookie_string = cookie_string  # optional full cookie string
        self._request_delay = request_delay
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._max_count = min(max_count, _ABSOLUTE_MAX_COUNT)

    # ── Public read API ──────────────────────────────────────────────────

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
        """Search tweets. product: Top | Latest | Photos | Videos

        ⚠️  KNOWN LIMITATION: As of early 2026, X requires an `x-client-transaction-id`
        header for SearchTimeline requests. This header is generated by the `xclienttransaction`
        library (a C extension) which cannot be installed on iSH/Alpine. As a result,
        SearchTimeline returns 404 in this environment.

        Workaround: Use the browser_use tool to navigate to x.com/search and extract
        results directly from the DOM, or use the twitter-cli package in a full Python
        environment where xclienttransaction can be installed.
        """
        # SearchTimeline requires fieldToggles (discovered from JS bundle analysis)
        field_toggles = {
            "withArticlePlainText": True,
            "withArticleRichContentState": True,
            "withGrokAnalyze": False,
            "withDisallowedReplyControls": False,
        }
        # SearchTimeline uses a different features set than timeline endpoints
        search_features = {
            "rweb_video_screen_enabled": False,
            "profile_label_improvements_pcf_label_in_post_enabled": True,
            "rweb_tipjar_consumption_enabled": True,
            "verified_phone_label_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "premium_content_api_read_enabled": False,
            "communities_web_enable_tweet_community_results_fetch": True,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "articles_preview_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
        }
        variables = {
            "rawQuery": query,
            "querySource": "typed_query",
            "product": product,
            "count": min(count, 20),
        }
        return self._fetch_timeline(
            "SearchTimeline", count,
            lambda d: _deep_get(
                d, "data", "search_by_raw_query", "search_timeline", "timeline", "instructions"
            ),
            extra_variables=variables,
            override_base_variables=True,
            features_override=search_features,
            field_toggles=field_toggles,
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
        profile = parse_user_result(result)
        if not profile:
            raise RuntimeError(f"User @{screen_name} unavailable")
        return profile

    def fetch_user_tweets(self, user_id: str, count: int = 20) -> List[Tweet]:
        """Fetch tweets posted by a user (requires user_id, not screen_name)."""
        return self._fetch_timeline(
            "UserTweets", count,
            lambda d: _deep_get(
                d, "data", "user", "result", "timeline_v2", "timeline", "instructions"
            ),
            extra_variables={
                "userId": user_id,
                "includePromotedContent": True,
                "withQuickPromoteEligibilityTweetFields": True,
                "withVoice": True,
                "withV2Timeline": True,
            },
            override_base_variables=True,
        )

    def fetch_user_likes(self, user_id: str, count: int = 20) -> List[Tweet]:
        """Fetch tweets liked by a user (own likes only since Jun 2024)."""
        return self._fetch_timeline(
            "Likes", count,
            lambda d: _deep_get(
                d, "data", "user", "result", "timeline_v2", "timeline", "instructions"
            ),
            extra_variables={"userId": user_id, "includePromotedContent": False},
            override_base_variables=True,
        )

    def fetch_tweet_detail(self, tweet_id: str, count: int = 40) -> List[Tweet]:
        """Fetch a tweet and its reply thread."""
        return self._fetch_timeline(
            "TweetDetail", count,
            lambda d: _deep_get(
                d, "data", "threaded_conversation_with_injections_v2", "instructions"
            ),
            extra_variables={
                "focalTweetId": tweet_id,
                "referrer": "tweet",
                "count": count,
                "with_rux_injections": False,
                "includePromotedContent": True,
                "withCommunity": True,
                "withQuickPromoteEligibilityTweetFields": True,
                "withBirdwatchNotes": True,
                "withVoice": True,
            },
            override_base_variables=True,
        )

    def fetch_tweet_by_id(self, tweet_id: str) -> Optional[Tweet]:
        """Fetch a single tweet by ID (TweetResultByRestId)."""
        data = self._graphql_get(
            "TweetResultByRestId",
            {
                "tweetId": tweet_id,
                "withCommunity": False,
                "includePromotedContent": False,
                "withVoice": False,
            },
            FEATURES,
        )
        result = _deep_get(data, "data", "tweetResult", "result")
        if not result:
            return None
        return parse_tweet_result(result)

    def fetch_list_timeline(self, list_id: str, count: int = 20) -> List[Tweet]:
        """Fetch tweets from a Twitter List."""
        return self._fetch_timeline(
            "ListLatestTweetsTimeline", count,
            lambda d: _deep_get(
                d, "data", "list", "tweets_timeline", "timeline", "instructions"
            ),
            extra_variables={"listId": list_id, "count": count},
            override_base_variables=True,
        )

    def fetch_followers(self, user_id: str, count: int = 20) -> List[UserProfile]:
        """Fetch followers of a user."""
        return self._fetch_users("Followers", user_id, count)

    def fetch_following(self, user_id: str, count: int = 20) -> List[UserProfile]:
        """Fetch accounts followed by a user."""
        return self._fetch_users("Following", user_id, count)

    def fetch_bookmark_folders(self) -> List[BookmarkFolder]:
        """Fetch bookmark folders."""
        data = self._graphql_get(
            "BookmarkFoldersSlice",
            {"count": 100},
            FEATURES,
        )
        folders = []
        items = _deep_get(data, "data", "bookmark_folders_slice", "items") or []
        for item in items:
            folder_id = item.get("id", "")
            name = item.get("name", "")
            if folder_id:
                folders.append(BookmarkFolder(id=folder_id, name=name))
        return folders

    # ── Write API ────────────────────────────────────────────────────────

    def post_tweet(self, text: str, reply_to_id: Optional[str] = None) -> Dict[str, Any]:
        """Post a new tweet or reply."""
        variables: Dict[str, Any] = {
            "tweet_text": text,
            "dark_request": False,
            "media": {"media_entities": [], "possibly_sensitive": False},
            "semantic_annotation_ids": [],
        }
        if reply_to_id:
            variables["reply"] = {
                "in_reply_to_tweet_id": reply_to_id,
                "exclude_reply_user_ids": [],
            }
        return self._graphql_post("CreateTweet", variables)

    def delete_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """Delete a tweet by ID."""
        return self._graphql_post("DeleteTweet", {"tweet_id": tweet_id, "dark_request": False})

    def like_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """Like a tweet."""
        return self._graphql_post("FavoriteTweet", {"tweet_id": tweet_id})

    def unlike_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """Unlike a tweet."""
        return self._graphql_post("UnfavoriteTweet", {"tweet_id": tweet_id})

    def retweet(self, tweet_id: str) -> Dict[str, Any]:
        """Retweet a tweet."""
        return self._graphql_post("CreateRetweet", {"tweet_id": tweet_id, "dark_request": False})

    def unretweet(self, tweet_id: str) -> Dict[str, Any]:
        """Undo a retweet."""
        return self._graphql_post("DeleteRetweet", {"source_tweet_id": tweet_id, "dark_request": False})

    def bookmark_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """Bookmark a tweet."""
        return self._graphql_post("CreateBookmark", {"tweet_id": tweet_id})

    def unbookmark_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """Remove a tweet from bookmarks."""
        return self._graphql_post("DeleteBookmark", {"tweet_id": tweet_id})

    # ── Internal helpers ─────────────────────────────────────────────────

    def _build_headers(self) -> Dict[str, str]:
        cookie = f"auth_token={self._auth_token}; ct0={self._ct0}"
        if self._cookie_string:
            # Merge full cookie string (full browser fingerprint)
            cookie = self._cookie_string
        return {
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "Cookie": cookie,
            "X-Csrf-Token": self._ct0,
            "X-Twitter-Active-User": "yes",
            "X-Twitter-Auth-Type": "OAuth2Session",
            "X-Twitter-Client-Language": "en",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://x.com/",
            "Sec-Ch-Ua": SEC_CH_UA,
            "Sec-Ch-Ua-Mobile": SEC_CH_UA_MOBILE,
            "Sec-Ch-Ua-Platform": SEC_CH_UA_PLATFORM,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def _request(self, url: str, method: str = "GET", body: Optional[bytes] = None) -> Any:
        headers = self._build_headers()
        req = urllib.request.Request(url, headers=headers, method=method, data=body)
        for attempt in range(self._max_retries + 1):
            try:
                with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                status = e.code
                body_text = e.read().decode("utf-8", errors="replace")
                logger.debug("HTTP %d: %s", status, body_text[:200])
                if status == 404:
                    raise TwitterAPIError(status, f"404 Not Found: {url}")
                if status in (429, 503) or (status == 400 and "88" in body_text):
                    if attempt < self._max_retries:
                        delay = self._retry_base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning("Rate limited (HTTP %d), retrying in %.1fs…", status, delay)
                        time.sleep(delay)
                        continue
                raise TwitterAPIError(status, body_text[:300])
        raise TwitterAPIError(429, "Max retries exceeded")

    def _graphql_get(
        self,
        operation_name: str,
        variables: Dict[str, Any],
        features: Dict[str, Any],
        field_toggles: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a GraphQL GET request, with queryId auto-refresh on 404."""
        query_id = _resolve_query_id(operation_name)
        url = _build_graphql_url(query_id, operation_name, variables, features, field_toggles)
        try:
            result = self._request(url)
        except TwitterAPIError as e:
            if e.status_code == 404:
                # queryId expired — invalidate cache and force JS bundle scan
                _invalidate_query_id(operation_name)
                global _bundles_scanned
                _bundles_scanned = False  # force re-scan on next lookup
                query_id = _resolve_query_id(operation_name, prefer_fallback=False)
                url = _build_graphql_url(query_id, operation_name, variables, features, field_toggles)
                result = self._request(url)
            else:
                raise
        # Add jitter delay between requests
        time.sleep(self._request_delay * random.uniform(0.7, 1.3))
        return result

    def _graphql_post(self, operation_name: str, variables: Dict[str, Any]) -> Any:
        """Execute a GraphQL POST mutation."""
        query_id = _resolve_query_id(operation_name)
        url = f"https://x.com/i/api/graphql/{query_id}/{operation_name}"
        payload = json.dumps({"variables": variables, "queryId": query_id}, separators=(",", ":"))
        # Write operations: longer random delay to avoid rate limiting
        time.sleep(random.uniform(1.5, 4.0))
        try:
            result = self._request(url, method="POST", body=payload.encode())
        except TwitterAPIError as e:
            if e.status_code == 404:
                _invalidate_query_id(operation_name)
                global _bundles_scanned
                _bundles_scanned = False
                query_id = _resolve_query_id(operation_name, prefer_fallback=False)
                url = f"https://x.com/i/api/graphql/{query_id}/{operation_name}"
                payload = json.dumps({"variables": variables, "queryId": query_id}, separators=(",", ":"))
                result = self._request(url, method="POST", body=payload.encode())
            else:
                raise
        return result

    def _fetch_timeline(
        self,
        operation_name: str,
        count: int,
        get_instructions: Callable[[Any], Any],
        extra_variables: Optional[Dict[str, Any]] = None,
        override_base_variables: bool = False,
        features_override: Optional[Dict[str, Any]] = None,
        field_toggles: Optional[Dict[str, Any]] = None,
    ) -> List[Tweet]:
        count = min(count, self._max_count)
        base_vars: Dict[str, Any] = {
            "count": 20,
            "includePromotedContent": True,
            "latestControlAvailable": True,
        }
        if override_base_variables:
            variables = dict(extra_variables or {})
        else:
            variables = {**base_vars, **(extra_variables or {})}

        features = features_override if features_override is not None else FEATURES

        tweets: List[Tweet] = []
        seen_ids: Set[str] = set()
        cursor: Optional[str] = None
        page = 0

        while len(tweets) < count:
            if cursor:
                variables["cursor"] = cursor
            data = self._graphql_get(operation_name, variables, features, field_toggles=field_toggles)
            new_tweets, cursor = parse_timeline_response(data, get_instructions)

            added = 0
            for t in new_tweets:
                if t.id not in seen_ids:
                    seen_ids.add(t.id)
                    tweets.append(t)
                    added += 1

            page += 1
            logger.debug("Page %d: +%d tweets (total %d), cursor=%s", page, added, len(tweets), cursor)

            if not cursor or added == 0:
                break

        return tweets[:count]

    def _fetch_users(
        self, operation_name: str, user_id: str, count: int
    ) -> List[UserProfile]:
        count = min(count, self._max_count)
        variables: Dict[str, Any] = {"userId": user_id, "count": 20}
        users: List[UserProfile] = []
        seen_ids: Set[str] = set()
        cursor: Optional[str] = None

        while len(users) < count:
            if cursor:
                variables["cursor"] = cursor
            data = self._graphql_get(operation_name, variables, FEATURES)

            instructions = (
                _deep_get(data, "data", "user", "result", "timeline", "timeline", "instructions")
                or []
            )
            new_cursor = None
            added = 0
            for instruction in instructions:
                for entry in instruction.get("entries", []):
                    content = entry.get("content", {})
                    if content.get("cursorType") == "Bottom":
                        new_cursor = content.get("value")
                    item_content = content.get("itemContent", {})
                    if item_content.get("__typename") == "TimelineUser":
                        result = _deep_get(item_content, "user_results", "result") or {}
                        profile = parse_user_result(result)
                        if profile and profile.id not in seen_ids:
                            seen_ids.add(profile.id)
                            users.append(profile)
                            added += 1

            cursor = new_cursor
            if not cursor or added == 0:
                break

        return users[:count]
