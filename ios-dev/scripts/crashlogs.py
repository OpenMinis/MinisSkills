#!/usr/bin/env python3
"""crashlogs.py — Pull an app's crash reports straight over the loopback RSD channel.

No Mac, no Xcode, no Settings taps: the reports live in the device's
com.apple.crashreportcopymobile store, which iOS 17+ also exposes over RSD as
``com.apple.crashreportcopymobile.shim.remote``. session.CoreDeviceSession already
builds that RSD channel, so this script just walks the store.

Usage:
  python3 crashlogs.py                       # list the 10 newest reports
  python3 crashlogs.py --app AppConnect      # only reports whose name contains AppConnect
  python3 crashlogs.py --app AppConnect --print   # print the newest report in full
  python3 crashlogs.py --pull ./crashes      # download every matching report

Environment: IOSDEV_PAIRING_FILE (or legacy CDTK_PAIRING_FILE), same as the other scripts.
"""
import argparse
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from session import CoreDeviceSession  # noqa: E402
from pymobiledevice3.services.crash_reports import CrashReportsManager  # noqa: E402


def _fmt(name: str) -> str:
    base = name.lstrip("/")
    return base


async def _run(args) -> int:
    async with CoreDeviceSession() as s:
        async with CrashReportsManager(s.rsd) as m:
            names = [n for n in await m.ls("/", depth=1) if n.lower().endswith(".ips")]
            if args.app:
                names = [n for n in names if args.app.lower() in n.lower()]
            names.sort()
            if not names:
                print("no crash reports matched")
                return 1
            show = names[-args.limit:]
            if not args.print and not args.pull:
                print(f"== {len(names)} matching report(s), newest {len(show)}:")
                for n in show:
                    print("  -", _fmt(n))
                return 0
            if args.pull:
                os.makedirs(args.pull, exist_ok=True)
                for n in show:
                    dest = os.path.join(args.pull, os.path.basename(n))
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write((await m.get_file_contents(n)).decode("utf-8", "replace"))
                    print("saved", dest)
                return 0
            rep = await m.parse(names[-1])
            print(rep.text if hasattr(rep, "text") else rep)
            return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull crash reports over the loopback RSD channel")
    ap.add_argument("--app", help="filter by app name substring (e.g. AppConnect)")
    ap.add_argument("--limit", type=int, default=10, help="how many newest reports to act on (default 10)")
    ap.add_argument("--print", action="store_true", help="print the newest matching report")
    ap.add_argument("--pull", metavar="DIR", help="download matching reports into DIR")
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
