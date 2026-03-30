"""
Custom exceptions for bilibili-hub.

改造来源：jackwener/bilibili-cli
https://github.com/jackwener/bilibili-cli/blob/main/bili_cli/exceptions.py
"""


class BiliError(Exception):
    """Base exception."""

class InvalidBvidError(BiliError):
    """BV 号格式错误。"""

class NetworkError(BiliError):
    """网络/API 请求失败。"""

class AuthenticationError(BiliError):
    """认证信息缺失或无效。"""

class RateLimitError(BiliError):
    """触发 B 站反爬限速（HTTP 412/429）。"""

class NotFoundError(BiliError):
    """视频、用户或资源不存在。"""
