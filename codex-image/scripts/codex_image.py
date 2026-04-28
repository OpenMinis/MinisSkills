#!/usr/bin/env python3
"""
Codex Image Generation via ChatGPT backend API.
Uses gpt-image-2 through the Codex responses endpoint with stream=true.
"""
import json, re, base64, http.client, ssl, sys, os, time, subprocess

AUTH_CACHE = os.path.expanduser("~/.chatgpt_auth.json")


def get_token_auto(no_login=False) -> str:
    """Get ChatGPT access token via get_auth.py (auto login flow).

    get_auth.py intentionally does NOT print the token to stdout (to avoid
    leaking credentials into logs or conversation context). Instead, it writes
    the token to AUTH_CACHE (~/.chatgpt_auth.json, chmod 600) and we read it
    from there after the subprocess exits successfully.

    Args:
        no_login: If True, only check session/cache, don't open login page.
    """
    script = os.path.join(os.path.dirname(__file__), "get_auth.py")
    cmd = [sys.executable, script]
    if no_login:
        cmd.append("--no-login")
    # T172: do NOT capture stdout. get_auth.py emits OSC 1337 markers (via
    # `minis-open <login_url>`) that the host ChatViewModel must see in order
    # to pop the WebView login sheet. capture_output=True swallows those
    # markers so the user never sees the login page and the script polls
    # uselessly for 5 minutes. Pass stdout through; success signal comes
    # from process exit code + presence of the auth cache file.
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, timeout=360)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"get_auth.py exited rc={result.returncode}. stderr: {result.stderr[:300]}")
    # Read token from cache file — get_auth.py writes it on success
    try:
        with open(AUTH_CACHE) as f:
            cached = json.load(f)
        token = cached.get("accessToken", "")
        if not token:
            raise RuntimeError("Cache file exists but accessToken is empty.")
        return token
    except FileNotFoundError:
        raise RuntimeError("get_auth.py exited 0 but no cache file was written")
    except Exception as e:
        raise RuntimeError(f"Failed to read token from cache after auth: {e}")

def is_oauth_error(result: dict) -> bool:
    """Check if the error is an OAuth/auth related error."""
    err = result.get("error", "")
    return any(k in err.lower() for k in ["401", "403", "unauthorized", "forbidden", "oauth", "token", "invalid_api_key", "authentication"])


