import os
import json
import sys
import urllib.request
import urllib.error

API_URL = (
    "https://mcp.exa.ai/mcp?"
    "tools=web_search_exa,web_search_advanced_exa,get_code_context_exa,"
    "crawling_exa,company_research_exa,people_search_exa,"
    "deep_researcher_start,deep_researcher_check"
)
API_KEY = os.environ.get("EXA_API_KEY")
DEFAULT_TIMEOUT = 30
JSONRPC_VERSION = "2.0"
REQUEST_ID = 1


def build_headers(api_key):
    return {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Minis/1.0",
        "X-Exa-API-Key": api_key,
        "Authorization": f"Bearer {api_key}",
    }


def decode_response_body(response, raw_bytes):
    charset = None
    try:
        charset = response.headers.get_content_charset()
    except Exception:
        charset = None
    return raw_bytes.decode(charset or "utf-8", errors="replace")


def parse_sse_message(text):
    lines = text.splitlines()
    event_type = "message"
    data_lines = []
    event_id = None
    retry = None

    for line in lines:
        if not line:
            continue
        if line.startswith(":"):
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

    try:
        parsed_payload = json.loads(payload)
        return parsed_payload
    except json.JSONDecodeError:
        return {
            "event": event_type,
            "id": event_id,
            "retry": retry,
            "data": payload,
            "raw": text,
        }


def parse_response(response, text):
    content_type = response.headers.get("Content-Type", "").lower()

    if "text/event-stream" in content_type or text.lstrip().startswith("event:") or text.lstrip().startswith(""):
        return parse_sse_message(text)

    return json.loads(text)


def make_error_result(message, code=-1, data=None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": REQUEST_ID, "error": error}


def make_request(method, params=None, timeout=DEFAULT_TIMEOUT):
    if not API_KEY:
        return make_error_result("EXA_API_KEY is not set.")

    payload = {
        "jsonrpc": JSONRPC_VERSION,
        "id": REQUEST_ID,
        "method": method,
        "params": params or {},
    }

    req = urllib.request.Request(
        API_URL,
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
        return make_error_result(f"Invalid JSON response: {e.msg}")

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

        result = make_request("tools/call", {
            "name": tool_name,
            "arguments": params
        })
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print(f"Unknown command: {cmd}")
    print_usage()
    sys.exit(1)


if __name__ == "__main__":
    main()
