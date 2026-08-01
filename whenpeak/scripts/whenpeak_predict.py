#!/usr/bin/env python3
"""
WhenPeak public API client — stdlib only, no installs.

Single day:
    python whenpeak_predict.py --wake 07:00 --sleep 23:00 --quality good
    python whenpeak_predict.py --wake 07:00 --sleep 23:00 --quality good --exercise morning

Multi-day (7-30):
    python whenpeak_predict.py --wake 07:00 --sleep 23:00 --quality good --days 7

Fragmented sleep:
    python whenpeak_predict.py --wake 07:00 --sleep 22:00 --quality poor \
        --latency 60 --waso 60

Prints the API's JSON response to stdout. Both endpoints are public (no key).
Use --dry-run to print the request that would be sent without any network call.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

API_URL = "https://api.whenpeak.com"


def build_payload(args: argparse.Namespace) -> dict:
    payload = {
        "wake_time": args.wake,
        "sleep_time": args.sleep,
        "sleep_quality": args.quality,
    }
    if args.exercise:
        payload["exercise_yesterday"] = True
        payload["exercise_timing"] = args.exercise
    if args.latency is not None:
        payload["sleep_latency_minutes"] = args.latency
    if args.waso is not None:
        payload["waso_minutes"] = args.waso
    return payload


def call_api(path: str, payload: dict, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(
        API_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "whenpeak-skill-minis/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description="WhenPeak public prediction client")
    p.add_argument("--wake", required=True, help='Wake time "HH:MM", e.g. 07:00')
    p.add_argument("--sleep", required=True, help='Bed time "HH:MM", e.g. 23:00')
    p.add_argument("--quality", default="fair", choices=["good", "fair", "poor"])
    p.add_argument("--exercise", choices=["morning", "afternoon", "evening"],
                   help="If the user exercised yesterday, when")
    p.add_argument("--latency", type=float, default=None,
                   help="Minutes to fall asleep (fragmented sleep)")
    p.add_argument("--waso", type=float, default=None,
                   help="Minutes awake during the night, summed")
    p.add_argument("--days", type=int, default=None,
                   help="Multi-day projection, 7-30 days (omit for single day)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the request instead of calling the API")
    args = p.parse_args()

    payload = build_payload(args)
    if args.days is not None:
        days = max(7, min(30, args.days))
        path = f"/api/v1/predict/week?days={days}"
    else:
        path = "/api/v1/predict"

    if args.dry_run:
        print(json.dumps({"url": API_URL + path, "method": "POST",
                          "body": payload}, indent=2))
        return 0

    try:
        result = call_api(path, payload)
    except urllib.error.HTTPError as e:
        print(json.dumps({"error": f"HTTP {e.code}",
                          "detail": e.read().decode("utf-8", "replace")}),
              file=sys.stderr)
        return 1
    except Exception as e:  # network down, DNS, timeout
        print(json.dumps({"error": "WhenPeak unreachable", "detail": str(e)}),
              file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
