#!/usr/bin/env python3
"""Pipelined TodooCard sender with stage timing.

Overlaps image conversion with BLE connect, minimizes handshake sleeps,
and streams blocks as fast as apple-bluetooth with_response allows.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from image_to_payload import convert  # noqa: E402


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


def connect(dev: str, retries: int = 8) -> float:
    t0 = time.perf_counter()
    try:
        bt(["disconnect", "--uuid", dev], timeout=15)
    except Exception:
        pass
    time.sleep(0.05)
    for i in range(retries):
        try:
            if i:
                try:
                    bt(["scan", "--service", "FEF0", "--duration", "2"], timeout=15)
                except Exception:
                    pass
            r = bt(["connect", "--uuid", dev], timeout=40)
            bt(["services", "--uuid", dev], timeout=40)
            print(f"connected {r.get('data', {}).get('name')}", flush=True)
            return time.perf_counter() - t0
        except Exception as e:
            print(f"connect {i}: {e}", flush=True)
            time.sleep(0.4)
    raise RuntimeError("connect failed")


def u32(n: int) -> bytes:
    return int(n).to_bytes(4, "little")


def send_payload(
    dev: str,
    payload: bytes,
    *,
    block: int = 240,
    wait_refresh: float = 12.0,
    hs_gap: float = 0.12,
) -> dict:
    report: dict = {}
    t_conn = connect(dev)
    report["connect_s"] = round(t_conn, 3)

    def w(char: str, data: bytes):
        return bt(
            [
                "write",
                "--uuid",
                dev,
                "--service",
                "FEF0",
                "--characteristic",
                char,
                "--value",
                data.hex(),
            ],
            timeout=30,
        )

    t1 = time.perf_counter()
    w("FEF1", bytes([1]))
    time.sleep(hs_gap)
    w("FEF1", bytes([2]) + u32(len(payload)) + bytes([0x01]))
    time.sleep(hs_gap)
    w("FEF1", bytes([3]))
    time.sleep(hs_gap)
    report["handshake_s"] = round(time.perf_counter() - t1, 3)

    total = (len(payload) + block - 1) // block
    t2 = time.perf_counter()
    last = -1
    # Pre-hex to reduce per-iter overhead slightly
    # (building hex still dominates less than process spawn)
    for idx in range(total):
        chunk = payload[idx * block : (idx + 1) * block]
        packet = u32(idx) + chunk
        try:
            w("FEF2", packet)
        except Exception as e:
            print(f"FATAL block {idx}/{total}: {e}", flush=True)
            try:
                bt(["disconnect", "--uuid", dev])
            except Exception:
                pass
            report["fatal_block"] = idx
            report["error"] = str(e)
            raise SystemExit(2)
        pct = int((idx + 1) * 100 / total)
        if pct != last and (pct % 10 == 0 or pct >= 100):
            last = pct
            el = time.perf_counter() - t2
            print(f"Progress {pct}% ({idx+1}/{total}) {el:.1f}s", flush=True)
    data_s = time.perf_counter() - t2
    report["data_s"] = round(data_s, 3)
    report["blocks"] = total
    report["per_block_ms"] = round(data_s / total * 1000, 2)
    report["throughput_kib_s"] = round(len(payload) / max(data_s, 1e-6) / 1024, 2)

    t3 = time.perf_counter()
    if wait_refresh > 0:
        print(f"refresh wait {wait_refresh}s", flush=True)
        time.sleep(wait_refresh)
    report["refresh_wait_s"] = round(time.perf_counter() - t3, 3)
    try:
        bt(["disconnect", "--uuid", dev])
    except Exception:
        pass
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--device-id", required=True)
    ap.add_argument("--orientation", default="rotate-180-then-flip-horizontal")
    ap.add_argument("--block-size", type=int, default=240)
    ap.add_argument("--wait-refresh", type=float, default=12.0)
    ap.add_argument("--prefix", default="/var/minis/workspace/todoocard_run/fast_e2e")
    ap.add_argument("--report", default="/var/minis/workspace/todoocard_run/fast_e2e_report.json")
    args = ap.parse_args()

    report: dict = {
        "input": args.input,
        "device_id": args.device_id,
        "orientation": args.orientation,
    }
    t0 = time.perf_counter()

    # Pipeline: convert || connect-prep is done inside send after convert for simplicity
    # True overlap: convert in thread while connecting
    box: dict = {}

    def do_convert():
        tc = time.perf_counter()
        info = convert(args.input, args.prefix, orientation=args.orientation, make_preview=True)
        box["info"] = info
        box["convert_s"] = time.perf_counter() - tc

    def do_connect():
        # only establish link; handshake after payload ready
        box["connect_s"] = connect(args.device_id)

    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(do_convert)
        f2 = ex.submit(do_connect)
        f1.result()
        f2.result()

    report["convert_s"] = round(box["convert_s"], 3)
    report["connect_s"] = round(box["connect_s"], 3)
    info = box["info"]
    report["qlz_bytes"] = info["qlz_bytes"]
    print(f"convert {report['convert_s']}s  connect {report['connect_s']}s  qlz={info['qlz_bytes']}", flush=True)

    # Connection already open from do_connect — but convert thread may have taken longer
    # and idle timeout is 5 min, OK. Handshake+data:
    # Re-use connection: skip reconnect in send_payload by inlining from connected state.
    payload = Path(info["qlz"]).read_bytes()

    def w(char: str, data: bytes):
        return bt(
            [
                "write",
                "--uuid",
                args.device_id,
                "--service",
                "FEF0",
                "--characteristic",
                char,
                "--value",
                data.hex(),
            ],
            timeout=30,
        )

    # If connection dropped during convert, reconnect quickly
    try:
        w("FEF1", bytes([1]))
        already = True
    except Exception:
        already = False
        report["connect_s"] = round(report["connect_s"] + connect(args.device_id), 3)

    t_hs = time.perf_counter()
    if already:
        # first HS01 already sent
        time.sleep(0.12)
    else:
        w("FEF1", bytes([1]))
        time.sleep(0.12)
    w("FEF1", bytes([2]) + u32(len(payload)) + bytes([0x01]))
    time.sleep(0.12)
    w("FEF1", bytes([3]))
    time.sleep(0.12)
    report["handshake_s"] = round(time.perf_counter() - t_hs, 3)
    print(f"handshake {report['handshake_s']}s", flush=True)

    block = args.block_size
    total = (len(payload) + block - 1) // block
    t_data = time.perf_counter()
    last = -1
    for idx in range(total):
        packet = u32(idx) + payload[idx * block : (idx + 1) * block]
        try:
            w("FEF2", packet)
        except Exception as e:
            print(f"FATAL {idx}/{total}: {e}", flush=True)
            report["error"] = str(e)
            Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2))
            raise SystemExit(2)
        pct = int((idx + 1) * 100 / total)
        if pct != last and (pct % 10 == 0 or pct == 100):
            last = pct
            print(f"Progress {pct}% ({idx+1}/{total}) {time.perf_counter()-t_data:.1f}s", flush=True)
    data_s = time.perf_counter() - t_data
    report["data_s"] = round(data_s, 3)
    report["blocks"] = total
    report["per_block_ms"] = round(data_s / total * 1000, 2)
    report["throughput_kib_s"] = round(len(payload) / max(data_s, 1e-6) / 1024, 2)
    print(
        f"data {report['data_s']}s  {report['per_block_ms']}ms/block  {report['throughput_kib_s']}KiB/s",
        flush=True,
    )

    t_r = time.perf_counter()
    if args.wait_refresh > 0:
        print(f"refresh wait {args.wait_refresh}s", flush=True)
        time.sleep(args.wait_refresh)
    report["refresh_wait_s"] = round(time.perf_counter() - t_r, 3)
    try:
        bt(["disconnect", "--uuid", args.device_id])
    except Exception:
        pass

    report["end_to_end_s"] = round(time.perf_counter() - t0, 3)
    # pipeline wall for convert||connect
    report["pipeline_setup_s"] = round(max(report["convert_s"], report["connect_s"]), 3)
    print("==== REPORT ====", flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    # preview
    prev = info.get("preview")
    if prev and Path(prev).exists():
        Path("/var/minis/attachments/fast_e2e_preview.png").write_bytes(Path(prev).read_bytes())


if __name__ == "__main__":
    main()
