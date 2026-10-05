#!/usr/bin/env python3
"""Sign Apple Shortcuts files via RoutineHub HubSign using curl -F.

Usage:
  python3 sign_shortcut_via_hubsign.py /path/to/draft.xml --name "My Shortcut"
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SERVICE_URL = "https://hubsign.routinehub.services/sign"
DEFAULT_OUTPUT_DIR = "/var/minis/attachments/shortcut"
SAFE_NAME_RE = re.compile(r"[\\/:*?\"<>|]+")


def safe_name(name: str) -> str:
    cleaned = SAFE_NAME_RE.sub("-", name).strip().strip(".")
    return cleaned or "Shortcut"


def detect_content_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".xml": "application/xml",
        ".plist": "application/x-plist",
        ".shortcut": "application/octet-stream",
    }.get(ext, "application/octet-stream")


def extract_filename(header_text: str, fallback_name: str) -> str:
    match = re.search(r"(?im)^content-disposition:\s*attachment;\s*filename=\"?([^\";\r\n]+)\"?", header_text)
    if not match:
        return fallback_name
    name = match.group(1).strip()
    return name or fallback_name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path")
    parser.add_argument("--name", help="Final shortcut display/file name")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--service-url", default=SERVICE_URL)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    input_path = Path(args.input_path).expanduser().resolve()
    if not input_path.is_file():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 2
    if shutil.which("curl") is None:
        print("curl not found on PATH", file=sys.stderr)
        return 127

    payload = input_path.read_bytes()
    shortcut_name = safe_name(args.name or input_path.stem)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "drafts").mkdir(parents=True, exist_ok=True)
    archive_dir = output_dir / "archive" / dt.datetime.now().strftime("%Y-%m-%d")
    archive_dir.mkdir(parents=True, exist_ok=True)

    archive_ext = input_path.suffix or ".xml"
    archive_path = archive_dir / f"{shortcut_name}-{dt.datetime.now().strftime('%H%M%S')}{archive_ext}"
    archive_path.write_bytes(payload)

    with tempfile.TemporaryDirectory(prefix="hubsign_") as tmpdir:
        tmp = Path(tmpdir)
        headers_path = tmp / "headers.txt"
        body_path = tmp / "body.bin"
        file_field = f"shortcut=@{input_path};type={detect_content_type(input_path)}"
        cmd = [
            "curl",
            "-sS",
            "--max-time",
            str(args.timeout),
            "-D",
            str(headers_path),
            "-o",
            str(body_path),
            "-F",
            f"shortcutName={shortcut_name}",
            "-F",
            file_field,
            args.service_url,
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "curl upload failed").strip()
            print(f"HubSign curl upload failed: {detail}", file=sys.stderr)
            return 3

        response_bytes = body_path.read_bytes() if body_path.exists() else b""
        header_text = headers_path.read_text("utf-8", errors="replace") if headers_path.exists() else ""

    if not response_bytes:
        print("HubSign returned an empty response", file=sys.stderr)
        return 4
    if response_bytes[:4] != b"AEA1":
        snippet = response_bytes[:200].decode("utf-8", "replace")
        print(f"HubSign did not return an AEA1 shortcut payload: {snippet}", file=sys.stderr)
        return 5

    output_name = extract_filename(header_text, f"{shortcut_name}.shortcut")
    output_name = safe_name(Path(output_name).stem) + ".shortcut"
    output_path = output_dir / output_name
    output_path.write_bytes(response_bytes)

    result = {
        "ok": True,
        "service_url": args.service_url,
        "input_path": str(input_path),
        "archive_path": str(archive_path),
        "output_path": str(output_path),
        "size": output_path.stat().st_size,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
