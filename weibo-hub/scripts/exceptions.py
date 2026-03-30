"""Custom exceptions for weibo-hub."""

from __future__ import annotations


class WeiboError(Exception):
    """Base exception for all Weibo API errors."""

    def __init__(self, message: str, code: int | str | None = None):
        super().__init__(message)
        self.code = code


class SessionExpiredError(WeiboError):
    """Session cookies have expired — re-run auth."""

    def __init__(self):
        super().__init__("会话已过期，请重新认证（调用 WeiboClient.setup_credential()）", code="session_expired")


class AuthRequiredError(WeiboError):
    """No credential found."""

    def __init__(self):
        super().__init__("未找到凭证，请先调用 WeiboClient.setup_credential()", code="not_authenticated")


class RateLimitError(WeiboError):
    """Too many requests."""

    def __init__(self):
        super().__init__("请求过于频繁，请稍后再试", code="rate_limited")
