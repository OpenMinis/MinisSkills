"""Authentication for Boss Zhipin.

Strategy:
1. Try loading saved credential from ~/.config/boss-cli/credential.json
2. Try extracting cookies from local browsers via browser-cookie3
3. Fallback: QR code login in terminal
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
import time
from typing import Any

import httpx
import qrcode

from boss_cli.constants import (
    BASE_URL,
    CONFIG_DIR,
    CREDENTIAL_FILE,
    HEADERS,
    QR_DISPATCHER_URL,
    QR_RANDKEY_URL,
    QR_SCAN_LOGIN_URL,
    QR_SCAN_URL,
)

logger = logging.getLogger(__name__)

# Credential TTL: warn and attempt refresh after 7 days
CREDENTIAL_TTL_DAYS = 7
_CREDENTIAL_TTL_SECONDS = CREDENTIAL_TTL_DAYS * 86400

# QR poll config
POLL_TIMEOUT_S = 240  # 4 minutes


# ── Credential data class ───────────────────────────────────────────

class Credential:
    """Holds Boss Zhipin session cookies."""

    def __init__(self, cookies: dict[str, str]):
        self.cookies = cookies

    @property
    def is_valid(self) -> bool:
        return bool(self.cookies)

    def to_dict(self) -> dict[str, Any]:
        return {"cookies": self.cookies, "saved_at": time.time()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Credential:
        return cls(cookies=data.get("cookies", {}))

    def as_cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())


# ── Credential persistence ──────────────────────────────────────────

def save_credential(credential: Credential) -> None:
    """Save credential to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIAL_FILE.write_text(json.dumps(credential.to_dict(), indent=2, ensure_ascii=False))
    CREDENTIAL_FILE.chmod(0o600)
    logger.info("Credential saved to %s", CREDENTIAL_FILE)


def load_credential() -> Credential | None:
    """Load credential from saved file with TTL-based auto-refresh.

    If saved cookies are older than 7 days, automatically attempt to
    refresh from the browser before falling back to stale cookies.
    """
    if not CREDENTIAL_FILE.exists():
        return None
    try:
        data = json.loads(CREDENTIAL_FILE.read_text())
        cred = Credential.from_dict(data)
        if not cred.is_valid:
            return None

        # Check TTL — auto-refresh if stale
        saved_at = data.get("saved_at", 0)
        if saved_at and (time.time() - saved_at) > _CREDENTIAL_TTL_SECONDS:
            logger.info(
                "Credential older than %d days, attempting browser refresh",
                CREDENTIAL_TTL_DAYS,
            )
            fresh = extract_browser_credential()
            if fresh:
                logger.info("Auto-refreshed credential from browser")
                return fresh
            logger.warning(
                "Cookie refresh failed; using existing cookies (age: %d+ days)",
                CREDENTIAL_TTL_DAYS,
            )
        return cred
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to load saved credential: %s", e)
    return None


def clear_credential() -> None:
    """Remove saved credential file."""
    if CREDENTIAL_FILE.exists():
        CREDENTIAL_FILE.unlink()
        logger.info("Credential removed: %s", CREDENTIAL_FILE)


# ── Browser cookie extraction ───────────────────────────────────────

