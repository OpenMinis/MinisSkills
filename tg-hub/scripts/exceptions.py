"""
Structured exception hierarchy for tg-hub.

改造来源：jackwener/tg-cli
https://github.com/jackwener/tg-cli/blob/main/src/tg_cli/exceptions.py
"""

from __future__ import annotations


class TGHubError(Exception):
    """Base exception for tg-hub."""

class NotAuthenticatedError(TGHubError):
    """Telegram 凭证缺失或 session 无效。"""

class ChatNotFoundError(TGHubError):
    """无法通过名称或 ID 找到聊天。"""

class SyncError(TGHubError):
    """同步操作失败。"""
