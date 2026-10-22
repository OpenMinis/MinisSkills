#!/usr/bin/env python3
"""pair_via_bonjour.py — On the phone, use minis-bonjour to advertise the pairing broadcast on behalf of pair_host, wait for the device to connect, and obtain the pairing file.

How it works: pair_host (the Linux static build) only handles the protocol inside iSH (TCP listener + SRP), but the multicast it sends itself via mdns-sd is rejected by iOS
(missing the multicast entitlement). So we extract the port and TXT from its log and advertise them via Minis's App layer (Network.framework) instead.

Usage:
  python3 pair_via_bonjour.py [--pair-host $(which pair_host)] [--out ~/.cdtk/pairing/new_phone.plist]
                              [--name Minis-Phone] [--timeout 300] [--dry-run]
Flow (the script prints each step):
  1) start pair_host  2) extract port/TXT  3) minis-bonjour advertise  4) you go to Settings > Privacy & Security > Developer Mode (scroll down)
  5) tap "Pair with <name>" → enter the lock screen passcode first → then enter the PIN this script prints  6) validate and save the plist
It will not: resolve/connect to its own advertisement (that would make pair_host receive an incomplete handshake and panic: early eof).
"""
import argparse, json, os, plistlib, re, shutil, subprocess, sys, time
if __name__ != "__main__":
    raise ImportError("pair_via_bonjour.py is a command-line script, not a library: run it with python3 pair_via_bonjour.py")


ap = argparse.ArgumentParser()
ap.add_argument("--pair-host", default=shutil.which("pair_host") or "/usr/local/bin/pair_host")
ap.add_argument("--out", default=os.path.expanduser("~/.cdtk/pairing/new_phone.plist"))
ap.add_argument("--name", default="Minis-Phone")
ap.add_argument("--model", default="Mac16,10")
ap.add_argument("--timeout", type=int, default=300)
ap.add_argument("--dry-run", action="store_true", help="only check prerequisites, do not start pair_host or advertise")
a = ap.parse_args()

LOG = "/tmp/pair_via_bonjour.log"
TMP_OUT = "/tmp/pair_via_bonjour.plist"


def die(m): print("❌", m); sys.exit(1)
def run(cmd, t=30): return subprocess.run(cmd, capture_output=True, text=True, timeout=t)
def alive(): return bool([l for l in run(["ps"]).stdout.splitlines() if "pair_host" in l and "grep" not in l and "pair_via" not in l])


def bj(*args):
    r = run(["minis-bonjour", *args, "--compact"], 40)
    try: return json.loads(r.stdout)
    except Exception: die(f"could not parse the minis-bonjour {' '.join(args)} output: {(r.stdout or r.stderr)[:200]}")


# ---------- prerequisite checks ----------
print("== prerequisite checks")
shutil.which("minis-bonjour") or die("the minis-bonjour command is missing (this requires a Minis build that includes the bridge)")
os.path.exists(a.pair_host) or die(f"{a.pair_host} not found. Install it: add the ish-pkgs apk repository and run `apk add pair-host` (see references/pairing.md, section \"Obtaining pair_host\")")
os.access(a.pair_host, os.X_OK) or die(f"{a.pair_host} is not executable, chmod +x it")
wifi = run(["ip", "-4", "-o", "addr", "show", "en0"]).stdout.split()
wifi or die("the phone is not connected to Wi-Fi: mDNS only works on a local network, and the Settings entry needs Wi-Fi")
print("  Wi-Fi:", wifi[3])
t = bj("types")
types = (t.get("data") or t).get("types", [])
names = [x["type"] if isinstance(x, dict) else x for x in types]
"_remotepairing-pairable-host._tcp" in names or die("Minis's NSBonjourServices does not include _remotepairing-pairable-host._tcp")
print("  ✅ that service type is declared in NSBonjourServices")
l = bj("list")["data"]
if l.get("advertisements") or l.get("forwards"):
    print(f"  ⚠️  the bridge still has leftover advertisements/forwards {len(l.get('advertisements', []))}/{len(l.get('forwards', []))}, cleaning up first")
    bj("stop", "--all")
if l.get("app_in_background"):
    die("Minis is currently in the background: advertisements are withdrawn by the system while in the background. Bring Minis to the foreground and run again")
if a.dry_run:
    print("\n(dry-run: prerequisite checks passed, nothing was started)"); sys.exit(0)