def extract_browser_credential(cookie_source: str | None = None) -> Credential | None:
    """Extract Boss Zhipin cookies from local browsers via browser-cookie3.

    Args:
        cookie_source: Optional browser name to extract from (e.g., 'chrome', 'arc').
                       If None, tries all supported browsers in order.
    """
    extract_script = '''
import json, sys
try:
    import browser_cookie3 as bc3
except ImportError:
    print(json.dumps({"error": "not_installed"}))
    sys.exit(0)

target = sys.argv[1] if len(sys.argv) > 1 else None

browsers = [
    ("Chrome", bc3.chrome),
    ("Firefox", bc3.firefox),
    ("Edge", bc3.edge),
    ("Brave", bc3.brave),
    ("Chromium", bc3.chromium),
    ("Opera", bc3.opera),
    ("Vivaldi", bc3.vivaldi),
]

# Try adding optional browsers (not all browser_cookie3 versions support these)
for name, attr in [("Arc", "arc"), ("Safari", "safari"), ("LibreWolf", "librewolf")]:
    fn = getattr(bc3, attr, None)
    if fn:
        browsers.append((name, fn))

if target:
    target_lower = target.lower()
    browsers = [(n, fn) for n, fn in browsers if n.lower() == target_lower]
    if not browsers:
        print(json.dumps({"error": f"unsupported_browser: {target}"}))
        sys.exit(0)

for name, loader in browsers:
    try:
        cj = loader(domain_name=".zhipin.com")
        cookies = {c.name: c.value for c in cj if "zhipin.com" in (c.domain or "")}
        if cookies:
            print(json.dumps({"browser": name, "cookies": cookies}))
            sys.exit(0)
    except Exception:
        pass

print(json.dumps({"error": "no_cookies"}))
'''

    try:
        cmd = [sys.executable, "-c", extract_script]
        if cookie_source:
            cmd.append(cookie_source)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            logger.debug("Cookie extraction subprocess failed: %s", result.stderr)
            return None

        output = result.stdout.strip()
        if not output:
            return None

        data = json.loads(output)
        if "error" in data:
            if data["error"] == "not_installed":
                logger.debug("browser-cookie3 not installed, skipping")
            else:
                logger.debug("No valid Boss Zhipin cookies found: %s", data["error"])
            return None

        cookies = data["cookies"]
        browser_name = data["browser"]
        logger.info("Found cookies in %s (%d cookies)", browser_name, len(cookies))
        cred = Credential(cookies=cookies)
        save_credential(cred)
        return cred

    except subprocess.TimeoutExpired:
        logger.warning("Cookie extraction timed out (browser may be running)")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Cookie extraction parse error: %s", e)
        return None


# ── QR Code terminal rendering ──────────────────────────────────────

def _render_qr_half_blocks(matrix: list[list[bool]]) -> str:
    """Render QR matrix using Unicode half-block characters (▀▄█ and space).

    Same approach as xiaohongshu-cli: two rows are combined into one
    terminal line using half-block glyphs, halving the vertical space.
    """
    if not matrix:
        return ""

    # Add 1-module quiet zone
    size = len(matrix)
    padded = [[False] * (size + 2)]
    for row in matrix:
        padded.append([False] + list(row) + [False])
    padded.append([False] * (size + 2))
    matrix = padded
    rows = len(matrix)

    # Check terminal width
    term_cols = shutil.get_terminal_size(fallback=(80, 24)).columns
    qr_width = len(matrix[0])
    if qr_width > term_cols:
        logger.warning("Terminal too narrow (%d) for QR (%d)", term_cols, qr_width)
        return ""

    lines: list[str] = []
    for y in range(0, rows, 2):
        line = ""
        top_row = matrix[y]
        bottom_row = matrix[y + 1] if y + 1 < rows else [False] * len(top_row)
        for x in range(len(top_row)):
            top = top_row[x]
            bottom = bottom_row[x]
            if top and bottom:
                line += "█"
            elif top and not bottom:
                line += "▀"
            elif not top and bottom:
                line += "▄"
            else:
                line += " "
        lines.append(line)
    return "\n".join(lines)


def _display_qr_in_terminal(data: str) -> bool:
    """Display *data* as a QR code in the terminal using Unicode half-blocks.

    Returns True on success.
    """
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(data)
    qr.make(fit=True)
    modules = qr.get_matrix()

    rendered = _render_qr_half_blocks(modules)
    if rendered:
        print(rendered)
        return True

    # Fallback to basic ASCII
    qr2 = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=1,
    )
    qr2.add_data(data)
    qr2.make(fit=True)
    qr2.print_ascii(invert=True)
    return True


# ── QR Login flow ───────────────────────────────────────────────────

async def _get_qr_session(client: httpx.AsyncClient) -> dict[str, str]:
    """Step 1: Get QR session (qrId, randKey, secretKey)."""
    resp = await client.post(QR_RANDKEY_URL)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to get QR session: {data.get('message', 'Unknown error')}")
    return data["zpData"]


async def _wait_for_scan(client: httpx.AsyncClient, qr_id: str) -> bool:
    """Step 3: Long-poll waiting for QR scan."""
    try:
        resp = await client.get(QR_SCAN_URL, params={"uuid": qr_id}, timeout=35)
        resp.raise_for_status()
        data = resp.json()
        return data.get("scaned", False)
    except httpx.ReadTimeout:
        return False


