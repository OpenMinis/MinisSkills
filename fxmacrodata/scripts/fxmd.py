#!/usr/bin/env python3
"""Small FXMacroData REST client for the fxmacrodata skill.

Standard library only. Prints one JSON object to stdout:
  {"ok": true, "data": ..., "notices": [...]}   on success (exit 0)
  {"ok": false, "error": "..."}                 on failure (exit 1)

The API key is optional and read from FXMACRODATA_API_KEY. It is sent in the
X-API-Key header, never in a URL, and it never appears in output or errors.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

BASE_URL = "https://api.fxmacrodata.com/v1"
TIMEOUT_SECONDS = 30
MAX_PAGE_SIZE = 100
MAX_PAGES = 50
USER_AGENT = "MinisSkills-fxmacrodata/1.0"

CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
SLUG_RE = re.compile(r"^[a-z0-9_]{1,64}$")
KEY_RE = re.compile(r"^[!-~]{1,256}$")


class FxmdError(Exception):
    """An error whose message is safe to show to the user."""


class Secret:
    """Holds the API key without exposing it through repr() or str()."""

    def __init__(self, value):
        self._value = value

    def reveal(self):
        return self._value

    def __repr__(self):
        return "Secret('***')"

    __str__ = __repr__


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so the key header is never replayed to another URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise FxmdError(f"refused HTTP {code} redirect from the API")


def load_key(environ=None):
    raw = (environ if environ is not None else os.environ).get("FXMACRODATA_API_KEY", "")
    key = raw.strip()
    if not key:
        return None
    if not KEY_RE.match(key):
        raise FxmdError("FXMACRODATA_API_KEY contains spaces or control characters")
    return Secret(key)


def check_base_url(base_url):
    parts = urllib.parse.urlsplit(base_url)
    if parts.scheme != "https" or not parts.hostname:
        raise FxmdError("base URL must be https:// with a host")
    return base_url.rstrip("/")


def currency_code(value):
    code = value.strip()
    if not CURRENCY_RE.match(code):
        raise FxmdError(f"currency must be a 3-letter code, got {value!r}")
    return code.lower()


def slug(value, label="indicator"):
    text = value.strip().lower()
    if not SLUG_RE.match(text):
        raise FxmdError(f"{label} must be a lowercase slug such as policy_rate, got {value!r}")
    return text


def iso_date(value, label):
    text = value.strip()
    try:
        if len(text) != 10:
            raise ValueError
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise FxmdError(f"{label} must be a real date in YYYY-MM-DD form, got {value!r}") from None


def date_range(start, end):
    start_iso = iso_date(start, "start") if start else None
    end_iso = iso_date(end, "end") if end else None
    if start_iso and end_iso and start_iso > end_iso:
        raise FxmdError("start must be on or before end")
    return start_iso, end_iso


def page_limit(value):
    if value < 1 or value > MAX_PAGE_SIZE:
        raise FxmdError(f"limit must be between 1 and {MAX_PAGE_SIZE}")
    return value


class Client:
    def __init__(self, key=None, base_url=BASE_URL, opener=None):
        self.key = key
        self.base_url = check_base_url(base_url)
        self.opener = opener or urllib.request.build_opener(_NoRedirect)

    def _redact(self, text):
        if self.key is not None:
            text = text.replace(self.key.reveal(), "***")
        return text

    def get(self, path, params=None):
        query = {k: v for k, v in (params or {}).items() if v is not None}
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if self.key is not None:
            headers["X-API-Key"] = self.key.reveal()
        request = urllib.request.Request(url, headers=headers)
        try:
            with self.opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        except FxmdError:
            raise
        except Exception as exc:
            raise FxmdError(f"request failed ({type(exc).__name__})") from None
        return self._decode(status, raw)

    def _decode(self, status, raw):
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise FxmdError(f"HTTP {status}: response was not JSON") from None
        if not isinstance(body, dict):
            raise FxmdError(f"HTTP {status}: unexpected response shape")
        if status != 200 or "error" in body or "detail" in body:
            raise FxmdError(self._redact(f"HTTP {status}: {_error_text(body)}"))
        return body


def _error_text(body):
    for field in ("detail", "message", "error"):
        value = body.get(field)
        if isinstance(value, str) and value:
            return value[:300]
        if isinstance(value, dict):
            text = value.get("message") or value.get("code")
            if isinstance(text, str) and text:
                return text[:300]
    return "the API returned an error"


def notices(body):
    """Free-tier delay and window messages, so results are not read as current."""
    found = []
    for field in ("freemium_delay", "freemium_window"):
        item = body.get(field)
        if isinstance(item, dict) and item.get("applied") and isinstance(item.get("message"), str):
            found.append(item["message"])
    return found


def rows(body):
    data = body.get("data")
    if not isinstance(data, list):
        raise FxmdError("unexpected response shape: data is not a list")
    return data


def next_offset(body, offset):
    """Return the next offset, or None when there are no more pages."""
    if "pagination" not in body:
        return None
    page = body["pagination"]
    if not isinstance(page, dict) or not isinstance(page.get("has_more"), bool):
        raise FxmdError("unexpected response shape: malformed pagination")
    if not page["has_more"]:
        return None
    following = page.get("next_offset")
    if isinstance(following, bool) or not isinstance(following, int) or following <= offset:
        raise FxmdError("unexpected response shape: next_offset does not advance")
    return following


def catalogue(client, args):
    """One compact row per indicator; the raw catalogue is over 100 KB."""
    body = client.get(f"/data_catalogue/{currency_code(args.currency)}")
    entries = []
    for indicator, info in body.items():
        if not isinstance(info, dict) or not isinstance(info.get("name"), str):
            raise FxmdError("unexpected response shape: catalogue entry is not an object")
        coverage = info.get("coverage") if isinstance(info.get("coverage"), dict) else {}
        entries.append({
            "indicator": indicator,
            "name": info["name"],
            "unit": info.get("unit"),
            "frequency": info.get("frequency"),
            "latest_release_date": coverage.get("latest_release_date"),
            "requires_api_key": coverage.get("requires_api_key"),
        })
    return {"ok": True, "data": entries, "notices": []}


def paged(client, path, params, args):
    """Read one page, or every page when --all is set."""
    limit = page_limit(args.limit)
    collected, notes, offset = [], [], 0
    for _ in range(MAX_PAGES):
        body = client.get(path, dict(params, limit=limit, offset=offset))
        collected.extend(rows(body))
        notes = notices(body) or notes
        following = next_offset(body, offset)
        if following is None or not args.all:
            return {"ok": True, "data": collected, "notices": notes, "has_more": following is not None}
        offset = following
    raise FxmdError(f"stopped after {MAX_PAGES} pages; narrow the date range")


def history(client, args):
    path = f"/announcements/{currency_code(args.currency)}/{slug(args.indicator)}"
    start, end = date_range(args.start, args.end)
    return paged(client, path, {"start_date": start, "end_date": end}, args)


def calendar(client, args):
    start, end = date_range(args.start, args.end)
    indicator = slug(args.indicator) if args.indicator else None
    params = {"indicator": indicator, "start_date": start, "end_date": end}
    body = client.get(f"/calendar/{currency_code(args.currency)}", params)
    return {"ok": True, "data": rows(body), "notices": notices(body)}


def fx(client, args):
    path = f"/forex/{currency_code(args.base)}/{currency_code(args.quote)}"
    start, end = date_range(args.start, args.end)
    return paged(client, path, {"start_date": start, "end_date": end}, args)


def add_paging(parser):
    parser.add_argument("--limit", type=int, default=20, help=f"rows per page, 1-{MAX_PAGE_SIZE}")
    parser.add_argument("--all", action="store_true", help="follow pagination to the end of the range")


def build_parser():
    parser = argparse.ArgumentParser(prog="fxmd.py", description="Query the FXMacroData REST API.")
    sub = parser.add_subparsers(dest="command", required=True)

    cat = sub.add_parser("catalogue", help="list indicators for a currency")
    cat.add_argument("currency")
    cat.set_defaults(func=catalogue)

    hist = sub.add_parser("history", help="release history for one indicator")
    hist.add_argument("currency")
    hist.add_argument("indicator")
    hist.add_argument("--start")
    hist.add_argument("--end")
    add_paging(hist)
    hist.set_defaults(func=history)

    cal = sub.add_parser("calendar", help="upcoming release calendar")
    cal.add_argument("currency")
    cal.add_argument("--indicator")
    cal.add_argument("--start")
    cal.add_argument("--end")
    cal.set_defaults(func=calendar)

    pair = sub.add_parser("fx", help="daily FX rates (needs an API key)")
    pair.add_argument("base")
    pair.add_argument("quote")
    pair.add_argument("--start")
    pair.add_argument("--end")
    add_paging(pair)
    pair.set_defaults(func=fx)
    return parser


def render(result, key):
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if key is not None:
        for form in {key.reveal(), json.dumps(key.reveal())[1:-1]}:
            text = text.replace(form, "***")
    return text + "\n"


def main(argv=None, environ=None, opener=None, out=None):
    args = build_parser().parse_args(argv)
    key = None
    try:
        key = load_key(environ)
        result = args.func(Client(key=key, opener=opener), args)
        code = 0
    except FxmdError as exc:
        result, code = {"ok": False, "error": str(exc)}, 1
    (out or sys.stdout).write(render(result, key))
    return code


if __name__ == "__main__":
    sys.exit(main())
