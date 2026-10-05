#!/usr/bin/env python3
"""Sign a Shortcuts draft with a user-chosen backend.

Backends
  mac       SSH into the user's own Mac and run Apple's `shortcuts sign` (no third party).
  hubsign   Upload the draft to the third-party HubSign service (free, but content leaves the device).

The backend must be chosen once (see --setup-*); until then signing exits with code 10.

Usage
  sign_shortcut.py --show-config
  sign_shortcut.py --setup-mac user@host [--port 22] [--password-env VAR] [--key PATH]
  sign_shortcut.py --setup-hubsign --i-understand-upload
  sign_shortcut.py DRAFT.xml --name "Name" [--mode anyone|people-who-know-me] [--backend mac|hubsign]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("SHORTCUTS_SIGN_CONFIG", Path.home() / ".config/shortcuts-playground/sign.json"))
DEFAULT_OUTPUT_DIR = "/var/minis/attachments/shortcut"
HERE = Path(__file__).resolve().parent
SAFE_NAME_RE = re.compile(r"[\\/:*?\"<>|]+")
EXIT_NOT_CONFIGURED = 10


def out(obj: dict, code: int = 0) -> int:
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    return code


def load_config() -> dict:
    cfg: dict = {}
    if CONFIG_PATH.is_file():
        try:
            cfg = json.loads(CONFIG_PATH.read_text("utf-8"))
        except json.JSONDecodeError:
            cfg = {}
    if os.environ.get("SHORTCUTS_SIGN_BACKEND"):
        cfg["backend"] = os.environ["SHORTCUTS_SIGN_BACKEND"]
    if os.environ.get("SHORTCUTS_SIGN_MAC_HOST"):
        cfg.setdefault("mac", {})["host"] = os.environ["SHORTCUTS_SIGN_MAC_HOST"]
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")
    CONFIG_PATH.chmod(0o600)


def safe_name(name: str) -> str:
    return SAFE_NAME_RE.sub("-", name).strip().strip(".") or "Shortcut"


def ssh_base(mac: dict) -> tuple[list[str], dict]:
    """Return (ssh argv prefix, env). The password is read from an env var, never stored."""
    env = os.environ.copy()
    opts = ["-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10", "-p", str(mac.get("port", 22))]
    if mac.get("key"):
        opts += ["-i", mac["key"], "-o", "BatchMode=yes"]
        return ["ssh", *opts], env
    pw_var = mac.get("password_env")
    if pw_var:
        if not env.get(pw_var):
            raise RuntimeError(f"environment variable {pw_var} is not set")
        env["SSHPASS"] = env[pw_var]
        return ["sshpass", "-e", "ssh", *opts], env
    return ["ssh", *opts, "-o", "BatchMode=yes"], env


def scp_base(mac: dict) -> tuple[list[str], dict]:
    argv, env = ssh_base(mac)
    argv = [("scp" if a == "ssh" else a) for a in argv]
    # scp uses -P for the port
    for i, a in enumerate(argv):
        if a == "-p":
            argv[i] = "-P"
    return argv, env


def setup_mac(args: argparse.Namespace) -> int:
    if shutil.which("ssh") is None:
        return out({"ok": False, "error": "ssh not found"}, 2)
    mac = {"host": args.setup_mac, "port": args.port}
    if args.key:
        mac["key"] = args.key
    if args.password_env:
        if shutil.which("sshpass") is None:
            return out({"ok": False, "error": "sshpass not found (apk add sshpass), or use --key"}, 2)
        mac["password_env"] = args.password_env
    try:
        argv, env = ssh_base(mac)
    except RuntimeError as exc:
        return out({"ok": False, "error": str(exc)}, 2)
    proc = subprocess.run([*argv, mac["host"], "sw_vers -productVersion && command -v shortcuts"],
                          capture_output=True, text=True, env=env, timeout=30)
    if proc.returncode != 0 or "shortcuts" not in proc.stdout:
        return out({"ok": False, "stage": "verify_mac", "stderr": proc.stderr.strip()[-400:],
                    "hint": "Need key-based login or --password-env, and macOS 12+ with the `shortcuts` CLI."}, 3)
    save_config({"backend": "mac", "mac": mac})
    return out({"ok": True, "backend": "mac", "host": mac["host"], "macos": proc.stdout.splitlines()[0],
                "config": str(CONFIG_PATH)})


def setup_hubsign(args: argparse.Namespace) -> int:
    if not args.i_understand_upload:
        return out({"ok": False, "error": "confirmation_required",
                    "message": "HubSign is a third-party service. Your shortcut draft is uploaded to it. "
                               "Re-run with --i-understand-upload only after the user agrees."}, 4)
    save_config({"backend": "hubsign", "hubsign_ack": dt.datetime.now().isoformat(timespec="seconds")})
    return out({"ok": True, "backend": "hubsign", "config": str(CONFIG_PATH)})


def sign_mac(draft: Path, name: str, mode: str, out_dir: Path, mac: dict) -> dict:
    argv, env = ssh_base(mac)
    sargv, senv = scp_base(mac)
    host = mac["host"]
    remote_dir = subprocess.run([*argv, host, "mktemp -d /tmp/sp-sign.XXXXXX"], capture_output=True, text=True, env=env, timeout=30)
    if remote_dir.returncode != 0:
        raise RuntimeError(f"ssh failed: {remote_dir.stderr.strip()[-300:]}")
    rd = remote_dir.stdout.strip()
    try:
        up = subprocess.run([*sargv, str(draft), f"{host}:{rd}/in.shortcut"], capture_output=True, text=True, env=senv, timeout=60)
        if up.returncode != 0:
            raise RuntimeError(f"scp upload failed: {up.stderr.strip()[-300:]}")
        cmd = f"cd {shlex.quote(rd)} && shortcuts sign -m {shlex.quote(mode)} -i in.shortcut -o out.shortcut"
        sg = subprocess.run([*argv, host, cmd], capture_output=True, text=True, env=env, timeout=120)
        if sg.returncode != 0:
            raise RuntimeError(f"shortcuts sign failed: {(sg.stderr or sg.stdout).strip()[-300:]}")
        dst = out_dir / f"{name}.shortcut"
        dn = subprocess.run([*sargv, f"{host}:{rd}/out.shortcut", str(dst)], capture_output=True, text=True, env=senv, timeout=60)
        if dn.returncode != 0:
            raise RuntimeError(f"scp download failed: {dn.stderr.strip()[-300:]}")
        return {"path": dst, "backend": "mac"}
    finally:
        subprocess.run([*argv, host, f"rm -rf {shlex.quote(rd)}"], capture_output=True, text=True, env=env, timeout=30)


def sign_hubsign(draft: Path, name: str, out_dir: Path) -> dict:
    proc = subprocess.run([sys.executable, str(HERE / "sign_shortcut_via_hubsign.py"), str(draft),
                           "--name", name, "--output-dir", str(out_dir)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[-400:])
    return {"path": Path(json.loads(proc.stdout)["output_path"]), "backend": "hubsign"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input_path", nargs="?")
    p.add_argument("--name")
    p.add_argument("--mode", default="anyone", choices=["anyone", "people-who-know-me"])
    p.add_argument("--backend", choices=["mac", "hubsign"])
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--show-config", action="store_true")
    p.add_argument("--setup-mac", metavar="USER@HOST")
    p.add_argument("--port", type=int, default=22)
    p.add_argument("--key")
    p.add_argument("--password-env", help="NAME of an env var holding the SSH password (the value is never stored)")
    p.add_argument("--setup-hubsign", action="store_true")
    p.add_argument("--i-understand-upload", action="store_true")
    args = p.parse_args()

    if args.show_config:
        cfg = load_config()
        return out({"configured": bool(cfg.get("backend")), "backend": cfg.get("backend"),
                    "mac_host": cfg.get("mac", {}).get("host"), "config": str(CONFIG_PATH)})
    if args.setup_mac:
        return setup_mac(args)
    if args.setup_hubsign:
        return setup_hubsign(args)
    if not args.input_path:
        p.print_usage(sys.stderr)
        return 2

    cfg = load_config()
    backend = args.backend or cfg.get("backend")
    if not backend:
        return out({"ok": False, "error": "backend_not_configured",
                    "message": "Ask the user to choose a signing backend first.",
                    "choices": {
                        "mac": "Safer: sign on your own Mac over SSH (needs a Mac with `shortcuts`, plus SSH key or password env var). "
                               "Run: sign-shortcut --setup-mac user@host [--password-env VAR | --key PATH]",
                        "hubsign": "Free and zero setup, but the draft is uploaded to a third-party service. "
                                   "Run: sign-shortcut --setup-hubsign --i-understand-upload"}}, EXIT_NOT_CONFIGURED)
    if backend == "hubsign" and not (cfg.get("hubsign_ack") or args.backend):
        return out({"ok": False, "error": "confirmation_required", "message": "Run --setup-hubsign --i-understand-upload first."}, 4)

    draft = Path(args.input_path).expanduser().resolve()
    if not draft.is_file():
        return out({"ok": False, "error": f"input not found: {draft}"}, 2)
    name = safe_name(args.name or draft.stem)
    out_dir = Path(args.output_dir).expanduser().resolve()
    (out_dir / "drafts").mkdir(parents=True, exist_ok=True)
    arch = out_dir / "archive" / dt.datetime.now().strftime("%Y-%m-%d")
    arch.mkdir(parents=True, exist_ok=True)
    archive_path = arch / f"{name}-{dt.datetime.now().strftime('%H%M%S')}{draft.suffix or '.xml'}"
    shutil.copyfile(draft, archive_path)

    try:
        if backend == "mac":
            if not cfg.get("mac", {}).get("host"):
                return out({"ok": False, "error": "mac backend has no host; run --setup-mac"}, EXIT_NOT_CONFIGURED)
            res = sign_mac(draft, name, args.mode, out_dir, cfg["mac"])
        else:
            res = sign_hubsign(draft, name, out_dir)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return out({"ok": False, "backend": backend, "error": str(exc)}, 3)

    path: Path = res["path"]
    if not path.is_file() or path.stat().st_size == 0 or path.read_bytes()[:4] != b"AEA1":
        return out({"ok": False, "backend": backend, "error": "output is not a signed AEA1 shortcut", "path": str(path)}, 5)
    return out({"ok": True, "backend": backend, "mode": args.mode if backend == "mac" else "anyone",
                "archive_path": str(archive_path), "output_path": str(path), "size": path.stat().st_size,
                "note": "On first import iOS asks the user to allow the shortcut once."})


if __name__ == "__main__":
    raise SystemExit(main())
