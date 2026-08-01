"""
XHS API Client

改造来源：jackwener/xiaohongshu-cli
https://github.com/jackwener/xiaohongshu-cli/blob/main/xhs_cli/client.py

主要改动：
- 移除 browser-cookie3 依赖，Cookie 通过构造函数直接传入
- 移除 click/rich/PyYAML/qrcode 依赖
- 移除 QR 登录、浏览器提取等认证相关方法
- 保留全部读写 API 方法
"""

import json
import logging
import random
import time
from typing import Any

import httpx

from .constants import CHROME_VERSION, CREATOR_HOST, EDITH_HOST, HOME_URL, USER_AGENT
from .creator_signing import sign_creator
from .exceptions import (
    IpBlockedError,
    NeedVerifyError,
    SessionExpiredError,
    SignatureError,
    UnsupportedOperationError,
    XhsApiError,
)
from .signing import build_get_uri, sign_main_api

logger = logging.getLogger(__name__)


def _cookies_str(cookies: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _search_id() -> str:
    num = (int(time.time() * 1000) << 64) + random.randint(0, 2147483646)
    alpha = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = ""
    while num > 0:
        result = alpha[num % 36] + result
        num //= 36
    return result or "0"


class XhsClient:
    """
    小红书 API 客户端。

    Cookie 直接通过构造函数传入，支持两种方式：

    方式一：dict 传入
        cookies = {"a1": "...", "web_session": "...", "webId": "..."}
        client = XhsClient(cookies)

    方式二：从环境变量读取（推荐在脚本中使用）
        import os
        client = XhsClient.from_env()
        # 需要设置：XHS_A1, XHS_WEB_SESSION, XHS_WEBID

    Cookie 获取方式（browser_use 自动获取，见 SKILL.md）：
        1. browser_use navigate → https://www.xiaohongshu.com
        2. browser_use get_cookies → 获取 a1 / web_session / webId
        3. 加载 offload env 文件，或直接从 tool 返回值中提取
    """

    def __init__(
        self,
        cookies: dict[str, str],
        timeout: float = 30.0,
        request_delay: float = 1.0,
        max_retries: int = 3,
    ):
        if not cookies.get("a1"):
            raise ValueError("cookies 必须包含 'a1' 字段")
        self.cookies = cookies
        self._http = httpx.Client(timeout=timeout, follow_redirects=True)
        self._delay = request_delay
        self._base_delay = request_delay
        self._max_retries = max_retries
        self._last_req = 0.0
        self._verify_count = 0

    @classmethod
    def from_env(cls, **kwargs) -> "XhsClient":
        """从环境变量构建客户端。需要 XHS_A1 / XHS_WEB_SESSION / XHS_WEBID。"""
        import os
        a1          = os.environ.get("XHS_A1", "")
        web_session = os.environ.get("XHS_WEB_SESSION", "")
        webid       = os.environ.get("XHS_WEBID", "")
        if not a1:
            raise ValueError("环境变量 XHS_A1 未设置")
        cookies = {"a1": a1}
        if web_session: cookies["web_session"] = web_session
        if webid:       cookies["webId"] = webid
        return cls(cookies, **kwargs)

    # ─── Context manager ──────────────────────────────────────────────────

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ─── Internal ─────────────────────────────────────────────────────────

    def _wait(self) -> None:
        """高斯抖动限速，模拟真实浏览行为。"""
        if self._delay <= 0:
            return
        elapsed = time.time() - self._last_req
        if elapsed < self._delay:
            jitter = max(0, random.gauss(0.3, 0.15))
            if random.random() < 0.05:
                jitter += random.uniform(2.0, 5.0)
            time.sleep(self._delay - elapsed + jitter)

    def _headers(self) -> dict[str, str]:
        return {
            "user-agent": USER_AGENT,
            "content-type": "application/json",
            "cookie": _cookies_str(self.cookies),
            "origin": HOME_URL,
            "referer": f"{HOME_URL}/",
            "sec-ch-ua": (
                f'"Chromium";v="{CHROME_VERSION}", '
                f'"Google Chrome";v="{CHROME_VERSION}", "Not-A.Brand";v="8"'
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "dnt": "1",
            "priority": "u=1, i",
        }

    def _parse(self, resp: httpx.Response) -> Any:
        if resp.status_code in (461, 471):
            self._verify_count += 1
            cooldown = min(30, 5 * (2 ** (self._verify_count - 1)))
            self._delay = max(self._delay, self._base_delay * 2)
            time.sleep(cooldown)
            raise NeedVerifyError(
                resp.headers.get("verifytype", ""),
                resp.headers.get("verifyuuid", ""),
            )
        self._verify_count = 0
        if not resp.text:
            return None
        try:
            data = json.loads(resp.text)
        except json.JSONDecodeError:
            raise XhsApiError(f"Non-JSON response: {resp.text[:200]}") from None
        if data.get("success"):
            return data.get("data", data.get("success"))
        code = data.get("code")
        if code == 300012: raise IpBlockedError()
        if code == 300015: raise SignatureError()
        if code == -100:   raise SessionExpiredError()
        raise XhsApiError(f"API error: {json.dumps(data)[:300]}", code=code, response=data)

    def _req(self, method: str, url: str, **kwargs) -> httpx.Response:
        self._wait()
        last_exc = None
        for attempt in range(self._max_retries):
            try:
                resp = self._http.request(method, url, **kwargs)
                self._last_req = time.time()
                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = (2 ** attempt) + random.random()
                    logger.warning("HTTP %d, retry %d in %.1fs", resp.status_code, attempt + 1, wait)
                    time.sleep(wait)
                    continue
                return resp
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exc = e
                wait = (2 ** attempt) + random.random()
                logger.warning("Network error: %s, retry %d in %.1fs", e, attempt + 1, wait)
                time.sleep(wait)
        raise XhsApiError(f"Request failed after {self._max_retries} retries: {last_exc}")

    # ─── Main API ─────────────────────────────────────────────────────────

    def _get(self, uri: str, params: dict | None = None) -> Any:
        sign = sign_main_api("GET", uri, self.cookies, params=params)
        url  = f"{EDITH_HOST}{build_get_uri(uri, params)}"
        return self._parse(self._req("GET", url, headers={**self._headers(), **sign}))

    def _post(self, uri: str, data: dict, extra: dict | None = None) -> Any:
        sign = sign_main_api("POST", uri, self.cookies, payload=data)
        hdrs = {**self._headers(), **sign}
        if extra: hdrs.update(extra)
        return self._parse(self._req(
            "POST", f"{EDITH_HOST}{uri}", headers=hdrs,
            content=json.dumps(data, separators=(",", ":")),
        ))

    # ─── Creator API ──────────────────────────────────────────────────────

    def _chost(self, uri: str) -> str:
        return CREATOR_HOST if uri.startswith("/api/galaxy/") else EDITH_HOST

    def _cget(self, uri: str, params: dict | None = None) -> Any:
        qs   = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        sign = sign_creator(f"url={uri}?{qs}" if qs else f"url={uri}", None, self.cookies["a1"])
        full = f"{uri}?{qs}" if qs else uri
        hdrs = {**self._headers(), **sign, "origin": CREATOR_HOST, "referer": f"{CREATOR_HOST}/"}
        return self._parse(self._req("GET", f"{self._chost(uri)}{full}", headers=hdrs))

    def _cpost(self, uri: str, data: dict) -> Any:
        sign = sign_creator(f"url={uri}", data, self.cookies["a1"])
        hdrs = {**self._headers(), **sign, "origin": CREATOR_HOST, "referer": f"{CREATOR_HOST}/"}
        return self._parse(self._req(
            "POST", f"{self._chost(uri)}{uri}", headers=hdrs,
            content=json.dumps(data, separators=(",", ":")),
        ))

    # ═══════════════════════════════════════════════════════════════════════
    # 公开 API
    # ═══════════════════════════════════════════════════════════════════════

    # ── 用户 ──────────────────────────────────────────────────────────────

    def get_self_info(self) -> dict:
        """获取当前登录用户信息。"""
        return self._get("/api/sns/web/v2/user/me")

    def get_user_info(self, user_id: str) -> dict:
        """获取指定用户主页信息。"""
        return self._get("/api/sns/web/v1/user/otherinfo", {"target_user_id": user_id})

    def get_user_notes(self, user_id: str, cursor: str = "") -> dict:
        """获取用户发布的笔记列表。"""
        return self._get("/api/sns/web/v1/user_posted",
                         {"num": 30, "cursor": cursor, "user_id": user_id,
                          "image_scenes": "FD_WM_WEBP"})

    # ── 搜索 ──────────────────────────────────────────────────────────────

    def search_notes(
        self, keyword: str, page: int = 1, page_size: int = 20,
        sort: str = "general", note_type: int = 0,
    ) -> Any:
        """
        搜索笔记。
        sort: "general" | "popularity_descending" | "time_descending"
        note_type: 0=全部, 1=视频, 2=图文
        """
        return self._post("/api/sns/web/v1/search/notes", {
            "keyword": keyword, "page": page, "page_size": page_size,
            "search_id": _search_id(), "sort": sort, "note_type": note_type,
        })

    def search_users(self, keyword: str, page: int = 1) -> Any:
        """搜索用户。"""
        return self._post("/api/sns/web/v1/search/users", {
            "keyword": keyword, "page": page, "page_size": 20,
            "search_id": _search_id(),
        })

    def search_topics(self, keyword: str) -> Any:
        """搜索话题/标签。"""
        return self._get("/api/sns/web/v1/search/topic",
                         {"keyword": keyword, "page": 1, "page_size": 20})

    # ── 笔记 ──────────────────────────────────────────────────────────────

    def get_note_by_id(self, note_id: str, xsec_token: str = "") -> Any:
        """获取笔记详情。"""
        return self._post("/api/sns/web/v1/feed", {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": 1},
            "xsec_source": "pc_feed",
            "xsec_token": xsec_token,
        })

    def get_comments(self, note_id: str, cursor: str = "", xsec_token: str = "") -> Any:
        """获取笔记评论（单页）。"""
        return self._get("/api/sns/web/v2/comment/page", {
            "note_id": note_id, "cursor": cursor,
            "top_comment_id": "", "image_formats": "jpg,webp,avif",
            "xsec_token": xsec_token,
        })

    def get_all_comments(
        self, note_id: str, xsec_token: str = "", max_pages: int = 20,
    ) -> list[dict]:
        """自动翻页获取全部评论。"""
        all_comments: list[dict] = []
        cursor = ""
        for _ in range(max_pages):
            data = self.get_comments(note_id, cursor=cursor, xsec_token=xsec_token)
            if not isinstance(data, dict): break
            all_comments.extend(data.get("comments", []))
            if not data.get("has_more") or not data.get("cursor"): break
            cursor = data["cursor"]
        return all_comments

    def get_sub_comments(
        self, note_id: str, comment_id: str, cursor: str = "", xsec_token: str = "",
    ) -> Any:
        """获取评论的回复。"""
        return self._get("/api/sns/web/v2/comment/sub/page", {
            "note_id": note_id, "root_comment_id": comment_id,
            "num": 20, "cursor": cursor, "xsec_token": xsec_token,
            "image_formats": "jpg,webp,avif",
        })

    # ── Feed / 发现 ───────────────────────────────────────────────────────

    def get_home_feed(self, category: str = "homefeed_recommend") -> dict:
        """获取推荐 Feed。"""
        return self._post("/api/sns/web/v1/homefeed", {
            "cursor_score": "", "num": 40, "refresh_type": 1,
            "note_index": 0, "unread_begin_note_id": "",
            "unread_end_note_id": "", "unread_note_count": 0,
            "category": category, "search_key": "", "need_num": 40,
            "image_scenes": ["FD_PRV_WEBP", "FD_WM_WEBP"],
        })

    def get_hot_feed(self, category: str = "homefeed.food_v3") -> dict:
        """
        获取热门笔记。
        category: homefeed.fashion_v3 / food_v3 / cosmetics_v3 /
                  movie_and_tv_v3 / career_v3 / love_v3 /
                  household_product_v3 / gaming_v3 / travel_v3 / fitness_v3
        """
        return self.get_home_feed(category=category)

    # ── 社交 ──────────────────────────────────────────────────────────────

    def follow_user(self, user_id: str) -> dict:
        """关注用户。"""
        return self._post("/api/sns/web/v1/user/follow", {"target_user_id": user_id})

    def unfollow_user(self, user_id: str) -> dict:
        """取消关注。"""
        return self._post("/api/sns/web/v1/user/unfollow", {"target_user_id": user_id})

    def get_user_favorites(self, user_id: str, cursor: str = "") -> dict:
        """获取用户收藏夹。"""
        return self._get("/api/sns/web/v2/note/collect/page",
                         {"user_id": user_id, "cursor": cursor, "num": 30})

    # ── 互动 ──────────────────────────────────────────────────────────────

    def like_note(self, note_id: str, xsec_token: str = "") -> dict:
        """点赞笔记。"""
        return self._post("/api/sns/web/v1/note/like",
                          {"note_id": note_id, "xsec_token": xsec_token})

    def unlike_note(self, note_id: str, xsec_token: str = "") -> dict:
        """取消点赞。"""
        return self._post("/api/sns/web/v1/note/like/remove",
                          {"note_id": note_id, "xsec_token": xsec_token})

    def collect_note(self, note_id: str, xsec_token: str = "") -> dict:
        """收藏笔记。"""
        return self._post("/api/sns/web/v1/note/collect",
                          {"note_id": note_id, "xsec_token": xsec_token})

    def uncollect_note(self, note_id: str, xsec_token: str = "") -> dict:
        """取消收藏。"""
        return self._post("/api/sns/web/v1/note/collect/remove",
                          {"note_id": note_id, "xsec_token": xsec_token})

    def post_comment(self, note_id: str, content: str, xsec_token: str = "") -> dict:
        """发表评论。"""
        return self._post("/api/sns/web/v1/comment/post", {
            "note_id": note_id, "content": content,
            "at_users": [], "xsec_token": xsec_token,
        })

    def reply_comment(
        self, note_id: str, comment_id: str, content: str, xsec_token: str = "",
    ) -> dict:
        """回复评论。"""
        return self._post("/api/sns/web/v1/comment/post", {
            "note_id": note_id, "content": content,
            "target_comment_id": comment_id,
            "at_users": [], "xsec_token": xsec_token,
        })

    def delete_comment(self, note_id: str, comment_id: str) -> dict:
        """删除自己的评论。"""
        return self._post("/api/sns/web/v1/comment/delete",
                          {"note_id": note_id, "comment_id": comment_id})

    # ── 通知 ──────────────────────────────────────────────────────────────

    def get_unread_count(self) -> dict:
        """获取未读通知数。"""
        return self._get("/api/sns/web/unread_count", {})

    def get_notifications_mentions(self, cursor: str = "", num: int = 20) -> dict:
        """获取评论 / @ 通知。"""
        return self._get("/api/sns/web/v1/you/mentions", {"num": num, "cursor": cursor})

    def get_notifications_likes(self, cursor: str = "", num: int = 20) -> dict:
        """获取点赞 / 收藏通知。"""
        return self._get("/api/sns/web/v1/you/likes", {"num": num, "cursor": cursor})

    def get_notifications_connections(self, cursor: str = "", num: int = 20) -> dict:
        """获取新增关注通知。"""
        return self._get("/api/sns/web/v1/you/connections", {"num": num, "cursor": cursor})

    # ── 创作者 ────────────────────────────────────────────────────────────

    def get_my_notes(self, page: int = 0) -> dict:
        """获取自己发布的笔记列表。"""
        return self._cget("/api/galaxy/v2/creator/note/user/posted",
                          {"tab": 0, "page": page})

    def delete_note(self, note_id: str) -> dict:
        """删除笔记（实验性，API 可能不可用）。"""
        try:
            return self._cpost("/api/galaxy/creator/note/delete", {"note_id": note_id})
        except XhsApiError as e:
            resp = e.response or {}
            if resp.get("status") == 404 or "404" in str(e):
                raise UnsupportedOperationError("Delete note API currently unavailable.") from None
            raise
