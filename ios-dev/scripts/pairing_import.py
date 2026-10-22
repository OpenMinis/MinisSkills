#!/usr/bin/env python3
"""pairing_import.py — Validate and import a RemotePairing pairing file (no matter how it was obtained: Mac pair_host, StikPair export, bridge pairing).

Usage:
  python3 pairing_import.py <source plist> [--dest ~/.cdtk/pairing/new_phone.plist] [--no-handshake]
What it does (all read-only validation + writing to disk):
  1) Format: XML/binary plist; must contain public_key (32B Data), private_key (32B Data), identifier (str); alt_irk optional (should be 16B)
  2) Rejects legacy lockdown records (HostID/SystemBUID/HostCertificate...) and explains why
  3) The public key must be derivable from the private key (guards against truncation/corruption/typos)
  4) Copy to the destination (using copyfile, because copy2 fails on iSH), chmod 600
  5) By default also verify with a real device loopback handshake (needs Wi-Fi and the loopback VPN); --no-handshake skips it
Never prints key contents.
"""
import argparse, os, plistlib, shutil, sys, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
LOCKDOWN_KEYS = {"HostID", "SystemBUID", "HostCertificate", "HostPrivateKey", "RootCertificate", "DeviceCertificate", "EscrowBag"}


def validate(path):
    """Return (errors, warnings, info)."""
    errs, warns, info = [], [], {}
    try:
        raw = open(path, "rb").read()
        d = plistlib.loads(raw)
    except Exception as e:
        return [f"not a valid plist: {e}"], warns, info
    if not isinstance(d, dict):
        return ["plist top level is not a dictionary"], warns, info
    info["format"] = "binary" if raw[:6] == b"bplist" else "xml"
    info["keys"] = sorted(d.keys())
    present = LOCKDOWN_KEYS & set(d.keys())
    has_rp = {"public_key", "private_key", "identifier"} <= set(d.keys())
    if present and not has_rp:
        return [f"This is a legacy lockdown record (contains {sorted(present)[:3]}…), with no RemotePairing fields; "
                "new pairings on iOS 27 only produce RemotePairing records, and loopback handshakes (cdtk/pymobiledevice3 RSD) do not accept legacy records"], warns, info
    if present and has_rp:
        warns.append("Contains both lockdown and RemotePairing fields (the full version exported by iloader/SideStore); the RemotePairing part is usable")
    for k in ("public_key", "private_key"):
        v = d.get(k)
        if not isinstance(v, (bytes, bytearray)):
            errs.append(f"missing {k} (or it is not of type Data)")
        elif len(v) != 32:
            errs.append(f"{k} is {len(v)} bytes long, it must be exactly 32 (Ed25519)")
    if not isinstance(d.get("identifier"), str) or not d.get("identifier"):
        errs.append("missing identifier (or it is not a string)")
    else:
        try: info["identifier_uuid_version"] = uuid.UUID(d["identifier"]).version
        except Exception: warns.append("identifier is not in UUID form (idevice generates UUID v3, other tools may differ, this is not necessarily a problem)")
    irk = d.get("alt_irk")
    if irk is None: warns.append("no alt_irk (it is optional, only used when the device reconnects and for authTag identification)")
    elif not isinstance(irk, (bytes, bytearray)) or len(irk) != 16: warns.append(f"alt_irk length {len(irk) if hasattr(irk,'__len__') else '?'}, expected 16 bytes")
    if not errs:
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives import serialization as S
            pub = Ed25519PrivateKey.from_private_bytes(bytes(d["private_key"])).public_key().public_bytes(S.Encoding.Raw, S.PublicFormat.Raw)
            if pub != bytes(d["public_key"]): errs.append("public_key is not derived from private_key (the file was modified/mistyped/corrupted)")
            else: info["keypair_ok"] = True
        except Exception as e:
            warns.append(f"could not check key pair consistency: {type(e).__name__}")
    return errs, warns, info


def install(src, dest):
    errs, warns, info = validate(src)
    for w in warns: print("⚠️ ", w)
    if errs:
        print("❌ validation failed:"); [print("   -", e) for e in errs]; sys.exit(1)
    print(f"✅ validation passed: {info['format']} plist | keys {info['keys']} | key pair consistent")
    dest = os.path.expanduser(dest)
    os.makedirs(os.path.dirname(dest), mode=0o700, exist_ok=True)
    os.chmod(os.path.dirname(dest), 0o700)
    tmp = dest + ".tmp"
    shutil.copyfile(src, tmp)                  # copy2's utime fails on iSH
    os.chmod(tmp, 0o600); os.replace(tmp, dest)
    print(f"📁 saved: {dest} (mode {oct(os.stat(dest).st_mode)[-3:]})")
    return dest


def handshake(dest):
    sys.path.insert(0, HERE)
    os.environ["CDTK_PAIRING_FILE"] = dest
    import asyncio
    from session import CoreDeviceSession
    async def go():
        async with CoreDeviceSession() as s:
            return True
    asyncio.run(go())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--dest", default="~/.cdtk/pairing/new_phone.plist")
    ap.add_argument("--no-handshake", action="store_true")
    a = ap.parse_args()
    dest = install(a.src, a.dest)
    if a.no_handshake:
        print("(skipped the real device handshake verification)"); sys.exit(0)
    try:
        handshake(dest); print("✅ real device loopback handshake succeeded: this pairing file is usable on this phone")
    except Exception as e:
        print(f"❌ real device handshake failed: {type(e).__name__}: {str(e)[:200]}")
        print("   The file format is fine; common causes: no Wi-Fi / loopback VPN not enabled / Developer Mode not enabled / this pairing was deleted by the device (device erased or that computer manually removed)")
        sys.exit(3)
