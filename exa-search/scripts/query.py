import os
import json
import sys
import urllib.request
import urllib.error

BASE_API_URL = os.environ.get("EXA_MCP_URL", "https://mcp.exa.ai/mcp")
API_KEY = os.environ.get("EXA_API_KEY")
DEFAULT_TIMEOUT = 45
JSONRPC_VERSION = "2.0"
REQUEST_ID = 1


def build_api_url():
    tools = os.environ.get("EXA_MCP_TOOLS", "").strip()
    if tools:
        sep = "&" if "?" in BASE_API_URL else "?"
        return f"{BASE_API_URL}{sep}tools={tools}"
    return BASE_API_URL


def build_headers(api_key):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Minis/1.0",
    }
    if api_key:
        headers["x-api-key"] = api_key
        headers["X-Exa-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def decode_response_body(response, raw_bytes):
    charset = None
    try:
        charset = response.headers.get_content_charset()
    except Exception:
        charset = None
    return raw_bytes.decode(charset or "utf-8", errors="replace")


def parse_sse_message(text):
    chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    last_payload = None
    for chunk in chunks:
        lines = chunk.splitlines()
        data_lines = []
        event_type = "message"
        event_id = None
        retry = None
        for line in lines:
            if not line or line.startswith(":"):
                continue
            if ":" in line:
                field, value = line.split(":", 1)
                if value.startswith(" "):
                    value = value[1:]
            else:
                field, value = line, ""
            if field == "event":
                event_type = value
            elif field == "data":
                data_lines.append(value)
            elif field == "id":
                event_id = value
            elif field == "retry":
                retry = value
        payload = "\n".join(data_lines).strip()
        if not payload:
            continue
        try:
            last_payload = json.loads(payload)
        except json.JSONDecodeError:
            last_payload = {
                "event": event_type,
                "id": event_id,
                "retry": retry,
                "data": payload,
                "raw": chunk,
            }
    if last_payload is None:
        raise json.JSONDecodeError("Empty SSE payload", text, 0)
    return last_payload


def parse_response(response, text):
    content_type = response.headers.get("Content-Type", "").lower()
    stripped = text.lstrip()
    if "text/event-stream" in content_type or stripped.startswith("event:") or stripped.startswith("data:"):
        return parse_sse_message(text)
    return json.loads(text)


def make_error_result(message, code=-1, data=None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": REQUEST_ID, "error": error}


def make_request(method, params=None, timeout=DEFAULT_TIMEOUT):
    payload = {
        "jsonrpc": JSONRPC_VERSION,
        "id": REQUEST_ID,
        "method": method,
        "params": params or {},
    }
    req = urllib.request.Request(
        build_api_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers=build_headers(API_KEY),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            text = decode_response_body(response, raw)
            return parse_response(response, text)
    except urllib.error.HTTPError as e:
        error_body = None
        try:
            raw = e.read()
            if raw:
                error_body = raw.decode("utf-8", errors="replace")
        except Exception:
            error_body = None
        return make_error_result(str(e), code=getattr(e, "code", -1), data=error_body)
    except urllib.error.URLError as e:
        return make_error_result(f"Network error: {e.reason}")
    except json.JSONDecodeError as e:
        return make_error_result(f"Invalid response: {e.msg}")
    except Exception as e:
        return make_error_result(str(e))


def print_usage():
    print("Usage:")
    print("  python3 query.py list_tools")
    print("  python3 query.py call_tool <tool_name> [json_params]")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list_tools":
        result = make_request("tools/list")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if cmd == "call_tool":
        if len(sys.argv) < 3:
            print("Error: tool_name required for call_tool")
            print_usage()
            sys.exit(1)
        tool_name = sys.argv[2]
        params_str = sys.argv[3] if len(sys.argv) > 3 else "{}"
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON params: {params_str}")
            sys.exit(1)
        result = make_request("tools/call", {"name": tool_name, "arguments": params})
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Unknown command: {cmd}")
    print_usage()
    sys.exit(1)


if __name__ == "__main__":
    main()