# ---------- 1) start pair_host ----------
print("\n== 1) starting pair_host")
subprocess.run(["pkill", "-f", "pair_host"], capture_output=True); time.sleep(1)
for f in (LOG, TMP_OUT):
    try: os.remove(f)
    except FileNotFoundError: pass
env = dict(os.environ, RUST_LOG="debug")           # only the debug level prints the TXT records, which the next step needs
proc = subprocess.Popen([a.pair_host, "--name", a.name, "--model", a.model, "--out", TMP_OUT],
                        stdout=open(LOG, "w"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
text = ""
for _ in range(20):
    time.sleep(0.5); text = open(LOG).read()
    if "Waiting for a device" in text: break
    if proc.poll() is not None: die("pair_host exited immediately on startup:\n" + text[-400:])
else:
    die("pair_host did not reach the waiting state within 20 seconds:\n" + text[-400:])

# ---------- 2) extract port / identifier / TXT ----------
m_port = re.search(r"port:\s+(\d+)", text); m_id = re.search(r"identifier:\s+(\S+)", text)
m_txt = re.search(r"TxtProperties \{ properties: \[(.*?)\] \}", text, re.S)
(m_port and m_id and m_txt) or die("could not extract port/identifier/TXT from the log (the pair_host version may have changed):\n" + text[-500:])
port, ident = m_port.group(1), m_id.group(1)
props = re.findall(r'key: "(\w+)", val: Some\("([^"]*)"\)', m_txt.group(1))
keys = {k for k, _ in props}
need = {"name", "identifier", "authTag", "model", "flags", "ver", "minVer"}
need <= keys or die(f"TXT is missing keys {need - keys}")
print(f"  port {port} | identifier {ident} | TXT keys {sorted(keys)}")

# ---------- 3) advertise ----------
print("\n== 2) advertising with minis-bonjour (the instance name must equal the identifier)")
r = bj("advertise", "_remotepairing-pairable-host._tcp", ident, port, *[f"{k}={v}" for k, v in props])
if not r.get("ok"):
    proc.terminate(); die(f"advertise failed: {json.dumps(r.get('error') or r, ensure_ascii=False)[:300]}")
adv = r["data"]
print(f"  ✅ advertised id={adv.get('id')} | state={adv.get('state')} | bridge port {adv.get('listener_port')} → guest {adv.get('guest_port')} | authTag {adv['txt'].get('authTag')}")
print(f"  ⚠️  instance name: requested {ident}, actual {adv.get('name')}", "" if adv.get("name") == ident else " ← mismatch! the Settings entry may not match")

print(f"""
== 3) now do this on the phone (keep Minis in the foreground, do not lock the screen)
   Settings > Privacy & Security > Developer Mode → scroll down → find "Pair with {a.name}"
   Tap it → enter the [lock screen passcode] first → then enter the [6-digit PIN] that appears in the log below
   (if the entry does not appear yet, keep waiting — some reports say it only shows up about a third of the time; once it appears, do not leave the Settings page)
""")

# ---------- 4) wait for PIN / connection / completion ----------
seen = set(); deadline = time.time() + a.timeout; done = False
while time.time() < deadline:
    time.sleep(1.5); text = open(LOG).read()
    for tag, pat in [("connection", r"Device connected from (\S+)"), ("PIN", r"(?:PIN|code|Enter)[^0-9\n]{0,40}(\d{6})")]:
        mm = re.search(pat, text)
        if mm and tag not in seen:
            seen.add(tag); print(f"  📣 {tag}: {mm.group(1)}")
    if re.search(r"Pairing complete|Paired with|wrote pairing|Saved pairing", text, re.I) or os.path.exists(TMP_OUT):
        done = True; break
    if "panicked" in text:
        print("  💥 pair_host panic:", (re.search(r"pairing failed:[^\n]*", text) or re.search(r"panicked[^\n]*\n[^\n]*", text)).group(0)[:160]); break
    if proc.poll() is not None: print("  pair_host has exited"); break
bj("stop", "--all")
if not done:
    proc.terminate(); print("\n❌ did not obtain a pairing file (timed out or failed). Log:", LOG); sys.exit(2)

# ---------- 5) validate and save ----------
time.sleep(1)
print("\n== 4) validating and saving")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pairing_import import validate, install
d = plistlib.load(open(TMP_OUT, "rb"))
install(TMP_OUT, a.out)
print(f"\n✅ pairing file is ready: {a.out}\n   Next step: CDTK_PAIRING_FILE={a.out} python3 doctor.py --device")
