"""anisette.py — Anisette V3 client (corresponds to xtool's OmnisetteADIProvider + ADIDataProvider).
An external V3 server handles ADI computation (it needs Apple's private libraries, so it cannot run locally); locally we only persist provisioning information.
This module never touches any Apple account.
"""
import asyncio, base64, hashlib, json, os, ssl, time, uuid, plistlib
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
APPLE_ROOT = os.path.join(HERE, "AppleRoot.pem")
STATE = os.path.expanduser("~/.ios-signer/anisette.json")
ANISETTE_URL = os.environ.get("ANISETTE_URL", "https://ani.sidestore.io")

def apple_ctx():
    """The certificate chain of gsa.apple.com uses Apple Root CA, which is not in the system trust store, so specify it explicitly."""
    return ssl.create_default_context(cafile=APPLE_ROOT)

def http(url, data=None, headers=None, ctx=None, timeout=30, retries=20):
    """Automatically retry on transient network errors (DNS/TLS disconnects/timeouts); do not retry on HTTP error codes."""
    import urllib.error, socket
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
                return r.read(), r.headers
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and i < retries - 1:   # public server gateway flakiness, retry
                last = e; time.sleep(1.5); continue
            raise
        except (urllib.error.URLError, ssl.SSLError, socket.timeout, ConnectionError, OSError) as e:
            last = e; time.sleep(0.8)
    raise last

def _load():
    try: return json.load(open(STATE))
    except Exception: return {}

def _save(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(d, open(STATE, "w"))
    os.chmod(STATE, 0o600)

def client_info():
    b, _ = http(ANISETTE_URL + "/v3/client_info")
    return json.loads(b)  # {client_info, user_agent}

def local_user():
    st = _load()
    if "uid" not in st:
        st["uid"] = str(uuid.uuid4()).upper(); _save(st)
    uid = st["uid"]
    return uid, hashlib.sha256(uid.encode()).hexdigest().upper()

# ---- Send GSA provisioning requests (spim / cpim) to Apple ----
def _gsa_post(url, request, ci, luid, uid):
    body = plistlib.dumps({"Header": {}, "Request": request}, fmt=plistlib.FMT_XML)
    h = {"Content-Type": "text/x-xml-plist", "Accept-Language": "en_US", "Accept": "*/*",
         "User-Agent": ci["user_agent"],   # without a UA, gsa returns 401 outright
         
         "X-Apple-I-MD-LU": luid, "X-MMe-Client-Info": ci["client_info"], "X-Mme-Device-Id": uid}
    b, _ = http(url, body, h, apple_ctx())
    resp = plistlib.loads(b)["Response"]
    st = resp.get("Status", {})
    if st.get("ec", 0) != 0:
        raise RuntimeError(f"GSA error {st.get('ec')}: {st.get('em')}")
    return resp

def lookup(ci, uid):
    h = {"X-MMe-Client-Info": ci["client_info"], "User-Agent": ci["user_agent"], "X-Mme-Device-Id": uid}
    b, _ = http("https://gsa.apple.com/grandslam/GsService2/lookup", headers=h, ctx=apple_ctx())
    return plistlib.loads(b)["urls"]

async def _provision(ci, urls, uid, luid):
    import websockets
    ws_url = ANISETTE_URL.replace("https", "wss").replace("http", "ws") + "/v3/provisioning_session"
    async with websockets.connect(ws_url, open_timeout=20) as ws:
        async def recv(expect):
            m = json.loads(await ws.recv())
            if m.get("result") != expect: raise RuntimeError(f"expected {expect}, got {m}")
            return m
        async def send(o): await ws.send(json.dumps(o))
        ident = base64.b64encode(uuid.UUID(uid).bytes).decode()
        await recv("GiveIdentifier"); await send({"identifier": ident})
        await recv("GiveStartProvisioningData")          # read the server instruction first, then ask Apple, so we don't wait idle until timeout
        r = await asyncio.to_thread(_gsa_post, urls["midStartProvisioning"], {}, ci, luid, uid)
        await send({"spim": base64.b64encode(r["spim"]).decode() if isinstance(r["spim"], bytes) else r["spim"]})
        cpim = (await recv("GiveEndProvisioningData"))["cpim"]
        r2 = await asyncio.to_thread(_gsa_post, urls["midFinishProvisioning"], {"cpim": cpim}, ci, luid, uid)
        b64 = lambda v: base64.b64encode(v).decode() if isinstance(v, bytes) else v
        await send({"ptm": b64(r2["ptm"]), "tk": b64(r2["tk"])})
        adi_pb = (await recv("ProvisioningSuccess"))["adi_pb"]
        return adi_pb, r2["X-Apple-I-MD-RINFO"]

def get_headers(force=False):
    """Return the Anisette headers needed for GSA requests (dict). On first use a provisioning round is performed."""
    ci = client_info()
    uid, luid = local_user()
    st = _load()
    if force or "adi_pb" not in st:
        urls = lookup(ci, uid)
        last = None
        for i in range(4):                       # public server occasionally times out/disconnects, retry
            try:
                adi_pb, rinfo = asyncio.run(_provision(ci, urls, uid, luid)); break
            except Exception as e:
                last = e; time.sleep(1.5)
        else:
            raise RuntimeError(f"Anisette provisioning failed repeatedly: {last}")
        st.update(adi_pb=adi_pb, rinfo=rinfo); _save(st)
    t = time.time()
    body = json.dumps({"identifier": base64.b64encode(uuid.UUID(uid).bytes).decode(),
                       "adi_pb": st["adi_pb"]}).encode()
    b, _ = http(ANISETTE_URL + "/v3/get_headers", body, {"Content-Type": "application/json"})
    d = json.loads(b)
    if d.get("result") not in (None, "GetHeadersSuccess") and "X-Apple-I-MD" not in d:
        raise RuntimeError(f"get_headers failed: {d}")
    return {
        "X-Apple-I-MD-M": d["X-Apple-I-MD-M"], "X-Apple-I-MD": d["X-Apple-I-MD"],
        "X-Apple-I-MD-RINFO": d.get("X-Apple-I-MD-RINFO", st["rinfo"]),
        "X-Apple-I-MD-LU": luid, "X-Mme-Device-Id": uid,
        "X-Apple-I-Client-Time": datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "X-Apple-Locale": "en_US", "X-Apple-I-TimeZone": "UTC",
    }, ci

if __name__ == "__main__":
    h, ci = get_headers()
    print("client_info:", ci["client_info"])
    for k, v in h.items(): print(f"  {k}: {v[:48]}{'…' if len(v)>48 else ''}")
