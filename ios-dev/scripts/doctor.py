#!/usr/bin/env python3
"""doctor.py — ios-dev environment self-check. Read-only, changes nothing, prints no keys.
Usage: python3 doctor.py [--device]     (--device additionally performs one loopback handshake, which needs Wi-Fi and a pairing file)
Exit code: 0 all passed; 1 something failed. Each item reports ✅/⚠️/❌ with a fix hint.
"""
import json, datetime, os, plistlib, re, shutil, socket, subprocess, sys, time
if __name__ != "__main__":
    raise ImportError("doctor.py is a command-line script, not a library: run it with python3 doctor.py")


if any(a in ("-h", "--help") for a in sys.argv[1:]):
    print("Usage: python3 doctor.py [--device]\n"
          "  (no arguments)  read-only self-check: toolchain, dependencies, SDK, p12, token, provisioning profile, loopback, pairing file\n"
          "  --device        additionally perform a real device handshake (requires the loopback and pairing file to be ready; read-only)\n"
          "Every failed item carries a \"fix\" hint; see references/*.md for details.")
    sys.exit(0)
HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
fails = 0

def ok(m, fix=""): print("✅", m)
def warn(m): print("⚠️ ", m)
def bad(m, fix=""):
    global fails; fails += 1
    print("❌", m); fix and print("   ↳ fix:", fix)

def run(cmd, t=15):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=t)
    except Exception as e: return None

print("== 1. toolchain (build/sign)")
for b, hint in [("clang", "apk add clang lld llvm19"), ("ld64.lld", "apk add lld"), ("rcodesign", "put it in /usr/local/bin (apple-codesign 0.29+)"),
                ("openssl", "apk add openssl"), ("zip", "apk add zip"), ("node", "apk add nodejs (the loopback handshake needs Node 18+)")]:
    ok(f"{b}: {shutil.which(b)}") if shutil.which(b) else bad(f"missing {b}", hint)

print("\n== 2. Python dependencies")
for mod, pipn in [("yaml", "apk add py3-yaml"), ("cryptography", "apk add py3-cryptography"), ("websockets", "pip install websockets"),
                  ("pymobiledevice3", "pip install 'pymobiledevice3>=11.34' pmd-pytcp"), ("pmd_pytcp", "pip install pmd-pytcp")]:
    try: __import__(mod); ok(f"python module {mod}")
    except Exception: bad(f"missing python module {mod}", pipn)

print("\n== 3. iOS SDK")
_base = os.path.join(HOME, ".ios-sdk")
_vers = []
if os.path.isdir(_base):
    import re as _re
    for d in os.listdir(_base):
        m = _re.match(r"iPhoneOS(\d+(?:\.\d+)*)\.sdk$", d)
        if m and os.path.exists(os.path.join(_base, d, "System/Library/Frameworks/UIKit.framework")):
            _vers.append((tuple(int(x) for x in m.group(1).split(".")), os.path.join(_base, d)))
_vers.sort()
if not _vers:
    bad("no iOS SDK", "python3 scripts/install_sdk.py  (installs iPhoneOS26.5.sdk by default, about 330MB)")
else:
    ok(f"SDK: {_vers[-1][1]}")
    if _vers[-1][0][0] < 26:
        bad("SDK is older than 26, so iOS 26 APIs such as UIGlassEffect are unavailable", "python3 scripts/install_sdk.py")
    elif not os.path.isdir(os.path.join(_vers[-1][1], "System/Library/SubFrameworks/UIUtilities.framework")):
        bad("the 26 SDK is missing SubFrameworks/UIUtilities (UIKit headers will not find <UIUtilities/UIDefines.h>)", "re-run install_sdk.py")

print("\n== 4. rcodesign compatibility with p12 (0.29 cannot read OpenSSL3 default encryption)")
def _p12_pbes2(path):
    try:
        r = run(["openssl", "asn1parse", "-in", path, "-inform", "DER"], 10)
        out = (r.stdout or "") if r else ""
        return "1.2.840.113549.1.5.13" in out
    except Exception:
        return False

_p12s = []
_d = os.path.join(HOME, ".ios-signer/keys/dev.p12")
if os.path.exists(_d): _p12s.append(("default dev.p12", _d))
_paid = os.path.join(HOME, ".ios-signer/paid/dist.p12")
if os.path.exists(_paid): _p12s.append(("distribution/AdHoc certificate", _paid))
if not _p12s:
    warn("no p12 yet (it only exists after get-cert in step 5)")
for _label, p12 in _p12s:
    if _p12_pbes2(p12):
        warn(f"{_label}: the p12 is PBES2 (AES-256), rcodesign 0.29 wrongly reports 'wrong password'; mk.py converts it to 3DES and re-signs automatically")
    else:
        ok(f"{_label}: legacy p12 encryption (readable by rcodesign)")
    m = oct(os.stat(p12).st_mode)[-3:]
    (ok if m == "600" else warn)(f"{_label}: p12 mode {m}")

