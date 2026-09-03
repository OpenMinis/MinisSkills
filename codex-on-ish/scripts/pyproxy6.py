#!/usr/bin/env python3
"""pyproxy6: MITM P-256 + version spoof (0.130->0.151) + models down-translation.

Adds to pyproxy5:
- HTTP/1.1 framing on both legs (request heads tracked for path)
- Forces accept-encoding: identity so responses are rewriteable text
- /backend-api/codex/models responses: buffered, JSON-transformed for v0.130
  (drop 'max'/'ultra' efforts), re-framed with new Content-Length
- Everything else (incl. SSE streams): raw pass-through

Singleton + refcount teardown identical to pyproxy5 (state: /tmp/codex-proxy).
"""
import socket, ssl, threading, sys, time, os, errno, re, json

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8894
OLD, NEW = b"0.130.0", b"0.151.0"
MODELS_MARK = b"/backend-api/codex/models"
ALLOWED_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}
STATE = "/tmp/codex-proxy"
CLIENTS = STATE + "/clients"
os.makedirs(CLIENTS, exist_ok=True)
LOGF = open(STATE + "/proxy.log", "a", buffering=1)

def log(*a):
    LOGF.write(time.strftime("%H:%M:%S ") + " ".join(map(str, a)) + "\n")

def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        return e.errno == errno.EPERM

def monitor():
    time.sleep(4)
    idle = 0
    while True:
        try:
            refs = os.listdir(CLIENTS)
        except FileNotFoundError:
            refs = []
        alive = False
        for r in refs:
            try:
                p = int(r)
            except ValueError:
                try: os.unlink(CLIENTS + "/" + r)
                except OSError: pass
                continue
            if pid_alive(p):
                alive = True
            else:
                try: os.unlink(CLIENTS + "/" + r)
                except OSError: pass
        if alive:
            idle = 0
        else:
            idle += 1
            if idle >= 2:
                log("last client gone, shutting down")
                try: os.unlink(STATE + "/proxy.pid")
                except OSError: pass
                os._exit(0)
        time.sleep(2)

SRV_CTX = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
SRV_CTX.load_cert_chain("/etc/pyproxy/srv256.pem", "/etc/pyproxy/srv256.key")
SRV_CTX.set_alpn_protocols(["http/1.1"])

def rewrite_ver(b):
    if OLD in b:
        b = b.replace(OLD, NEW)
    return b

def transform_models(body):
    d = json.loads(body)
    ms = d.get("models", [])
    kept = 0
    for m in ms:
        # v0.130 works over SSE on this stack; WS frames would stall the relay
        if m.get("prefer_websockets"):
            m["prefer_websockets"] = False
        lv = m.get("supported_reasoning_levels")
        if isinstance(lv, list):
            newlv = [e for e in lv if isinstance(e, dict) and e.get("effort") in ALLOWED_EFFORTS]
            if len(newlv) != len(lv):
                kept += len(lv) - len(newlv)
            m["supported_reasoning_levels"] = newlv
        dr = m.get("default_reasoning_level")
        if dr is not None and dr not in ALLOWED_EFFORTS:
            m["default_reasoning_level"] = "high"
    log("models transform: %d models, dropped %d effort levels, SSE forced" % (len(ms), kept))
    return json.dumps(d).encode()

def recv_head(sock, buf):
    """Accumulate until full HTTP head (\r\n\r\n). Returns (head, rest) or (None, buf)."""
    while b"\r\n\r\n" not in buf:
        try:
            d = sock.recv(65536)
        except OSError:
            return None, buf
        if not d:
            return None, buf
        buf += d
    i = buf.index(b"\r\n\r\n") + 4
    return buf[:i], buf[i:]

def recv_exact(sock, buf, n):
    """Read exactly n body bytes. Returns (body, rest) or (None, buf)."""
    while len(buf) < n:
        try:
            d = sock.recv(65536)
        except OSError:
            return None, buf
        if not d:
            return None, buf
        buf += d
    return buf[:n], buf[n:]

