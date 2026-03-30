"""WeiboClient — core API client for weibo-hub.

Only dependency: httpx.
Anti-detection: Gaussian jitter + 5% long pause + exponential backoff (same as upstream).
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

from .auth import Credential, load_credential, setup_credential
from .constants import (
    BASE_URL,
    BUILD_COMMENTS_URL,
    FEED_GROUPS_URL,
    FRIENDS_TIMELINE_URL,
    FRIENDS_URL,
    GET_CONFIG_URL,
    HEADERS,
    HOT_BAND_URL,
    HOT_SEARCH_URL,
    HOT_TIMELINE_URL,
    MOBILE_BASE_URL,
    MOBILE_HEADERS,
    MOBILE_SEARCH_URL,
    MY_MBLOG_URL,
    PROFILE_INFO_URL,
    REPOST_TIMELINE_URL,
    SEARCH_BAND_URL,
    STATUSES_SHOW_URL,
)
from .exceptions import AuthRequiredError, SessionExpiredError, WeiboError

logger = logging.getLogger(__name__)

_SESSION_EXPIRED_KEYWORDS = ("请先登录", "请登录后使用", "请登录", "用户未登录")


class WeiboClient:
    """Weibo API client — httpx only, no CLI layer.

    Usage (context manager):
        with WeiboClient() as client:
            topics = client.hot_search()

    Usage (manual):
        client = WeiboClient()
        client.open()
        topics = client.hot_search()
        client.close()

    Auth:
        # First time: get cookies via browser_use get_cookies on weibo.com, then:
        WeiboClient.setup_credential({"SUB": "...", "SUBP": "...", ...})
        # Subsequent calls: credential auto-loaded from disk.
    """

    # ── Static auth helper (delegate to auth module) ──────────────────
    @staticmethod
    def setup_credential(cookies: dict[str, str]) -> Credential:
        """Persist cookies obtained from browser_use get_cookies."""
        return setup_credential(cookies)

    # ── Init ──────────────────────────────────────────────────────────

    def __init__(
        self,
        credential: Credential | None = None,
        *,
        timeout: float = 30.0,
        request_delay: float = 1.0,
        max_retries: int = 3,
    ):
        self._credential = credential or load_credential()
        self._timeout = timeout
        self._request_delay = request_delay
        self._max_retries = max_retries
        self._last_request_time: float = 0.0
        self._http: httpx.Client | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────

    def _build_client(self) -> httpx.Client:
        cookies = self._credential.cookies if self._credential else {}
        return httpx.Client(
            base_url=BASE_URL,
            headers=dict(HEADERS),
            cookies=cookies,
            follow_redirects=True,
            timeout=httpx.Timeout(self._timeout),
        )

    def open(self) -> "WeiboClient":
        self._http = self._build_client()
        return self

    def close(self) -> None:
        if self._http:
            self._http.close()
            self._http = None

    def __enter__(self) -> "WeiboClient":
        return self.open()

    def __exit__(self, *_: Any) -> None:
        self.close()

    @property
    def _client(self) -> httpx.Client:
        if not self._http:
            raise RuntimeError("Client not open. Use 'with WeiboClient() as c:' or call c.open() first.")
        return self._http

    # ── Rate limiting ─────────────────────────────────────────────────

    def _rate_limit(self) -> None:
        if self._request_delay <= 0:
            return
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            jitter = max(0.0, random.gauss(0.3, 0.15))
            if random.random() < 0.05:
                jitter += random.uniform(2.0, 5.0)
            time.sleep(self._request_delay - elapsed + jitter)
        self._last_request_time = time.time()

    # ── Response handling ─────────────────────────────────────────────

    def _check(self, data: dict[str, Any], action: str, *, unwrap: bool = True) -> dict[str, Any]:
        ok = data.get("ok")
        if ok == -100:
            raise SessionExpiredError()
        msg = str(data.get("msg", data.get("message", "")))
        if ok == 0:
            if any(kw in msg for kw in _SESSION_EXPIRED_KEYWORDS):
                raise SessionExpiredError()
            raise WeiboError(f"{action}: {msg}", code=ok)
        if ok:
            return data.get("data", data) if unwrap else data
        raise WeiboError(f"{action}: unexpected ok={ok} msg={msg}", code=ok)

    # ── Low-level request ─────────────────────────────────────────────

    def _request(
        self,
        method: str,
        url: str,
        *,
        client: httpx.Client | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self._rate_limit()
        http = client or self._client
        last_exc: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                resp = http.request(method, url, **kwargs)
                if client is None:
                    # Merge response cookies back into main session
                    for k, v in resp.cookies.items():
                        if v:
                            self._client.cookies.set(k, v)

                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.warning("HTTP %d — retry %d/%d in %.1fs", resp.status_code, attempt + 1, self._max_retries, wait)
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                if resp.text.startswith("<"):
                    raise WeiboError(f"Got HTML instead of JSON from {url} — session may have expired")
                return resp.json()

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                time.sleep(2 ** attempt + random.uniform(0, 1))

        raise WeiboError(f"Request failed after {self._max_retries} retries: {last_exc}")

    def _get(self, url: str, params: dict | None = None, action: str = "", *, unwrap: bool = True) -> dict[str, Any]:
        data = self._request("GET", url, params=params)
        return self._check(data, action, unwrap=unwrap)

    # ── Public API ────────────────────────────────────────────────────
    # Hot / Trending

    def hot_search(self) -> list[dict]:
        """热搜榜（sidebar，~52 条，无需登录）。"""
        data = self._get(HOT_SEARCH_URL, action="热搜")
        return data.get("realtime", [])

    def hot_band(self) -> list[dict]:
        """完整热搜榜（无需登录）。"""
        data = self._get(HOT_BAND_URL, action="热搜榜")
        return data.get("band_list", [])

    def trending(self) -> list[dict]:
        """实时搜索推荐词（无需登录）。"""
        data = self._get(SEARCH_BAND_URL, action="搜索推荐")
        return data.get("bands", [])

    # Feed

    def hot_feed(self, count: int = 10, max_id: str = "0") -> list[dict]:
        """热门时间线（无需登录）。"""
        data = self._get(
            HOT_TIMELINE_URL,
            params={
                "since_id": "0", "refresh": "0",
                "group_id": "102803", "containerid": "102803",
                "extparam": "discover|new_feed",
                "max_id": max_id, "count": str(count),
            },
            action="热门Feed",
            unwrap=False,
        )
        return data.get("data", {}).get("statuses", [])

    def home_feed(self, count: int = 20, max_id: str = "0") -> list[dict]:
        """关注者时间线（需要登录）。"""
        data = self._get(
            FRIENDS_TIMELINE_URL,
            params={"count": str(count), "max_id": max_id},
            action="关注Feed",
            unwrap=False,
        )
        return data.get("statuses", [])

    # Search

    def search(self, keyword: str, page: int = 1) -> list[dict]:
        """按关键词搜索微博（使用移动端 API）。"""
        params = {
            "containerid": f"100103type=1&q={keyword}",
            "page_type": "searchall",
            "page": str(page),
        }
        with httpx.Client(
            base_url=MOBILE_BASE_URL,
            headers=dict(MOBILE_HEADERS),
            cookies=self._credential.cookies if self._credential else {},
            follow_redirects=True,
            timeout=httpx.Timeout(self._timeout),
        ) as mob:
            raw = self._request("GET", MOBILE_SEARCH_URL, client=mob, params=params)
        # Extract card list
        cards = raw.get("data", {}).get("cards", [])
        results = []
        for card in cards:
            if card.get("card_type") == 9:
                mblog = card.get("mblog")
                if mblog:
                    results.append(mblog)
        return results

    # Weibo detail / comments / reposts

    def detail(self, mblogid: str) -> dict:
        """单条微博详情（需要登录）。"""
        return self._get(STATUSES_SHOW_URL, params={"id": mblogid}, action="微博详情", unwrap=False)

    def comments(self, weibo_id: str, count: int = 20, max_id: int = 0) -> list[dict]:
        """微博评论列表。"""
        params: dict[str, Any] = {
            "id": weibo_id, "is_show_bulletin": "2",
            "count": str(count), "flow": "0",
        }
        if max_id:
            params["max_id"] = str(max_id)
        data = self._get(BUILD_COMMENTS_URL, params=params, action="评论")
        return data.get("data", [])

    def reposts(self, weibo_id: str, page: int = 1, count: int = 10) -> list[dict]:
        """微博转发列表。"""
        data = self._get(
            REPOST_TIMELINE_URL,
            params={"id": weibo_id, "page": str(page), "count": str(count)},
            action="转发",
            unwrap=False,
        )
        return data.get("statuses", [])

    # User

    def profile(self, uid: str) -> dict:
        """用户资料（需要登录）。"""
        return self._get(PROFILE_INFO_URL, params={"uid": uid}, action="用户资料")

    def user_weibos(self, uid: str, page: int = 1, count: int = 20) -> list[dict]:
        """用户微博列表（需要登录）。"""
        data = self._get(MY_MBLOG_URL, params={"uid": uid, "page": str(page)}, action="用户微博")
        return data.get("list", [])

    def following(self, uid: str, page: int = 1) -> list[dict]:
        """用户关注列表（需要登录）。"""
        data = self._get(FRIENDS_URL, params={"uid": uid, "page": str(page)}, action="关注列表", unwrap=False)
        return data.get("users", [])

    def followers(self, uid: str, page: int = 1) -> list[dict]:
        """用户粉丝列表（需要登录）。"""
        data = self._get(
            FRIENDS_URL,
            params={"uid": uid, "page": str(page), "relate": "fans"},
            action="粉丝列表",
            unwrap=False,
        )
        return data.get("users", [])

    # Me

    def me(self) -> dict:
        """当前登录用户信息（需要登录）。
        
        先通过移动端 /api/config 拿 uid，再调 profile() 返回完整用户资料。
        """
        cookies = self._credential.cookies if self._credential else {}
        with httpx.Client(
            base_url=MOBILE_BASE_URL,
            headers=dict(MOBILE_HEADERS),
            cookies=cookies,
            follow_redirects=True,
            timeout=httpx.Timeout(self._timeout),
        ) as mob:
            raw = self._request("GET", "/api/config", client=mob)
        uid = str(raw.get("data", {}).get("uid", ""))
        if not uid:
            raise AuthRequiredError()
        return self.profile(uid)
