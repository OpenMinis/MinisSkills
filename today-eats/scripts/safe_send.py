#!/usr/bin/env python3
"""Reliable TodooCard sender — never resume mid-frame; discover block size if possible."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


def bt(args, timeout=60):
    p = subprocess.run(
        ["apple-bluetooth", *args, "--compact"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = (p.stdout or "").strip()
    if not out:
        raise RuntimeError(f"empty: {args} {p.stderr}")
    d = json.loads(out[out.find("{") :])
    if d.get("ok") is False:
        raise RuntimeError(str(d.get("error")))
    return d


def connect(dev, retries=10):
    try:
        bt(["disconnect", "--uuid", dev], timeout=15)
    except Exception:
        pass
    time.sleep(0.2)
    for i in range(retries):
        try:
            # Try direct first. Only wake with a filtered scan after a failed
            # connection; scanning on every attempt adds avoidable latency.
            if i:
                try:
                    bt(["scan", "--service", "FEF0", "--duration", "3"], timeout=20)
                except Exception:
                    pass
            r = bt(["connect", "--uuid", dev], timeout=45)
            bt(["services", "--uuid", dev], timeout=40)
            print("connected", r.get("data", {}).get("name"), flush=True)
            return
        except Exception as e:
            print(f"connect {i}: {e}", flush=True)
            time.sleep(0.8)
    raise RuntimeError("connect failed")


def try_discover_block_size(dev, svc="FEF0", ctrl="FEF1") -> int | None:
    """Best-effort: run notify concurrently, write 0x01, parse response."""
    import threading

    result = {}

    def notifier():
        try:
            r = bt(
                [
                    "notify",
                    "--uuid",
                    dev,
                    "--service",
                    svc,
                    "--characteristic",
                    ctrl,
                    "--duration",
                    "8",
                ],
                timeout=40,
            )
            result["notify"] = r
        except Exception as e:
            result["err"] = str(e)

    t = threading.Thread(target=notifier, daemon=True)
    t.start()
    time.sleep(2.0)
    try:
        bt(
            ["write", "--uuid", dev, "--service", svc, "--characteristic", ctrl, "--value", "01"],
            timeout=20,
        )
        # also try FEF2 notify path by dummy - keep simple
    except Exception as e:
        print("write01 during discover:", e, flush=True)
    t.join(timeout=15)
    print("notify result:", json.dumps(result, ensure_ascii=False)[:800], flush=True)
    r = result.get("notify") or {}
    data = r.get("data") or {}
    samples = data.get("samples") or data.get("events") or []
    for s in samples:
        hx = s.get("value_hex") or s.get("hex") or s.get("value") or ""
        if isinstance(hx, str):
            hx = hx.replace(" ", "")
            try:
                b = bytes.fromhex(hx)
            except Exception:
                continue
            print("sample", b.hex(), flush=True)
            # [01][size][status]  e.g. 01f400 → size=0xF4=244, payload=240
            if len(b) >= 3 and b[0] == 1 and b[2] == 0:
                return max(1, b[1] - 4)
    return None


def send_full(
    dev: str,
    payload: bytes,
    *,
    compressed: bool = True,
    block_payload: int | None = None,
    pace: float = 0.008,
    wait_refresh: float = 40.0,
    max_att_payload: int = 240,
):
    """Send entire payload in one session. On any failure: abort (no resume)."""
    # Connect once before the optional block-size probe. The config normally
    # contains the verified 240-byte value, so this is the only connection cycle
    # used for regular pushes.
    connect(dev)
    # If the caller already has a verified block size from config/probe, skip the
    # notify discovery round-trip. That round-trip currently costs ~8–10s because
    # apple-bluetooth notify is a separate CLI session.
    discovered = None
    did_discovery = block_payload is None
    if did_discovery:
        discovered = try_discover_block_size(dev)
        block_payload = discovered or 240
    block_payload = min(block_payload, max_att_payload)
    print(
        f"block_payload={block_payload} discovered={discovered} compressed={compressed} bytes={len(payload)}",
        flush=True,
    )

    SVC, CTRL, DATA = "FEF0", "FEF1", "FEF2"

    def w(char, data: bytes):
        return bt(
            [
                "write",
                "--uuid",
                dev,
                "--service",
                SVC,
                "--characteristic",
                char,
                "--value",
                data.hex(),
            ],
            timeout=30,
        )

    def u32(n: int) -> bytes:
        return int(n).to_bytes(4, "little")

    # The discovery session is only needed when block size is unknown. If it was
    # skipped, keep the existing connection and avoid a second connect cycle.
    if did_discovery:
        connect(dev)

    print("HS01", w(CTRL, bytes([1])), flush=True)
    time.sleep(0.4)
    flags = 0x01 if compressed else 0x03
    pkt = bytes([2]) + u32(len(payload)) + bytes([flags])
    print("HS02", w(CTRL, pkt), flush=True)
    time.sleep(0.4)
    print("HS03", w(CTRL, bytes([3])), flush=True)
    time.sleep(0.5)

    total = (len(payload) + block_payload - 1) // block_payload
    t0 = time.time()
    last_pct = -1
    for idx in range(total):
        chunk = payload[idx * block_payload : (idx + 1) * block_payload]
        packet = u32(idx) + chunk
        try:
            w(DATA, packet)
        except Exception as e:
            # DO NOT RESUME — corruption risk (horizontal stripes)
            print(f"FATAL at block {idx}/{total}: {e}", flush=True)
            print("Aborting without resume. Re-run full send.", flush=True)
            try:
                bt(["disconnect", "--uuid", dev])
            except Exception:
                pass
            raise SystemExit(2)
        pct = int((idx + 1) * 100 / total)
        if pct != last_pct and (pct % 5 == 0 or pct == 100):
            last_pct = pct
            print(f"Progress {pct}% ({idx+1}/{total}) {time.time()-t0:.1f}s", flush=True)
        if pace:
            time.sleep(pace)

    print("stream complete, wait refresh", wait_refresh, "s", flush=True)
    if wait_refresh > 0:
        time.sleep(wait_refresh)
    try:
        bt(["disconnect", "--uuid", dev])
    except Exception:
        pass
    elapsed = time.time() - t0
    data_elapsed = elapsed - wait_refresh
    print(f"DONE total={elapsed:.1f}s data={data_elapsed:.1f}s blocks={total} effective={len(payload)/max(data_elapsed, 0.001)/1024:.2f} KiB/s", flush=True)


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--device-id", required=True)
    ap.add_argument("--payload", required=True)
    ap.add_argument("--standard", action="store_true", help="send raw .bin with flags=0x03")
    ap.add_argument("--block-size", type=int, default=0)
    ap.add_argument("--pace", type=float, default=0.008)
    ap.add_argument("--wait-refresh", type=float, default=40.0)
    args = ap.parse_args()
    payload = Path(args.payload).read_bytes()
    send_full(
        args.device_id,
        payload,
        compressed=not args.standard,
        block_payload=args.block_size or None,
        pace=args.pace,
        wait_refresh=args.wait_refresh,
    )


if __name__ == "__main__":
    main()