def recv_chunked(sock, buf):
    """Decode chunked body. Returns (body, rest) or (None, buf)."""
    body = b""
    while True:
        while b"\r\n" not in buf:
            try:
                d = sock.recv(65536)
            except OSError:
                return None, buf
            if not d:
                return None, buf
            buf += d
        line, buf = buf.split(b"\r\n", 1)
        try:
            size = int(line.split(b";")[0].strip(), 16)
        except ValueError:
            return None, buf
        if size == 0:
            # consume trailer until blank line
            while b"\r\n" not in buf:
                try:
                    d = sock.recv(65536)
                except OSError:
                    return None, buf
                if not d:
                    return None, buf
                buf += d
            _, buf = buf.split(b"\r\n", 1)
            return body, buf
        chunk, buf = recv_exact(sock, buf, size + 2)
        if chunk is None:
            return None, buf
        body += chunk[:size]

def hget(head, name):
    m = re.search(rb'(?i)^' + name + rb':\s*([^\r\n]*)', head, re.M)
    return m.group(1).strip() if m else None

def pump(a, b):
    """Raw bidirectional-ish single direction pump."""
    try:
        while True:
            d = a.recv(65536)
            if not d:
                break
            b.sendall(d)
    except OSError:
        pass

def c2u_framed(cli, up, state):
    """Client->upstream: frame requests, rewrite version, force identity encoding."""
    buf = b""
    while True:
        head, buf = recv_head(cli, buf)
        if head is None:
            break
        head = rewrite_ver(head)
        head = re.sub(rb'(?i)^accept-encoding:[^\r\n]*', b'accept-encoding: identity', head, flags=re.M)
        parts = head.split(b"\r\n", 1)[0].split()
        if len(parts) > 1:
            try:
                state["path"] = parts[1].decode(errors="replace")
            except Exception:
                pass
            # Block websocket upgrades on the responses endpoint: our relay is
            # HTTP-framed and codex falls back to SSE there. Any OTHER websocket
            # upgrade (e.g. remote-control relay) switches to raw passthrough.
            if re.search(rb'(?i)^upgrade:', head, re.M):
                if state["path"].startswith("/backend-api/codex/responses"):
                    log("blocked WS upgrade -> forcing SSE fallback")
                    try:
                        cli.sendall(b"HTTP/1.1 501 WebSocket unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                    except OSError:
                        pass
                    for s in (cli, up):
                        try: s.shutdown(socket.SHUT_RDWR)
                        except OSError: pass
                    return
                # generic WS passthrough: forward head, then raw pump both legs
                log("WS passthrough:", state["path"][:70])
                up.sendall(head + buf)
                buf = b""
                pump(cli, up)
                return
            log("REQ", parts[0].decode(errors="replace"), state["path"][:80])
        te = hget(head, b"transfer-encoding")
        cl = hget(head, b"content-length")
        if te and b"chunked" in te.lower():
            # stream this request and connection raw from here on
            up.sendall(head)
            if buf:
                up.sendall(buf)
            pump(cli, up)
            return
        body = b""
        if cl:
            n = int(cl)
            body, buf = recv_exact(cli, buf, n)
            if body is None:
                up.sendall(head)
                if buf:
                    up.sendall(buf)
                return
            body = rewrite_ver(body)
        up.sendall(head + body)

def u2c_framed(up, cli, state):
    """Upstream->client: raw pump, except models responses which get rewritten."""
    buf = b""
    while True:
        head, buf = recv_head(up, buf)
        if head is None:
            break
        is_models = MODELS_MARK in state.get("path", "").encode() if state.get("path") else False
        status = head.split(b" ", 2)
        ok = len(status) > 1 and status[1] == b"200"
        log("RESP", state.get("path", "?")[:60], head.split(b"\r\n", 1)[0].decode(errors="replace")[:40])
        te = hget(head, b"transfer-encoding")
        cl = hget(head, b"content-length")
        chunked = te and b"chunked" in te.lower()
        if is_models and ok and (chunked or cl):
            if chunked:
                body, buf = recv_chunked(up, buf)
            else:
                body, buf = recv_exact(up, buf, int(cl))
            if body is None:
                cli.sendall(head)
                if buf:
                    cli.sendall(buf)
                pump(up, cli)
                return
            try:
                body = transform_models(body)
            except Exception as e:
                log("models transform failed, passing through:", repr(e))
            head = re.sub(rb'(?i)^transfer-encoding:[^\r\n]*\r\n', b'', head, flags=re.M)
            head = re.sub(rb'(?i)^content-length:[^\r\n]*', b'content-length: ' + str(len(body)).encode(), head, flags=re.M)
            if b"content-length" not in head.lower():
                head = head.replace(b"\r\n\r\n", b"\r\ncontent-length: " + str(len(body)).encode() + b"\r\n\r\n")
            cli.sendall(head + body)
            continue
        # everything else: forward head + buffered, then raw pump (streams)
        cli.sendall(head)
        if buf:
            cli.sendall(buf)
        pump(up, cli)
        return

DNS_CACHE = {}  # host -> (ips, ts)
DNS_TTL = 300

def resolve(host):
    """DNS with cache + retry; iSH resolver intermittently returns EAI_AGAIN."""
    now = time.time()
    if host in DNS_CACHE:
        ips, ts = DNS_CACHE[host]
        if now - ts < DNS_TTL:
            return ips
    last = None
    for attempt in range(4):
        try:
            infos = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
            ips = list(dict.fromkeys(i[4][0] for i in infos))
            if ips:
                DNS_CACHE[host] = (ips, now)
                return ips
        except socket.gaierror as e:
            last = e
            time.sleep(0.4)
    if host in DNS_CACHE:  # stale fallback beats failure
        ips, _ = DNS_CACHE[host]
        return ips
    raise last if last else socket.gaierror("resolve failed")

def connect_up(host, port, timeout=30):
    ips = resolve(host)
    last = None
    for ip in ips:
        try:
            return socket.create_connection((ip, port), timeout=timeout)
        except OSError as e:
            last = e
    raise last

def handle(cli):
    host = None
    try:
        cli.settimeout(90)
        head = b""
        while b"\r\n\r\n" not in head:
            c = cli.recv(4096)
            if not c:
                return
            head += c
        line = head.split(b"\r\n", 1)[0].decode(errors="replace")
        parts = line.split()
        if len(parts) < 2 or parts[0] != "CONNECT":
            cli.sendall(b"HTTP/1.1 405 Only CONNECT\r\nContent-Length: 0\r\n\r\n")
            return
        host, port = parts[1].rsplit(":", 1)
        port = int(port)
        log("CONN", host)
        up = ssl.create_default_context()
        try:
            up_s = up.wrap_socket(connect_up(host, port), server_hostname=host)
        except Exception as ce:
            log("upstream connect failed", host, repr(ce))
            try:
                cli.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
            return
        cli.sendall(b"HTTP/1.1 200 Tunnel established\r\n\r\n")
        cli.settimeout(None)
        tls_cli = SRV_CTX.wrap_socket(cli, server_side=True)
        state = {"path": ""}
        t = threading.Thread(target=c2u_framed, args=(tls_cli, up_s, state), daemon=True)
        t.start()
        u2c_framed(up_s, tls_cli, state)
        t.join()
    except Exception as e:
        log("ERR", host, repr(e))
    finally:
        try: cli.close()
        except OSError: pass

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    srv.bind(("127.0.0.1", PORT))
except OSError as e:
    if e.errno == errno.EADDRINUSE:
        sys.exit(0)
    raise
srv.listen(16)
open(STATE + "/proxy.pid", "w").write(str(os.getpid()))
log("pyproxy6 up on %d (spoof + models down-translate) pid=%d" % (PORT, os.getpid()))
threading.Thread(target=monitor, daemon=True).start()
while True:
    c, _ = srv.accept()
    threading.Thread(target=handle, args=(c,), daemon=True).start()
