#!/usr/bin/env python3
"""devsvc.py — Python client for Apple's developer services (Xcode channel), replicating xtool's DeveloperServicesClient.

Write operations exist only for what is registered in the allowlist (register devices, create certificates/App IDs/provisioning profiles; the only deletion is provisioning profiles), and they require --yes. No revocation/deletion is included.
Dependency: ~/.ios-signer/xcode_token.json (produced by gsa.py). The token is never printed.

Usage:
  python3 devsvc.py whoami      # viewDeveloper + listTeams
  python3 devsvc.py certs  [teamId]
  python3 devsvc.py ids    [teamId]
  python3 devsvc.py devices [teamId]
"""
import gzip, json, os, plistlib, sys, urllib.error, urllib.request, uuid, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import anisette as A

BASE = "https://developerservices2.apple.com/services"
PROTO = "QH65B2"            # serviceProtocolVersion (legacy API)
CLIENT_ID = "XABBG36SBA"
XCODE_VERSION = "26.5 (17F42)"
APP_INFO = "com.apple.gs.xcode.auth"


import re as _re


def _write_allowed(method, path):
    if (method, path) in WRITE_ALLOWED:
        return True
    # Provisioning profiles are a regenerable derivative; with a free account an App ID can only have 1 profile, so renewing must delete the old one first (xtool does the same)
    return method == "DELETE" and bool(_re.fullmatch(r"/v1/profiles/[A-Z0-9]+", path))


def _inject_team(body, team_id):
    """xtool middleware: for POST/PATCH, write teamId into data.attributes."""
    import copy
    b = copy.deepcopy(body)
    if team_id:
        b.setdefault("data", {}).setdefault("attributes", {})["teamId"] = team_id
    return b


def _decode_body(raw, headers):
    """urllib does not decompress automatically; handle gzip/deflate based on Content-Encoding (or the gzip magic number)."""
    enc = (headers.get("Content-Encoding") or "").lower()
    if enc == "gzip" or raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    if enc == "deflate":
        try: return zlib.decompress(raw)
        except zlib.error: return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw


# Write operation allowlist. Every new write operation must be registered here explicitly, and the call site must ask the user for confirmation.
WRITE_ALLOWED = {("POST", "/v1/devices"), ("POST", "/v1/certificates"),
                 ("POST", "/v1/bundleIds"), ("POST", "/v1/profiles")}


class DevSvcError(Exception):
    def __init__(self, code, msg):
        super().__init__(f"{msg} ({code})"); self.code = code


def load_token():
    p = os.path.expanduser("~/.ios-signer/xcode_token.json")
    d = json.load(open(p))
    return d["adsid"], d["token"]


