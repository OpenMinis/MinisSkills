"""Credential management for weibo-hub.

Auth strategy (no browser-cookie3, no QR code):
  1. Load saved credential from /var/minis/workspace/weibo-hub/credential.json
  2. If missing/expired, agent calls setup_credential(cookies_dict) with cookies
     obtained via browser_use get_cookies on weibo.com.
  3. Credential persisted with 7-day TTL; auto-warns when stale.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .constants import CREDENTIAL_FILE, CREDENTIAL_TTL_DAYS, DATA_DIR, REQUIRED_COOKIES
from .exceptions import AuthRequiredError


# ── Credential ────────────────────────────────────────────────────────

class Credential:
    """Holds Weibo session cookies."""

    def __init__(self, cookies: dict[str, str]):
        self.cookies = cookies

    @property
    def is_valid(self) -> bool:
        return bool(self.cookies) and bool(REQUIRED_COOKIES & set(self.cookies))

    def to_dict(self) -> dict[str, Any]:
        return {"cookies": self.cookies, "saved_at": time.time()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Credential":
        return cls(cookies=data.get("cookies", {}))

    def as_cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())


# ── Persistence ───────────────────────────────────────────────────────

def save_credential(credential: Credential) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIAL_FILE.write_text(json.dumps(credential.to_dict(), indent=2, ensure_ascii=False))
    CREDENTIAL_FILE.chmod(0o600)


def load_credential() -> Credential | None:
    """Load credential from disk; warn if older than TTL."""
    if not CREDENTIAL_FILE.exists():
        return None
    try:
        data = json.loads(CREDENTIAL_FILE.read_text())
        cred = Credential.from_dict(data)
        if not cred.is_valid:
            return None
        saved_at = data.get("saved_at", 0)
        age_days = (time.time() - saved_at) / 86400
        if age_days > CREDENTIAL_TTL_DAYS:
            print(
                f"[weibo-hub] ⚠️  凭证已存储 {age_days:.0f} 天（TTL={CREDENTIAL_TTL_DAYS}天），"
                "建议重新调用 setup_credential() 刷新"
            )
        return cred
    except (json.JSONDecodeError, KeyError):
        return None


def clear_credential() -> None:
    if CREDENTIAL_FILE.exists():
        CREDENTIAL_FILE.unlink()


def setup_credential(cookies: dict[str, str]) -> Credential:
    """Create and persist a Credential from a cookies dict.

    Typically called by the agent after browser_use get_cookies on weibo.com:

        cookies = {"SUB": "...", "SUBP": "...", ...}
        cred = setup_credential(cookies)

    Returns the saved Credential.
    """
    cred = Credential(cookies=cookies)
    if not cred.is_valid:
        missing = REQUIRED_COOKIES - set(cookies)
        raise ValueError(
            f"Cookie 不完整，缺少必要字段: {missing}。"
            "请在浏览器中登录 weibo.com 后重新提取。"
        )
    save_credential(cred)
    print(f"[weibo-hub] ✅ 凭证已保存（{len(cookies)} 个 Cookie），有效期 {CREDENTIAL_TTL_DAYS} 天")
    return cred