async def _wait_for_confirm(client: httpx.AsyncClient, qr_id: str) -> bool:
    """Step 4: Long-poll waiting for login confirmation."""
    try:
        resp = await client.get(QR_SCAN_LOGIN_URL, params={"qrId": qr_id}, timeout=35)
        resp.raise_for_status()
        return resp.status_code == 200
    except httpx.ReadTimeout:
        return False


async def _dispatch_login(client: httpx.AsyncClient, qr_id: str) -> Credential:
    """Step 5: Get final login cookies via dispatcher."""
    resp = await client.get(
        QR_DISPATCHER_URL,
        params={"qrId": qr_id, "pk": "header-login"},
    )
    resp.raise_for_status()

    # Extract cookies from response
    cookies = {}
    for name, value in resp.cookies.items():
        cookies[name] = value

    # Also grab cookies accumulated on the client
    for name, value in client.cookies.items():
        cookies[name] = value

    if not cookies:
        raise RuntimeError("Login dispatcher returned no cookies")

    return Credential(cookies=cookies)


async def qr_login() -> Credential:
    """Full QR code login flow.

    1. Get QR session
    2. Display QR code in terminal (Unicode half-blocks)
    3. Wait for scan (long-polling)
    4. Wait for confirm (long-polling)
    5. Dispatch to get cookies
    """
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers=HEADERS,
        follow_redirects=True,
        timeout=httpx.Timeout(30, read=40),
    ) as client:
        # Step 1: Get QR session
        session = await _get_qr_session(client)
        qr_id = session["qrId"]

        # Step 2: Display QR code in terminal using Unicode half-blocks
        print("\n📱 请使用 Boss 直聘 APP 扫描以下二维码登录:\n")
        _display_qr_in_terminal(qr_id)
        print("\n⏳ 扫码后请在手机上确认登录...")
        print(f"   (QR ID: {qr_id[:20]}...)\n")

        # Step 3: Wait for scan
        max_retries = 6  # ~3 min with 30s timeout each
        scanned = False
        for _ in range(max_retries):
            scanned = await _wait_for_scan(client, qr_id)
            if scanned:
                print("  📲 已扫码，请在手机上确认...")
                break

        if not scanned:
            raise RuntimeError("二维码已过期，请重试 (boss login)")

        # Step 4: Wait for confirm
        confirmed = False
        for _ in range(max_retries):
            confirmed = await _wait_for_confirm(client, qr_id)
            if confirmed:
                break

        if not confirmed:
            raise RuntimeError("确认超时，请重试 (boss login)")

        # Step 5: Dispatch
        credential = await _dispatch_login(client, qr_id)
        save_credential(credential)
        print("\n✅ 登录成功！凭证已保存到", CREDENTIAL_FILE)
        return credential


# ── Environment variable credential ────────────────────────────────

def load_env_credential() -> Credential | None:
    """Load credential from environment variables.
    
    Supports:
    - BOSS_COOKIE: Full cookie string "wt2=xxx;wbg=xxx"
    - BOSS_WT2, BOSS_WBG: Individual cookie values
    """
    import os
    
    # Try full cookie string
    cookie_str = os.environ.get("BOSS_COOKIE")
    if cookie_str:
        cookies = {}
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                cookies[key] = value
        if cookies:
            logger.info("Loaded credential from BOSS_COOKIE env var")
            return Credential(cookies=cookies)
    
    # Try individual cookies
    wt2 = os.environ.get("BOSS_WT2")
    wbg = os.environ.get("BOSS_WBG")
    if wt2 or wbg:
        cookies = {}
        if wt2:
            cookies["wt2"] = wt2
        if wbg:
            cookies["wbg"] = wbg
        if cookies:
            logger.info("Loaded credential from BOSS_WT2/BOSS_WBG env vars")
            return Credential(cookies=cookies)
    
    return None


# ── Unified get_credential ──────────────────────────────────────────

def get_credential() -> Credential | None:
    """Try all auth methods and return credential.

    Priority:
    1. Environment variables (BOSS_COOKIE or BOSS_WT2 + BOSS_WBG)
    2. Saved credential file
    3. QR code login (if no other method available)
    """
    # 1. Try environment variables first
    cred = load_env_credential()
    if cred:
        logger.info("Loaded credential from environment variables")
        return cred

    # 2. Try saved credential file
    cred = load_credential()
    if cred:
        logger.info("Loaded credential from %s", CREDENTIAL_FILE)
        return cred

    # 3. Browser extraction disabled (browser-cookie3 removed)
    # Fall back to QR login handled by caller
    
    return None