# Provisioning profile types: development / AdHoc (distribution), plus App ID and expiry
def _profile_info(path):
    # A provisioning profile is a CMS container, so stdout must be read as binary (run() uses text=True, which would corrupt the content)
    try:
        r = subprocess.run(["openssl", "smime", "-inform", "DER", "-verify", "-noverify", "-in", path],
                           capture_output=True, timeout=15)
        if r.returncode != 0: return None
        return plistlib.loads(r.stdout)
    except Exception:
        return None

for _pf in (os.path.join(HOME, ".ios-signer/keys/appconnect.mobileprovision"),
            os.path.join(HOME, ".ios-signer/keys/dev.mobileprovision"),
            os.path.join(HOME, ".ios-signer/paid/dist.mobileprovision")):
    if not os.path.exists(_pf): continue
    _p = _profile_info(_pf)
    if not _p:
        warn(f"cannot read provisioning profile: {os.path.basename(_pf)}"); continue
    _ent = _p.get("Entitlements", {})
    _appid = _ent.get("application-identifier", "?")
    _dev = _ent.get("get-task-allow") is True
    _devs = _p.get("ProvisionedDevices") or []
    _exp = _p.get("ExpirationDate")
    _days = (_exp - datetime.datetime.now()).days if _exp else None
    _kind = "development" if _dev else ("AdHoc/distribution" if _devs else "App Store/enterprise")
    _msg = f"{os.path.basename(_pf)}: {_kind} | {_appid} | {len(_devs)} devices"
    if _days is not None: _msg += f" | expires {_exp.date()} ({_days} days)"
    if _days is not None and _days <= 14:
        bad(_msg, "the provisioning profile is about to expire, regenerate it (devsvc.py create-profile)")
    elif _days is not None and _days <= 30:
        warn(_msg)
    else:
        ok(_msg)
    if not _dev:
        ok(f"  └ non-development provisioning profile: bundle_id must equal the App ID above (no XTL- prefix), and debugging is not possible")

print("\n== 5. account session / token")
tk = os.path.join(HOME, ".ios-signer/xcode_token.json")
if os.path.exists(tk):
    d = json.load(open(tk)); left = (d["expiry_ms"] / 1000 - time.time()) / 86400
    (ok if left > 1 else bad)(f"Xcode token has {left:.0f} days left", "python3 gsa.py (this triggers a verification code)")
else:
    _have_keys = os.path.exists(os.path.join(HOME, ".ios-signer/keys")) and any(
        f.endswith(".p12") for f in os.listdir(os.path.join(HOME, ".ios-signer/keys")))
    if _have_keys:
        ok("no xcode_token.json, but you already have your own p12: just use the \"own p12\" path, no account login needed")
    else:
        warn("no xcode_token.json: a free account must log in via gsa.py first; for a paid account provide your own p12 (see signing.md)")
ss = os.path.join(HOME, ".ios-signer/session.json")
ok("a saved login session exists (gsa.py --reuse works)") if os.path.exists(ss) else warn("no session.json")
for v in ("APPLE_ID", "APPLE_PASSWORD"):
    ok(f"environment variable {v} is set") if os.environ.get(v) else warn(f"environment variable {v} is not set (needed for login)")

print("\n== 6. provisioning profile")
pf = os.path.join(HOME, ".ios-signer/keys/dev.mobileprovision")
if os.path.exists(pf):
    sys.path.insert(0, HERE)
    try:
        import profile as prov
        s = prov.summarize(prov.load_profile(pf))
        left = (s["expires"].replace(tzinfo=None) - prov._now()).days
        (ok if left >= 2 else bad)(f"provisioning profile {s['name']} | App ID {s['bundle_pattern']} | {left} days left | {len(s['devices'])} devices", "python3 devsvc.py renew …  (regenerate; free accounts must renew every 7 days)")
    except Exception as e: bad(f"failed to parse the provisioning profile: {e}")
else:
    warn("no provisioning profile yet")

print("\n== 7. loopback channel (any solution: Surge / LocalDevVPN / Clash Mi, etc.)")
# Solution-agnostic criteria: is there an active VPN interface (utun*), and how does 10.7.0.1 behave. The real device handshake is item 9 (--device).
r = run(["ip", "-4", "-o", "addr"], 5)
utun = [l.split()[1] for l in (r.stdout.splitlines() if r else []) if l.split()[1].startswith("utun")]
ok("VPN virtual interface detected: " + ", ".join(utun)) if utun else warn("no utun interface found: the loopback VPN (Surge/LocalDevVPN etc.) may not be enabled")

