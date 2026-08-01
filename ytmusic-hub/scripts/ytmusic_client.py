"""
ytmusic_client.py
Unified YTMusic client initializer for ytmusic-hub.

Handles two common issues in the iSH environment automatically:
  1. SSL certificate verification errors — patches urllib3 to disable cert checks
  2. DNS pollution for *.youtube.com — falls back to Google DoH and patches socket

Usage:
    import sys
    sys.path.insert(0, "/var/minis/skills/ytmusic-hub/scripts")
    from ytmusic_client import get_client
    yt = get_client()
"""

import ssl
import socket
import json
import urllib.request
import urllib3

AUTH_FILE = "/var/minis/workspace/ytmusic_headers.json"
TARGET_HOST = "music.youtube.com"
DOH_URL = "https://dns.google/resolve?name={}&type=A"


# ── SSL patch: applied at import time, runs only once ───────────────────────

def _patch_ssl_once():
    """
    Disable SSL certificate verification in urllib3 at two levels:
      1. create_urllib3_context: new contexts skip cert validation
      2. _ssl_wrap_socket_and_match_hostname: skip hostname matching
    """
    from urllib3.util import ssl_ as u3ssl
    import urllib3.connection as u3conn

    if getattr(u3ssl, "_ytmusic_patched", False):
        return  # already patched

    # Patch 1: disable cert verification in new SSL contexts
    _orig_ctx = u3ssl.create_urllib3_context
    def _patched_ctx(*a, **kw):
        ctx = _orig_ctx(*a, **kw)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    u3ssl.create_urllib3_context = _patched_ctx

    # Patch 2: skip hostname matching after handshake
    _orig_wrap = u3conn._ssl_wrap_socket_and_match_hostname
    def _patched_wrap(*a, **kw):
        kw["cert_reqs"] = ssl.CERT_NONE
        kw["assert_hostname"] = False
        kw["assert_fingerprint"] = None
        return _orig_wrap(*a, **kw)
    u3conn._ssl_wrap_socket_and_match_hostname = _patched_wrap

    urllib3.disable_warnings()
    u3ssl._ytmusic_patched = True


_patch_ssl_once()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ssl_reachable(host, ip=None):
    """Check SSL connectivity. Optionally connect via a specific IP."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        s = socket.create_connection((ip or host, 443), timeout=8)
        ssl_sock = ctx.wrap_socket(s, server_hostname=host)
        ssl_sock.close()
        return True
    except Exception:
        return False


def _doh_resolve(hostname):
    """Resolve hostname via Google DoH, bypassing local DNS pollution."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        DOH_URL.format(hostname),
        headers={"accept": "application/dns-json"}
    )
    with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
        data = json.loads(resp.read())
    ips = [r["data"] for r in data.get("Answer", []) if r["type"] == 1]
    return ips[0] if ips else None


# Track patched hostnames to avoid stacking wrappers
_dns_patched: set = set()

def _patch_dns(hostname, ip):
    """Force hostname to resolve to a specific IP via socket.getaddrinfo (idempotent)."""
    if hostname in _dns_patched:
        return
    _orig = socket.getaddrinfo
    def _patched(host, port, *a, **kw):
        if host == hostname:
            host = ip
        return _orig(host, port, *a, **kw)
    socket.getaddrinfo = _patched
    _dns_patched.add(hostname)
    print(f"  DNS patch: {hostname} -> {ip}")


# ── Main entry point ─────────────────────────────────────────────────────────

def get_client(auth_file=AUTH_FILE):
    """
    Return a ready-to-use YTMusic instance.
    Automatically resolves DNS pollution and SSL issues.
    Raises RuntimeError if the network is unreachable.
    """
    print(f"🔌 Connecting to {TARGET_HOST}...")

    if _ssl_reachable(TARGET_HOST):
        print(f"  ✅ Local DNS OK, connecting directly")
    else:
        print(f"  ⚠️  Local DNS polluted, resolving via DoH...")
        try:
            real_ip = _doh_resolve(TARGET_HOST)
            if not real_ip:
                raise RuntimeError("DoH returned no valid IP")
            print(f"  DoH resolved: {TARGET_HOST} -> {real_ip}")
            if not _ssl_reachable(TARGET_HOST, ip=real_ip):
                raise RuntimeError(f"IP {real_ip} is also unreachable. Check your proxy/VPN.")
            _patch_dns(TARGET_HOST, real_ip)
            _patch_dns("youtubei.googleapis.com", _doh_resolve("youtubei.googleapis.com") or real_ip)
        except Exception as e:
            raise RuntimeError(f"❌ Network unavailable: {e}\nPlease enable your proxy/VPN.") from e

    from ytmusicapi import YTMusic
    yt = YTMusic(auth_file)
    print(f"  ✅ YTMusic ready\n")
    return yt