class Client:
    def __init__(self):
        self.adsid, self.token = load_token()
        self.anis, self.ci = A.get_headers()          # Anisette headers + client_info
        self.ctx = None                                # developerservices2 is fine with the system trust store

    def _headers(self, accept, ctype):
        h = {
            "Accept": accept, "Content-Type": ctype, "Accept-Language": "en-US", "Accept-Encoding": "gzip, deflate",
            "User-Agent": "Xcode", "X-Xcode-Version": XCODE_VERSION,
            "X-MMe-Client-Info": self.ci["client_info"],
            "X-Mme-Device-Id": self.anis["X-Mme-Device-Id"],
            "X-Apple-App-Info": APP_INFO,
            "X-Apple-I-Identity-Id": self.adsid,
            "X-Apple-GS-Token": self.token,
        }
        for k, v in self.anis.items():
            h[k] = v
        return h

    # ---------- legacy API: plist, used for team/developer information ----------
    def legacy(self, action, params=None):
        p = dict(params or {})
        p.update({"requestId": str(uuid.uuid4()).upper(), "clientId": CLIENT_ID,
                  "protocolVersion": PROTO, "userLocale": ["en_US"]})
        url = f"{BASE}/{PROTO}/{action}.action?clientId={CLIENT_ID}"
        body = plistlib.dumps(p, fmt=plistlib.FMT_XML)
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers=self._headers("text/x-xml-plist", "text/x-xml-plist"))
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = _decode_body(r.read(), r.headers)
        except urllib.error.HTTPError as e:
            raise DevSvcError(e.code, f"HTTP {e.code}: {_decode_body(e.read(), e.headers)[:200]!r}")
        d = plistlib.loads(raw)
        rc = d.get("resultCode", 0)
        if str(rc) not in ("0", "0.0"):
            raise DevSvcError(rc, d.get("userString") or d.get("resultString") or "unknown error")
        return d

    # ---------- new API: JSON:API (ASC style); GET/DELETE must be wrapped as POST ----------
    def api(self, method, path, query=None, team_id=None, body=None):
        from urllib.parse import urlencode
        h = self._headers("application/vnd.api+json", "application/vnd.api+json")
        url = BASE + path
        data = None
        if method == "DELETE" and not _write_allowed(method, path):
            raise DevSvcError(-1, f"refusing to send {method} {path} (only provisioning profiles may be deleted)")
        if method in ("GET", "DELETE"):
            q = dict(query or {})
            if team_id: q["teamId"] = team_id
            h["X-HTTP-Method-Override"] = method
            data = json.dumps({"urlEncodedQueryParams": urlencode(q)}).encode()
            http_method = "POST"
        elif _write_allowed(method, path):
            if body is None:
                raise DevSvcError(-1, "write operations must include a body")
            body = _inject_team(body, team_id)
            data = json.dumps(body).encode()
            http_method = method
        else:
            raise DevSvcError(-1, f"refusing to send {method} {path} (not in the write operation allowlist)")
        req = urllib.request.Request(url, data=data, method=http_method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(_decode_body(r.read(), r.headers) or b"{}")
        except urllib.error.HTTPError as e:
            raw = _decode_body(e.read(), e.headers)
            try: j = json.loads(raw)
            except Exception: j = {}
            errs = j.get("errors") or []
            msg = "; ".join(f"{x.get('code')}: {x.get('title') or x.get('detail')}" for x in errs) or raw[:200].decode("utf8", "replace")
            raise DevSvcError(e.code, f"HTTP {e.code} {msg}")

    def api_all(self, path, query=None, team_id=None, max_pages=20):
        """Read-only pagination: follow cursor/limit in links.next. Returns (data list, included list)."""
        from urllib.parse import urlparse, parse_qs
        q = dict(query or {}); data, inc = [], []
        for _ in range(max_pages):
            j = self.api("GET", path, query=q, team_id=team_id)
            data += j.get("data", []); inc += j.get("included", [])
            nxt = (j.get("links") or {}).get("next")
            if not nxt: break
            qs = parse_qs(urlparse(nxt).query)
            if "cursor" not in qs: break
            q = dict(query or {}); q["cursor"] = qs["cursor"][0]
            if "limit" in qs: q["limit"] = qs["limit"][0]
        return data, inc

    # ---------- business logic ----------
    def view_developer(self):
        return self.legacy("viewDeveloper").get("developer", {})

    def list_teams(self):
        return self.legacy("listTeams").get("teams", [])


def _is_paid_team(t):
    """Whether the team has an iOS Apple Developer Program membership.
    Note: this test is based on the field shape returned for free accounts (a free account reports "Xcode Free Provisioning Program").
    The real fields for paid accounts have **not been verified in practice**, so we only classify a team as paid when the text "Apple Developer Program" is clearly present,
    and treat anything inconclusive as non-paid (better to miss a block than to wrongly block a free user)."""
    for m in t.get("memberships", []) or []:
        if (m.get("platform") or "").lower() == "ios" and "Apple Developer Program" in (m.get("name") or ""):
            return True
    return False


PAID_REFUSAL = """\
⛔ A paid developer account was detected (team %s). This skill does not support logging in with a paid account through the Apple ID route.

Why: this route goes through reverse-engineered private APIs (the Xcode channel), which Apple may change or tighten at any time; on free accounts we
have already hit rate limiting (-22421) and outright rejection (-80045). If a paid account gets flagged, the impact is bigger than for a free account.

For a paid account, do this instead (no login, no private APIs):
  1. Create the certificate and provisioning profile yourself in Xcode or on developer.apple.com, then export a p12;
  2. export IOSDEV_P12_PASS=<p12 password>
  3. Fill in sign.p12 / sign.profile in project.yaml, then run python3 mk.py <project> --install
See the "Bring your own p12 (paid accounts)" section of references/signing.md.

If you fully understand the risk and still want to continue, append --i-know-the-risk to the command.
"""


def _refuse_if_paid(c, team_id, allow):
    """Write operations and queries check the team type before doing anything. Paid accounts are refused by default; only --i-know-the-risk lets them through."""
    if allow:
        return
    for t in c.list_teams():
        if t.get("teamId") == team_id and _is_paid_team(t):
            sys.exit(PAID_REFUSAL % team_id)


_ALLOW_PAID = "--i-know-the-risk" in sys.argv


def _team(c, arg):
    teams = c.list_teams()
    if arg: tid = arg
    elif len(teams) == 1: tid = teams[0]["teamId"]
    else: sys.exit("multiple teams found, please specify the teamId explicitly: " + ", ".join(t["teamId"] for t in teams))
    _refuse_if_paid(c, tid, _ALLOW_PAID)
    return tid


def _tail(s, n=8):
    return ("…" + s[-n:]) if s and len(s) > n else (s or "")


def cmd_certs(c, team):
    data, _ = c.api_all("/v1/certificates", team_id=team)
    print(f"== certificates: {len(data)} (team {team})")
    import datetime
    for x in sorted(data, key=lambda r: r["attributes"].get("expirationDate") or ""):
        a = x["attributes"]
        print(f"  - id={x['id']} | type={a.get('certificateType')} | name={a.get('name') or a.get('displayName')} | "
              f"serial{_tail(a.get('serialNumber'))} | expires={str(a.get('expirationDate'))[:10]} | platform={a.get('platform')}")
    return data


def cmd_devices(c, team):
    data, _ = c.api_all("/v1/devices", team_id=team)
    print(f"== registered devices: {len(data)} (team {team})")
    for x in data:
        a = x["attributes"]
        udid = a.get("udid") or ""
        print(f"  - id={x['id']} | {a.get('name')} | {a.get('deviceClass')} | UDID {udid[:8]}…{udid[-4:]} | status={a.get('status')}")
    return data


def cmd_ids(c, team):
    data, _ = c.api_all("/v1/bundleIds", team_id=team)
    print(f"== App IDs (Bundle IDs): {len(data)} (team {team})")
    for x in data:
        a = x["attributes"]
        print(f"  - id={x['id']} | {a.get('identifier')} | {a.get('name')} | platform={a.get('platform')}")
    return data


def cmd_profiles(c, team):
    data, _ = c.api_all("/v1/profiles", team_id=team)
    print(f"== provisioning profiles: {len(data)} (team {team})")
    for x in data:
        a = x["attributes"]
        print(f"  - id={x['id']} | {a.get('name')} | type={a.get('profileType')} | state={a.get('profileState')} | expires={str(a.get('expirationDate'))[:10]}")
    return data


def cmd_add_device(c, team, name, udid, yes):
    """Register a device. An existing one (409) counts as success, same as xtool."""
    body = {"data": {"type": "devices", "attributes": {"name": name, "platform": "IOS", "udid": udid}}}
    shown = json.loads(json.dumps(body)); shown["data"]["attributes"]["teamId"] = team
    print("about to send: POST", BASE + "/v1/devices")
    print(json.dumps(shown, ensure_ascii=False, indent=2))
    if not yes:
        print("\n(--yes not given, preview only, no request was sent)"); return None
    try:
        r = c.api("POST", "/v1/devices", team_id=team, body=body)
    except DevSvcError as e:
        if e.code == 409:
            print("⚠️  409 conflict: the device may already exist, treating as success. Details:", e); return "exists"
        raise
    a = (r.get("data") or {}).get("attributes", {})
    print(f"✅ registered: id={r['data'].get('id')} | {a.get('name')} | status={a.get('status')} | class={a.get('deviceClass')}")
    return r


def cmd_create_cert(c, team, csr_path, out_cert, yes):
    """Request a development certificate (same as xtool: certificateType=DEVELOPMENT, CSR is RSA2048). Revokes nothing."""
    csr = open(os.path.expanduser(csr_path)).read()
    body = {"data": {"type": "certificates",
                     "attributes": {"csrContent": csr, "certificateType": "DEVELOPMENT"}}}
    shown = json.loads(json.dumps(body)); shown["data"]["attributes"]["csrContent"] = csr[:40].strip() + "…(CSR omitted)"
    shown["data"]["attributes"]["teamId"] = team
    print("about to send: POST", BASE + "/v1/certificates"); print(json.dumps(shown, ensure_ascii=False, indent=2))
    if not yes:
        print("\n(--yes not given, preview only)"); return None
    r = c.api("POST", "/v1/certificates", team_id=team, body=body)
    d = r.get("data") or {}; a = d.get("attributes", {})
    content = a.get("certificateContent")
    if not content:
        raise DevSvcError(-2, "the response has no certificateContent: " + json.dumps(r)[:300])
    import base64
    der = base64.b64decode(content)
    out = os.path.expanduser(out_cert); open(out, "wb").write(der); os.chmod(out, 0o600)
    print(f"✅ issued: id={d.get('id')} | type={a.get('certificateType')} | name={a.get('name') or a.get('displayName')} | "
          f"serial{_tail(a.get('serialNumber'))} | expires={str(a.get('expirationDate'))[:10]}")
    print(f"   certificate (DER) saved: {out}")
    return r


def app_identifier(team_id, name):
    """App IDs of free accounts are globally unique, so they cannot be chosen freely. Following xtool: add the XTL-<id>. prefix (here the team ID is used, it is stable and will not collide with others)."""
    if name.startswith("XTL-"): return name
    return f"XTL-{team_id}.{name}"


def cmd_create_appid(c, team, bundle_id, display, yes):
    full = app_identifier(team, bundle_id)
    body = {"data": {"type": "bundleIds", "attributes": {"name": display, "platform": "IOS", "identifier": full}}}
    shown = json.loads(json.dumps(body)); shown["data"]["attributes"]["teamId"] = team
    print("about to send: POST", BASE + "/v1/bundleIds"); print(json.dumps(shown, ensure_ascii=False, indent=2))
    # Idempotent: reuse it if it already exists
    data, _ = c.api_all("/v1/bundleIds", query={"filter[identifier]": full}, team_id=team)
    hit = [x for x in data if x["attributes"].get("identifier") == full]   # filter is a prefix match, so compare exactly again
    if hit:
        print(f"♻️  already exists, reusing: id={hit[0]['id']} | {full}"); return hit[0]
    if not yes:
        print("\n(--yes not given, preview only)"); return None
    r = c.api("POST", "/v1/bundleIds", team_id=team, body=body)
    d = r["data"]; print(f"✅ App ID created: id={d['id']} | {d['attributes'].get('identifier')} | {d['attributes'].get('name')}")
    return d


def cmd_create_profile(c, team, appid_id, cert_id, out, yes, device_ids=None):
    """Generate a development provisioning profile: bind the App ID + the given certificate + all iOS devices."""
    devs, _ = c.api_all("/v1/devices", team_id=team)
    dev_ids = device_ids or [x["id"] for x in devs if (x["attributes"].get("deviceClass") or "").upper() in ("IPHONE", "IPAD", "IPOD", "APPLE_WATCH") and x["attributes"].get("status") == "ENABLED"]
    if not dev_ids: raise DevSvcError(-3, "the team has no usable devices, register a device first")
    name = f"minis profile {appid_id}"
    body = {"data": {"type": "profiles", "attributes": {"name": name, "profileType": "IOS_APP_DEVELOPMENT"},
            "relationships": {
                "bundleId": {"data": {"type": "bundleIds", "id": appid_id}},
                "devices": {"data": [{"type": "devices", "id": i} for i in dev_ids]},
                "certificates": {"data": [{"type": "certificates", "id": cert_id}]}}}}
    shown = json.loads(json.dumps(body)); shown["data"]["attributes"]["teamId"] = team
    print("about to send: POST", BASE + "/v1/profiles"); print(json.dumps(shown, ensure_ascii=False, indent=2))
    if not yes:
        print("\n(--yes not given, preview only)"); return None
    r = c.api("POST", "/v1/profiles", team_id=team, body=body)
    d = r["data"]; a = d["attributes"]
    content = a.get("profileContent")
    if not content: raise DevSvcError(-2, "the response has no profileContent: " + json.dumps(r)[:300])
    import base64
    out = os.path.expanduser(out); open(out, "wb").write(base64.b64decode(content)); os.chmod(out, 0o600)
    print(f"✅ provisioning profile generated: id={d['id']} | {a.get('name')} | type={a.get('profileType')} | state={a.get('profileState')} | expires={str(a.get('expirationDate'))[:10]}")
    print(f"   saved: {out}")
    return r


def cmd_renew_profile(c, team, appid_id, cert_id, out, yes):
    """Renew: delete the old provisioning profiles under this App ID (provisioning profiles only), then regenerate with the same App ID + certificate + all devices."""
    olds, _ = c.api_all(f"/v1/bundleIds/{appid_id}/profiles", team_id=team)
    print(f"== existing provisioning profiles under this App ID: {len(olds)}")
    for x in olds:
        a = x["attributes"]
        print(f"  - id={x['id']} | {a.get('name')} | state={a.get('profileState')} | expires={str(a.get('expirationDate'))[:10]}")
    if not yes:
        print("\n(--yes not given, preview only; --yes will DELETE the provisioning profiles above and then recreate them. Only provisioning profiles are deleted, certificates/devices/App IDs are untouched)")
        return None
    for x in olds:
        c.api("DELETE", f"/v1/profiles/{x['id']}", team_id=team)
        print(f"🗑️  deleted provisioning profile {x['id']}")
    return cmd_create_profile(c, team, appid_id, cert_id, out, True)


def mask_email(e):
    if "@" not in e: return "(none)"
    a, d = e.split("@", 1)
    return a[:1] + "***@" + d


def cmd_whoami(c):
    dev = c.view_developer()
    print("== viewDeveloper")
    print("  email (masked):", mask_email(dev.get("email", "")))
    print("  developerStatus:", dev.get("developerStatus"))
    print("  name fields present:", bool(dev.get("firstName") or dev.get("dsFirstName")))
    teams = c.list_teams()
    print(f"\n== listTeams: {len(teams)} team(s)")
    for t in teams:
        ms = [(m.get("platform"), m.get("name")) for m in t.get("memberships", [])]
        paid = any(p == "ios" and "Apple Developer Program" in (n or "") for p, n in ms)
        print(f"  - team {t.get('teamId')} | {t.get('name')} | status={t.get('status')} | "
              f"{'paid (Apple Developer Program)' if paid else 'free/no paid iOS membership'}")
        for p, n in ms: print(f"      membership: [{p}] {n}")
    return teams


if __name__ == "__main__":
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__); sys.exit(0)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "whoami"
    c = Client()
    sys.argv = [x for x in sys.argv if x != "--i-know-the-risk"]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if cmd == "whoami":
        cmd_whoami(c)
    elif cmd in ("certs", "devices", "ids", "profiles"):
        team = _team(c, arg)
        {"certs": cmd_certs, "devices": cmd_devices, "ids": cmd_ids, "profiles": cmd_profiles}[cmd](c, team)
    elif cmd == "add-device":
        # usage: devsvc.py add-device <teamId> <name> <UDID> [--yes]
        yes = "--yes" in sys.argv
        a = [x for x in sys.argv[2:] if x != "--yes"]
        if len(a) != 3: sys.exit("usage: devsvc.py add-device <teamId> <name> <UDID> [--yes]")
        import re
        if not re.fullmatch(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{16}|[0-9A-Fa-f]{40}", a[2]):
            sys.exit(f"bad UDID format: {a[2]}")
        cmd_add_device(c, a[0], a[1], a[2], yes)
    elif cmd == "create-cert":
        # usage: devsvc.py create-cert <teamId> <csr path> <output cert.der> [--yes]
        yes = "--yes" in sys.argv
        a = [x for x in sys.argv[2:] if x != "--yes"]
        if len(a) != 3: sys.exit("usage: devsvc.py create-cert <teamId> <csr path> <output cert.der> [--yes]")
        cmd_create_cert(c, a[0], a[1], a[2], yes)
    elif cmd == "create-appid":
        yes = "--yes" in sys.argv; a = [x for x in sys.argv[2:] if x != "--yes"]
        if len(a) != 3: sys.exit("usage: devsvc.py create-appid <teamId> <bundleId> <display name> [--yes]")
        cmd_create_appid(c, a[0], a[1], a[2], yes)
    elif cmd == "create-profile":
        yes = "--yes" in sys.argv; a = [x for x in sys.argv[2:] if x != "--yes"]
        if len(a) != 4: sys.exit("usage: devsvc.py create-profile <teamId> <appIdId> <certId> <output .mobileprovision> [--yes]")
        cmd_create_profile(c, a[0], a[1], a[2], a[3], yes)
    elif cmd == "renew-profile":
        yes = "--yes" in sys.argv
        a = [x for x in sys.argv[2:] if x != "--yes"]
        if len(a) != 4:
            sys.exit("usage: devsvc.py renew-profile <teamId> <appIdId> <certId> <output .mobileprovision> [--yes]")
        cmd_renew_profile(c, a[0], a[1], a[2], a[3], yes)
    elif cmd == "all":
        team = _team(c, arg)
        for f in (cmd_certs, cmd_devices, cmd_ids, cmd_profiles):
            try: f(c, team)
            except DevSvcError as e: print(f"  ❌ {f.__name__}: {e}")
            print()
    else:
        sys.exit(f"unimplemented command: {cmd} (commands: whoami certs devices ids profiles all add-device create-cert create-appid create-profile renew-profile)")