def probe(port):
    s = socket.socket(); s.settimeout(3); t = time.time()
    try: s.connect(("10.7.0.1", port)); return "connected"
    except ConnectionRefusedError: return "refused"
    except Exception as e: return type(e).__name__
    finally: s.close()
a_, b_ = probe(49152), probe(1)
if a_ == "connected" and b_ == "refused": ok("10.7.0.1:49152 connects and a non-existent port is refused: loopback behaves correctly")
elif a_ == "refused" and b_ == "refused": bad("all ports on 10.7.0.1 are refused: the loopback is not up", "make sure the phone is on Wi-Fi and the loopback VPN is enabled; see references/loopback.md")
elif a_ == "connected" and b_ == "connected": bad("every port on 10.7.0.1 'connects': the tunnel terminates TCP itself and does not route packets back to this device", "upgrade Surge to >= 5.23.0 and restart the VPN; for other solutions check the routing configuration")
else: warn(f"10.7.0.1:49152={a_}, port 1={b_}")

# If it is Surge, also check the version and effective profile (only when the Surge API is readable)
try:
    conf = open("/var/minis/mounts/Surge/Documents/Mobile.conf", encoding="utf8").read()
    m = re.search(r"^http-api\s*=\s*([^@\s]+)@([^\s]+)", conf, re.M)
    import urllib.request
    api = lambda p: urllib.request.urlopen(urllib.request.Request(f"http://{m.group(2)}{p}", headers={"x-key": m.group(1)}), timeout=6)
    ver = api("/v1/environment").headers.get("X-Surge-Version", "?")
    vt = tuple(int(x) for x in re.findall(r"\d+", ver)[:3])
    (ok if vt >= (5, 23, 0) else warn)(f"[Surge] version {ver}" + ("" if vt >= (5, 23, 0) else " (<5.23.0 does not support [IP Rewrite]; ignore this if you use LocalDevVPN)"))
    eff = api("/v1/profiles/current?sensitive=0").read().decode().replace("\\/", "/")
    if "10.7.0.1 = reflect" in eff: ok("[Surge] the effective profile has [IP Rewrite] 10.7.0.1 = reflect")
    else: warn("[Surge] the effective profile has no 10.7.0.1 = reflect (ignore this if you use another loopback solution)")
except Exception:
    pass   # Surge not installed/mounted: not an error

r = run(["ip", "-4", "-o", "addr", "show", "en0"], 5)
ok("Wi-Fi (en0) is up:" + (r.stdout.split()[3] if r and r.stdout else "")) if (r and r.stdout.strip()) else bad("the phone is not connected to Wi-Fi", "the loopback depends on Wi-Fi; on cellular only, every port on 10.7.0.1 returns ConnectionRefused")

print("\n== 8. pairing file")
pairing = os.environ.get("CDTK_PAIRING_FILE", os.path.join(HOME, ".cdtk/pairing/new_phone.plist"))
if os.path.exists(pairing):
    import plistlib
    d = plistlib.load(open(pairing, "rb"))
    need = ["identifier", "private_key", "public_key"]
    miss = [k for k in need if k not in d]
    bad(f"the pairing file is missing fields {miss} (this is not the RemotePairing format, legacy lockdown records cannot be used)", "see references/pairing.md") if miss else ok(f"pairing file has all fields ({pairing})")
    m = oct(os.stat(pairing).st_mode)[-3:]; (ok if m == "600" else warn)(f"pairing file mode {m} (it contains a private key, should be 600)")
else:
    bad(f"pairing file not found {pairing}", "see references/pairing.md")

# pair_host is not required (an existing pairing file is enough), just report whether it is present and whether its provenance is trustworthy
_ph = shutil.which("pair_host")
if _ph:
    _prov = "/usr/share/doc/pair-host/PROVENANCE.txt"
    _mod = ""
    if os.path.exists(_prov):
        _m = re.search(r"^modifications:\s*(.+)$", open(_prov, errors="replace").read(), re.M)
        _mod = (" | provenance note: " + _m.group(1)[:40]) if _m else ""
    ok(f"pair_host installed: {_ph}{_mod}")
else:
    warn("pair_host not installed (only needed when you have to pair yourself): apk add pair-host, steps in references/pairing.md")

if "--device" in sys.argv:
    print("\n== 9. loopback handshake (real device)")
    sys.path.insert(0, HERE)
    try:
        import asyncio
        os.environ.setdefault("CDTK_PAIRING_FILE", pairing)
        from session import CoreDeviceSession
        async def go():
            async with CoreDeviceSession() as s: return True
        asyncio.run(go()); ok("RSD handshake succeeded")
    except Exception as e:
        bad(f"handshake failed: {type(e).__name__} {str(e)[:120]}", "see items 7 and 8 first; iOS requires Developer Mode to be enabled")

print("\n" + ("all checks passed" if not fails else f"{fails} item(s) failed"))
sys.exit(1 if fails else 0)
