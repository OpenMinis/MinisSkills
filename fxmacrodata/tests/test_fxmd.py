"""Offline tests for scripts/fxmd.py. Run: python3 -m unittest discover -s fxmacrodata/tests"""

import io
import json
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fxmd  # noqa: E402

KEY = "test-key-1234567890abcdef"


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """Returns queued (status, body) pairs and records each request."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        status, body = reply
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "error", {}, io.BytesIO(raw))
        return FakeResponse(status, raw)

    def query(self, index=0):
        return urllib.parse.parse_qs(urllib.parse.urlsplit(self.requests[index].full_url).query)


def run(argv, *replies, env=None):
    opener = FakeOpener(*replies)
    out = io.StringIO()
    code = fxmd.main(argv, environ=env or {}, opener=opener, out=out)
    return code, json.loads(out.getvalue()), out.getvalue(), opener


def page(rows, has_more=False, next_offset=None, **extra):
    pagination = {"has_more": has_more}
    if next_offset is not None:
        pagination["next_offset"] = next_offset
    return dict({"data": rows, "pagination": pagination}, **extra)


FREE = {
    "freemium_delay": {"applied": True, "message": "Free access is delayed by 15 minutes."},
    "freemium_window": {"applied": True, "message": "Anonymous access returns the most recent 90 days."},
}


class HistoryTests(unittest.TestCase):
    def test_keyless_request_has_no_key_and_surfaces_notices(self):
        code, result, _, opener = run(["history", "USD", "inflation"], (200, page([{"val": 3.4}], **FREE)))
        self.assertEqual(code, 0)
        self.assertEqual(result["data"], [{"val": 3.4}])
        self.assertEqual(len(result["notices"]), 2)
        self.assertIsNone(opener.requests[0].get_header("X-api-key"))
        self.assertTrue(opener.requests[0].full_url.startswith("https://api.fxmacrodata.com/v1/announcements/usd/inflation?"))

    def test_key_goes_in_header_never_in_url_or_output(self):
        echo = page([{"note": KEY}])
        code, _, text, opener = run(["history", "eur", "policy_rate"], (200, echo), env={"FXMACRODATA_API_KEY": f"  {KEY} "})
        self.assertEqual(code, 0)
        self.assertEqual(opener.requests[0].get_header("X-api-key"), KEY)
        self.assertNotIn(KEY, opener.requests[0].full_url)
        self.assertNotIn(KEY, text)

    def test_all_follows_pagination(self):
        code, result, _, opener = run(
            ["history", "usd", "inflation", "--all", "--limit", "100"],
            (200, page([1], True, 100)),
            (200, page([2])),
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["data"], [1, 2])
        self.assertFalse(result["has_more"])
        self.assertEqual(opener.query(1)["offset"], ["100"])
        self.assertEqual(opener.query(1)["limit"], ["100"])

    def test_without_all_reports_more_pages(self):
        _, result, _, opener = run(["history", "usd", "inflation"], (200, page([1], True, 20)))
        self.assertTrue(result["has_more"])
        self.assertEqual(len(opener.requests), 1)

    def test_malformed_pagination_is_an_error(self):
        for bad in ([], {"has_more": "yes"}, {}, None):
            code, result, _, _ = run(["history", "usd", "inflation"], (200, {"data": [], "pagination": bad}))
            self.assertEqual(code, 1, bad)
            self.assertIn("pagination", result["error"])

    def test_next_offset_must_advance(self):
        for bad in (0, -5, True, "20", None):
            body = {"data": [1], "pagination": {"has_more": True, "next_offset": bad}}
            code, result, _, _ = run(["history", "usd", "inflation", "--all"], (200, body))
            self.assertEqual(code, 1, bad)
            self.assertIn("next_offset", result["error"])


class ValidationTests(unittest.TestCase):
    def assert_rejected(self, argv, fragment):
        code, result, _, opener = run(argv)
        self.assertEqual(code, 1)
        self.assertIn(fragment, result["error"])
        self.assertEqual(opener.requests, [])

    def test_inputs_are_checked_before_any_request(self):
        self.assert_rejected(["history", "usdx", "inflation"], "3-letter")
        self.assert_rejected(["history", "us1", "inflation"], "3-letter")
        self.assert_rejected(["history", "usd", "cpi index"], "slug")
        self.assert_rejected(["history", "usd", "inflation", "--start", "2026-02-30"], "real date")
        self.assert_rejected(["history", "usd", "inflation", "--start", "2026-1-5"], "real date")
        self.assert_rejected(["history", "usd", "inflation", "--start", "2026-05-01", "--end", "2026-04-01"], "on or before")
        self.assert_rejected(["history", "usd", "inflation", "--limit", "101"], "between 1 and 100")
        self.assert_rejected(["history", "usd", "inflation", "--limit", "0"], "between 1 and 100")
        self.assert_rejected(["calendar", "usd", "--indicator", "../x"], "slug")

    def test_trimmed_slug_and_currency(self):
        code, _, _, opener = run(["history", " GBP ", " Policy_Rate "], (200, page([])))
        self.assertEqual(code, 0)
        self.assertIn("/announcements/gbp/policy_rate?", opener.requests[0].full_url)

    def test_bad_key_is_refused_without_echo(self):
        code, result, text, opener = run(["catalogue", "usd"], env={"FXMACRODATA_API_KEY": "abc def"})
        self.assertEqual(code, 1)
        self.assertNotIn("abc def", text)
        self.assertEqual(opener.requests, [])

    def test_base_url_must_be_https_with_host(self):
        for url in ("http://api.fxmacrodata.com/v1", "https://", "ftp://x"):
            with self.assertRaises(fxmd.FxmdError):
                fxmd.Client(base_url=url)

    def test_secret_repr_hides_value(self):
        secret = fxmd.Secret(KEY)
        self.assertNotIn(KEY, repr(secret))
        self.assertNotIn(KEY, str(secret))


class ErrorTests(unittest.TestCase):
    def test_200_with_error_body(self):
        code, result, _, _ = run(["history", "usd", "inflation"], (200, {"error": "api_key_required", "detail": "Needs a key."}))
        self.assertEqual(code, 1)
        self.assertIn("Needs a key.", result["error"])

    def test_http_error_message_is_redacted(self):
        body = {"detail": f"bad key {KEY}"}
        code, result, text, _ = run(["fx", "eur", "usd"], (401, body), env={"FXMACRODATA_API_KEY": KEY})
        self.assertEqual(code, 1)
        self.assertIn("HTTP 401", result["error"])
        self.assertNotIn(KEY, text)

    def test_non_json_and_wrong_shapes(self):
        cases = [
            (200, b"<html>"),
            (200, [1, 2]),
            (200, {"data": {"not": "a list"}}),
        ]
        for reply in cases:
            code, result, _, _ = run(["history", "usd", "inflation"], reply)
            self.assertEqual(code, 1, reply)
            self.assertTrue(result["error"])

    def test_transport_errors_report_type_only(self):
        err = urllib.error.URLError(f"boom {KEY}")
        code, result, text, _ = run(["catalogue", "usd"], err, env={"FXMACRODATA_API_KEY": KEY})
        self.assertEqual(code, 1)
        self.assertEqual(result["error"], "request failed (URLError)")
        self.assertNotIn(KEY, text)

    def test_redirects_are_refused(self):
        handler = fxmd._NoRedirect()
        request = urllib.request.Request("https://api.fxmacrodata.com/v1/calendar/usd", headers={"X-API-Key": KEY})
        with self.assertRaises(fxmd.FxmdError) as ctx:
            handler.redirect_request(request, None, 302, "Found", {}, "https://elsewhere.example/")
        self.assertNotIn(KEY, str(ctx.exception))


class OtherCommandTests(unittest.TestCase):
    def test_calendar_passes_filters(self):
        code, result, _, opener = run(
            ["calendar", "usd", "--indicator", "inflation", "--start", "2026-10-01", "--end", "2026-10-31"],
            (200, {"data": [{"release": "inflation"}]}),
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["data"], [{"release": "inflation"}])
        query = opener.query()
        self.assertEqual(query["indicator"], ["inflation"])
        self.assertEqual(query["start_date"], ["2026-10-01"])

    def test_catalogue_is_compact(self):
        body = {"inflation": {"name": "Inflation (CPI)", "unit": "%YoY", "frequency": "Monthly",
                              "coverage": {"requires_api_key": False, "latest_release_date": "2026-09-11"},
                              "series_variants": [{"big": "x"}]}}
        code, result, _, _ = run(["catalogue", "usd"], (200, body))
        self.assertEqual(code, 0)
        self.assertEqual(result["data"], [{
            "indicator": "inflation", "name": "Inflation (CPI)", "unit": "%YoY", "frequency": "Monthly",
            "latest_release_date": "2026-09-11", "requires_api_key": False,
        }])

    def test_catalogue_with_bad_entry_is_an_error(self):
        code, result, _, _ = run(["catalogue", "usd"], (200, {"inflation": "oops"}))
        self.assertEqual(code, 1)
        self.assertIn("catalogue entry", result["error"])


if __name__ == "__main__":
    unittest.main()