def generate_image(token: str, prompt: str, output_path: str, model: str = "gpt-5.4", effort: str = "low") -> dict:
    """Generate an image via Codex image_generation tool.
    
    Args:
        token: ChatGPT access token (Bearer token from chatgpt.com)
        prompt: Image generation prompt
        output_path: Output file path for the generated image
        model: Model to use (default: gpt-5.4)
        effort: Reasoning effort level (default: low)
    
    Returns:
        dict with keys: success, path, revised_prompt, usage, error
    """
    payload = json.dumps({
        "model": model,
        "instructions": "You are a helpful assistant. Use tools when available.",
        "input": [{"role": "user", "content": f"Use the image generation tool to create: {prompt}"}],
        "store": False,
        "tools": [{"type": "image_generation"}],
        "reasoning": {"effort": effort},
        "include": [],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
        "stream": True
    })

    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("chatgpt.com", context=ctx, timeout=180)
    conn.request("POST", "/backend-api/codex/responses", body=payload, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    })
    resp = conn.getresponse()

    if resp.status != 200:
        body = resp.read().decode("utf-8", errors="replace")
        conn.close()
        return {"success": False, "error": f"HTTP {resp.status}: {body[:500]}"}

    chunks = []
    while True:
        chunk = resp.read(65536)
        if not chunk:
            break
        chunks.append(chunk)
    conn.close()

    data = b"".join(chunks).decode("utf-8", errors="replace")

    # Extract base64 PNG
    matches = re.findall(r'(iVBOR[A-Za-z0-9+/=]{1000,})', data)
    if not matches:
        return {"success": False, "error": "No image data in response"}

    img = base64.b64decode(matches[0])
    with open(output_path, "wb") as f:
        f.write(img)

    # Extract revised_prompt
    revised = ""
    m = re.search(r'"revised_prompt"\s*:\s*"([^"]*)"', data)
    if m:
        revised = m.group(1)

    # Extract usage
    usage = {}
    m = re.search(r'"usage"\s*:\s*(\{[^}]+\})', data)
    if m:
        try:
            usage = json.loads(m.group(1))
        except:
            pass

    return {
        "success": True,
        "path": output_path,
        "size": len(img),
        "revised_prompt": revised,
        "usage": usage
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate images via Codex API")
    parser.add_argument("prompt", help="Image generation prompt")
    parser.add_argument("--token", help="ChatGPT access token (or set CODEX_IMAGE_TOKEN env)")
    parser.add_argument("--token-file", help="File containing the access token")
    parser.add_argument("--output", "-o", default="codex_image.png", help="Output file path")
    parser.add_argument("--model", default="gpt-5.4", help="Model (default: gpt-5.4)")
    parser.add_argument("--effort", default="low", choices=["low", "medium", "high"], help="Reasoning effort")
    args = parser.parse_args()

    # Token resolution order:
    # 1. --token argument
    # 2. CODEX_IMAGE_TOKEN env var
    # 3. --token-file argument
    # 4. ~/.chatgpt_auth.json cache
    # 5. Auto login flow via get_auth.py (opens browser, waits up to 5 min)
    token = args.token or os.environ.get("CODEX_IMAGE_TOKEN")
    if not token and args.token_file:
        with open(args.token_file) as f:
            token = f.read().strip()
    if not token:
        # Try cache
        if os.path.exists(AUTH_CACHE):
            try:
                with open(AUTH_CACHE) as f:
                    cached = json.load(f)
                cached_at = cached.get("_cached_at", 0)
                if time.time() - cached_at <= 8 * 3600:
                    token = cached.get("accessToken", "")
                    if token:
                        print("[auth] Using cached token.", file=sys.stderr)
            except Exception:
                pass
    if not token:
        print("[auth] No token found — starting auto login flow...", file=sys.stderr)
        try:
            token = get_token_auto()
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Generating image...", flush=True)
    result = generate_image(token, args.prompt, args.output, args.model, args.effort)

    # If oauth/auth error, invalidate cache and retry once with a fresh token
    if not result["success"] and is_oauth_error(result):
        print(f"[auth] OAuth error detected: {result['error']}", file=sys.stderr)
        print("[auth] Invalidating cached token, trying to refresh from session...", file=sys.stderr)

        # Remove stale cache
        if os.path.exists(AUTH_CACHE):
            os.remove(AUTH_CACHE)

        # First try silently refreshing from browser session (no login page)
        try:
            token = get_token_auto(no_login=True)
            print("[auth] Session refresh succeeded.", file=sys.stderr)
        except RuntimeError as e:
            if "not_logged_in" in str(e):
                # Session also expired — open login page once and wait
                print("[auth] Session expired. Opening login page for re-authentication (last attempt)...", file=sys.stderr)
                try:
                    token = get_token_auto(no_login=False)
                except Exception as e2:
                    print(json.dumps({"success": False, "error": f"Auth retry failed: {e2}. Please log in to ChatGPT and try again."}), file=sys.stderr)
                    sys.exit(1)
            else:
                print(json.dumps({"success": False, "error": f"Auth retry failed: {e}"}), file=sys.stderr)
                sys.exit(1)

        print("[auth] Retrying image generation with new token...", file=sys.stderr)
        print(f"Generating image...", flush=True)
        result = generate_image(token, args.prompt, args.output, args.model, args.effort)

        if not result["success"]:
            print(json.dumps({
                "success": False,
                "error": f"Failed after auth retry: {result['error']}. Please check your ChatGPT login and try again."
            }, indent=2), file=sys.stderr)
            sys.exit(1)

    if result["success"]:
        print(json.dumps({
            "success": True,
            "path": result["path"],
            "size": result["size"],
            "revised_prompt": result["revised_prompt"]
        }, indent=2))
    else:
        print(json.dumps({"success": False, "error": result["error"]}, indent=2), file=sys.stderr)
        sys.exit(1)
