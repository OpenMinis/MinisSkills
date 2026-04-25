#!/usr/bin/env python3
"""
ChatGPT Auth Token Fetcher
Fetches the accessToken from https://chatgpt.com/api/auth/session via minis-browser-use.
- If already cached in ~/.chatgpt_auth.json, returns it directly.
- If not, opens chatgpt.com login page and polls every 30s (up to 5 min) in a new tab.
- Saves the token to ~/.chatgpt_auth.json on success.
"""
import json, os, sys, time, subprocess

AUTH_CACHE = os.path.expanduser("~/.chatgpt_auth.json")
SESSION_URL = "https://chatgpt.com/api/auth/session"
LOGIN_URL = "https://chatgpt.com/auth/login"
MAX_WAIT = 300   # 5 minutes
POLL_INTERVAL = 10


def browser(action: str, **kwargs) -> dict:
    """Run a minis-browser-use action and return parsed JSON output."""
    # Build CLI args from action + kwargs
    cmd = ["minis-browser-use", action]
    tab_id = kwargs.pop("tab_id", None)
    for k, v in kwargs.items():
        cmd.append(f"--{k.replace('_', '-')}")
        cmd.append(str(v))
    if tab_id is not None:
        cmd += ["--tab-id", str(tab_id)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        stdout = result.stdout.strip()
        if stdout:
            try:
                return json.loads(stdout)
            except Exception:
                return {"text": stdout}
        return {"error": result.stderr.strip()}
    except Exception as e:
        return {"error": str(e)}


def fetch_session_json(tab_id=None) -> dict | None:
    """Navigate to the session URL in a tab and try to parse JSON."""
    nav_kwargs = {}
    if tab_id is not None:
        nav_kwargs["tab_id"] = tab_id
    browser("navigate", url=SESSION_URL, **nav_kwargs)

    # Wait for DOM to settle
    browser("wait_for_dom_stable", timeout=8000, **nav_kwargs)

    # Get page text
    text_result = browser("get_text", **nav_kwargs)

    text = ""
    if isinstance(text_result, dict):
        data_field = text_result.get("data", {})
        if isinstance(data_field, dict):
            text = data_field.get("text", "") or data_field.get("content", "")
        text = text or text_result.get("text", "") or text_result.get("content", "")
    if not text:
        return None

    # Try to parse JSON
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and data.get("accessToken"):
            return data
    except Exception:
        pass

    # Also try extracting JSON from page source
    import re
    m = re.search(r'\{.*"accessToken"\s*:\s*"[^"]+".*\}', text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if data.get("accessToken"):
                return data
        except Exception:
            pass

    return None


def save_cache(data: dict):
    """Only cache the token and timestamp — discard PII fields (email, user_id, etc.)."""
    cache = {
        "accessToken": data["accessToken"],
        "_cached_at": int(time.time()),
    }
    with open(AUTH_CACHE, "w") as f:
        json.dump(cache, f)
    os.chmod(AUTH_CACHE, 0o600)


def load_cache() -> dict | None:
    if not os.path.exists(AUTH_CACHE):
        return None
    try:
        with open(AUTH_CACHE) as f:
            data = json.load(f)
        token = data.get("accessToken", "")
        if not token:
            return None
        # Treat cache as valid for 8 hours
        cached_at = data.get("_cached_at", 0)
        if time.time() - cached_at > 8 * 3600:
            print("[auth] Cached token expired (>8h), re-fetching...", file=sys.stderr)
            return None
        return data
    except Exception:
        return None


def test_open(url: str):
    """Quick test: open a URL via minis-open and verify it succeeds."""
    print(f"[test-open] 正在用 minis-open 打开: {url}", file=sys.stderr)
    result = subprocess.run(["minis-open", url], capture_output=True, text=True)
    ok = result.returncode == 0
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if ok:
        print(f"[test-open] ✅ 成功 (returncode=0)", file=sys.stderr)
        if stdout:
            print(f"[test-open] stdout: {stdout}", file=sys.stderr)
    else:
        print(f"[test-open] ❌ 失败 (returncode={result.returncode})", file=sys.stderr)
        if stderr:
            print(f"[test-open] stderr: {stderr}", file=sys.stderr)
    print(json.dumps({"success": ok, "url": url, "returncode": result.returncode,
                      "stdout": stdout, "stderr": stderr}))
    sys.exit(0 if ok else 1)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-login", action="store_true",
                        help="Only check session, do not open login page. Exit with error if not logged in.")
    parser.add_argument("--test-open", metavar="URL", nargs="?",
                        const="https://chatgpt.com",
                        help="快速测试 minis-open 是否能正常打开 URL（默认: https://chatgpt.com），测试后直接退出。")
    parser.add_argument("--start-auth", action="store_true",
                        help="跳过 cache/session 检查，直接打开 ChatGPT 登录页开始授权流程。")
    args = parser.parse_args()

    # --test-open: 快速验证 minis-open 是否正常工作
    if args.test_open is not None:
        test_open(args.test_open)

    # --start-auth: 跳过缓存和 session 检查，直接跳转登录页
    if args.start_auth:
        print("[auth] --start-auth: 直接打开 ChatGPT 登录页...", file=sys.stderr)
        subprocess.run(["minis-open", LOGIN_URL])
        print("[auth] 请在弹出的页面中完成 ChatGPT 登录，登录后脚本将自动继续...", file=sys.stderr)
        print(f"[auth] 将每 {POLL_INTERVAL}s 检查一次，最多等待 {MAX_WAIT}s。", file=sys.stderr)
        # 直接进入 polling 逻辑
        deadline = time.time() + MAX_WAIT
        poll_tab_id = None
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL)
            remaining = int(deadline - time.time())
            print(f"[auth] Polling session... ({remaining}s remaining)", file=sys.stderr)
            if poll_tab_id is None:
                new_tab_result = browser("new_tab")
                if isinstance(new_tab_result, dict):
                    data_field = new_tab_result.get("data", new_tab_result)
                    poll_tab_id = data_field.get("tab_id") if isinstance(data_field, dict) else None
            data = fetch_session_json(tab_id=poll_tab_id)
            if data and data.get("accessToken"):
                if poll_tab_id is not None:
                    browser("close_tab", tab_id=poll_tab_id)
                save_cache(data)
                print("[auth] Login detected! Token saved.", file=sys.stderr)
                print(json.dumps({"success": True, "source": "login"}))
                return
        print("[auth] Timed out waiting for login.", file=sys.stderr)
        print(json.dumps({"success": False, "error": "Timed out waiting for ChatGPT login (5 min)"}))
        sys.exit(1)

    # 1. Check cache first
    cached = load_cache()
    if cached:
        print("[auth] Using cached token.", file=sys.stderr)
        # Token is NOT printed to stdout — callers must read from AUTH_CACHE directly
        print(json.dumps({"success": True, "source": "cache"}))
        return

    # 2. Try fetching session directly (user may already be logged in)
    print("[auth] Checking existing ChatGPT session...", file=sys.stderr)
    data = fetch_session_json()
    if data and data.get("accessToken"):
        save_cache(data)
        print("[auth] Got token from existing session.", file=sys.stderr)
        # Token is NOT printed to stdout — callers must read from AUTH_CACHE directly
        print(json.dumps({"success": True, "source": "session"}))
        return

    # 3. If --no-login, bail out immediately without opening login page
    if args.no_login:
        print("[auth] Not logged in (--no-login mode, skipping login page).", file=sys.stderr)
        print(json.dumps({"success": False, "error": "not_logged_in"}))
        sys.exit(1)

    # 4. Open login page in foreground via minis-open (shows to user)
    print("[auth] Not logged in. Opening ChatGPT login page...", file=sys.stderr)
    subprocess.run(["minis-open", LOGIN_URL])
    print("[auth] 请在弹出的页面中完成 ChatGPT 登录，登录后脚本将自动继续...", file=sys.stderr)
    print(f"[auth] 将每 {POLL_INTERVAL}s 检查一次，最多等待 {MAX_WAIT}s。", file=sys.stderr)

    deadline = time.time() + MAX_WAIT
    poll_tab_id = None

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        remaining = int(deadline - time.time())
        print(f"[auth] Polling session... ({remaining}s remaining)", file=sys.stderr)

        # Open a new tab to check session (avoids interrupting login tab)
        if poll_tab_id is None:
            new_tab_result = browser("new_tab")
            if isinstance(new_tab_result, dict):
                data_field = new_tab_result.get("data", new_tab_result)
                poll_tab_id = data_field.get("tab_id") if isinstance(data_field, dict) else None

        data = fetch_session_json(tab_id=poll_tab_id)
        if data and data.get("accessToken"):
            # Close the poll tab
            if poll_tab_id is not None:
                browser("close_tab", tab_id=poll_tab_id)
            save_cache(data)
            print("[auth] Login detected! Token saved.", file=sys.stderr)
            # Token is NOT printed to stdout — callers must read from AUTH_CACHE directly
            print(json.dumps({"success": True, "source": "login"}))
            return

    print("[auth] Timed out waiting for login.", file=sys.stderr)
    print(json.dumps({"success": False, "error": "Timed out waiting for ChatGPT login (5 min)"}))
    sys.exit(1)


if __name__ == "__main__":
    main()
