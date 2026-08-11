#!/usr/bin/env python3
"""
open_deep_link.py — Construct and open an Android app deep link, then confirm
the target app reached the foreground.

Why this script exists instead of a raw `android-open <url>`:
  * deep link construction (search queries, params) is URL-encoding-sensitive;
  * "opened" doesn't mean "foreground" — app may be missing, the scheme may be
    unregistered, or the view may be intercepted. This script verifies the
    foreground package and offers a configurable retry/fallback.

Usage (as a module):
    from open_deep_link import open_and_verify
    ok = open_and_verify(app_package="com.spotify.music",
                         url="spotify://search/firework")
"""

import argparse
import json
import subprocess
import time
import urllib.parse
import os

# Well-known scheme -> expected foreground package.
KNOWN_APPS = {
    "spotify": "com.spotify.music",
    "weixin": "com.tencent.mm",
    "youtube": "com.google.android.youtube",
    "bilibili": "tv.danmaku.bili",
    "douyin": "com.ss.android.ugc.aweme",
}


def foreground_package() -> str | None:
    """Return the currently focused/active package via ui info."""
    try:
        proc = subprocess.run(
            ["android-a11y-cli", "ui", "info", "--compact"],
            capture_output=True, text=True, timeout=15,
        )
        payload = proc.stdout
        start = payload.find("{")
        data = json.loads(payload[start:])
        if not data.get("ok"):
            return None
        return data["data"].get("packageName")
    except Exception:
        return None


def open_url(url: str) -> bool:
    """Fire android-open and return success."""
    try:
        proc = subprocess.run(
            ["android-open", url], capture_output=True, text=True, timeout=20
        )
        return proc.returncode == 0
    except Exception:
        return False


def wait_for_package(pkg: str | None, timeout: float = 8.0) -> bool:
    """Poll until the expected package reaches foreground, or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        cur = foreground_package()
        if pkg is None or cur == pkg:
            return True
        time.sleep(0.5)
    return False


def build_search_url(scheme: str, query: str, key: str = "search") -> str:
    """Construct <scheme>://<key>/<urlencoded-query> safely."""
    q = urllib.parse.quote(query, safe="")
    return f"{scheme}://{key}/{q}"


def open_and_verify(url: str, expected_pkg: str | None = None,
                    retries: int = 2, timeout: float = 8.0) -> dict:
    """Open a deep link and confirm the app reached foreground.

    Returns a dict with ok, url, package, attempts. Raises ValueError on
    malformed scheme; never raises on runtime failure (returns ok=False).
    """
    scheme = urllib.parse.urlparse(url).scheme
    if not scheme:
        raise ValueError(f"not a deep link (no scheme): {url}")

    expected = expected_pkg or KNOWN_APPS.get(scheme)

    attempts = 0
    last_err = None
    while attempts <= retries:
        attempts += 1
        if not open_url(url):
            last_err = f"android-open returned non-zero (attempt {attempts})"
            time.sleep(1.0)
            continue
        if wait_for_package(expected, timeout=timeout):
            return {
                "ok": True,
                "url": url,
                "scheme": scheme,
                "expected_pkg": expected,
                "got_pkg": foreground_package(),
                "attempts": attempts,
            }
        last_err = f"expected {expected} but got {foreground_package()}"
        time.sleep(1.0)

    return {
        "ok": False,
        "url": url,
        "scheme": scheme,
        "expected_pkg": expected,
        "got_pkg": foreground_package(),
        "attempts": attempts,
        "error": last_err,
    }


def main():
    p = argparse.ArgumentParser(description="Open a deep link and verify foreground.")
    p.add_argument("url", help="deep link, e.g. spotify://search/circles")
    p.add_argument("--pkg", help="expected foreground package override")
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--timeout", type=float, default=8.0)
    a = p.parse_args()
    try:
        result = open_and_verify(a.url, a.pkg, a.retries, a.timeout)
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    import sys
    main()