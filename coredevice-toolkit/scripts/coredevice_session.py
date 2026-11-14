#!/usr/bin/env python3
"""
coredevice_session: iOS CoreDevice RSD 本地回环隧道会话核心库 (cdtk)
基于 Surge 10.7.0.1 本地回环反射 + Node.js TLS-PSK + pmd-pytcp 纯用户态协议栈
"""

import asyncio
import base64
import fcntl
import json
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

import pymobiledevice3.remote.tunnel_service as tunnel_service
import pymobiledevice3.remote.userspace_tunnel as userspace_tunnel
from pymobiledevice3.remote.tunnel_service import RemotePairingTcpTunnel
from pymobiledevice3.remote.userspace_tunnel import UserspaceTun, UserspaceDialPlane
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
from pymobiledevice3.remote.remotexpc import default_handshake_uuid

def _env_float(name, default, lo=None):
    """宽容解析环境变量：不合法就用默认值并在 stderr 提醒，绝不让 import 崩掉。"""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        val = float(raw)
    except ValueError:
        print("[cdtk] %s=%r 不是数字，按默认 %s 处理" % (name, raw, default), file=sys.stderr)
        return default
    if lo is not None and val < lo:
        return 0.0 if lo == 1.0 else default   # <=0 约定为"不限"
    return val

def _env_int(name, default, lo=None, hi=None):
    """宽容解析整型环境变量：不合法或越界就用默认值并在 stderr 提醒，绝不让 import 崩掉。"""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        val = int(raw.strip(), 10)
    except ValueError:
        print("[cdtk] %s=%r 不是整数，按默认 %s 处理" % (name, raw, default), file=sys.stderr)
        return default
    if lo is not None and val < lo:
        print("[cdtk] %s=%r 小于下限 %s，按默认 %s 处理" % (name, raw, lo, default), file=sys.stderr)
        return default
    if hi is not None and val > hi:
        print("[cdtk] %s=%r 大于上限 %s，按默认 %s 处理" % (name, raw, hi, default), file=sys.stderr)
        return default
    return val

# 网络容错：支持通过环境变量覆盖目标 Host / Port，默认指向 Surge 本地回环反射。
HOST = os.environ.get("CDTK_RSD_HOST", "10.7.0.1")
PORT = _env_int("CDTK_RSD_PORT", 49152, 1, 65535)
PORT_EXPLICIT = "CDTK_RSD_PORT" in os.environ
HANDSHAKE_TIMEOUT = _env_float("CDTK_HANDSHAKE_TIMEOUT", 10.0, lo=0.1)

# ── 控制端口动态发现（issue #1 / 缺陷 2）────────────────────────────────
# 设备端 remoted 的 RSD 监听端口会随 listener 重新通告而漂移（真机实测曾漂到 65389）。
# 硬编码 49152 在漂移后只会得到两种失败：ConnectionRefused（listener 已走），
# 或更隐蔽的「TCP 连上但 0 字节回包」（reflect 层接住了，remoted 从不答）。
# 策略：env 显式指定 → 缓存 → 首选端口，都失败再做 49152-65535 端口扫描 + RPPairing 指纹。
# 只有在「连接级失败」时才扫描；握手超时说明端口活着、设备没醒，扫了也白扫。
PORT_CACHE_FILE = os.environ.get("CDTK_RSD_PORT_CACHE", "/tmp/.cdtk_rsd_port.json")
PORT_SCAN_TIMEOUT = _env_float("CDTK_RSD_SCAN_TIMEOUT", 1.2, lo=0.1)
PORT_SCAN_CONCURRENCY = _env_int("CDTK_RSD_SCAN_CONCURRENCY", 128, 1, 1024)
def _parse_scan_range():
    raw = os.environ.get("CDTK_RSD_SCAN_RANGE", "49152-65535")
    try:
        lo, hi = raw.split("-", 1)
        return int(lo), int(hi) + 1
    except Exception:
        return 49152, 65536

PORT_SCAN_RANGE = _parse_scan_range()
PORT_SCAN_CHUNK = 512

# ── 跨进程会话互斥（一个仍在跑的隧道，绝不能被第二条命令顶掉）─────────────
# iOS 27.x 的 remoted 有一条不通融的规则（注释在 pymobiledevice3 remote/remotexpc.py）：
# **按源地址替换** —— 新连接只要源 IP 与已有 peer 相同，就先顶掉那条 peer 的连接，
# 连握手都还没读。本机回环反射下，所有进程的源地址都是同一个 10.7.0.x，
# 于是「两条 cdtk 命令同时跑」= 后一条把前一条的隧道踩死；踩死的一方报
# 「连上了但 0 字节回包」，被踩的一方报 ConnectionRefused / 中途断连。
# 端口扫描同理：扫描会向成千个端口建连，等于对 remoted 发起连番源地址替换。
# 所以会话与扫描一律先拿这把跨进程锁，串行进出。
LOCK_FILE = os.environ.get("CDTK_LOCK_FILE", "/tmp/.cdtk_session.lock")
LOCK_TIMEOUT = _env_float("CDTK_LOCK_TIMEOUT", 120.0, lo=0.0)   # <=0 约定为不限时

def _port_scan_enabled():
    return os.environ.get("CDTK_RSD_SCAN", "1") not in ("0", "false", "off")

class SessionBusyError(RuntimeError):
    """排队超时：另一条 cdtk 命令长期占着设备会话。"""

class SessionLock:
    """跨进程会话互斥（flock）。只清业务口径：同一台设备同一时刻一条 RSD 会话。

    用法：
        async with session_lock():
            async with CoreDeviceSession() as s:
                ...
    CoreDeviceSession 自己已经默认持锁，直接用它即可；只有绕开它自己裸连
    （如 cdtk-doctor 的 pair-verify + createListener）时才需要手动包一层。
    """

    def __init__(self, timeout=None, path=None):
        self.path = path or LOCK_FILE
        self.timeout = LOCK_TIMEOUT if timeout is None else timeout
        self._fd = None

    async def __aenter__(self):
        self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        loop = asyncio.get_running_loop()
        deadline = None if not self.timeout else loop.time() + self.timeout
        announced = False
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if deadline is not None and loop.time() > deadline:
                    wait = "%.0fs" % self.timeout
                    os.close(self._fd)
                    self._fd = None
                    raise SessionBusyError(
                        "另一条 cdtk 会话占用设备超过 %s（CDTK_LOCK_TIMEOUT 可调，0=不限时）。\n"
                        "remoted 按源地址替换连接，两条命令同时跑会互相踩掉隧道；\n"
                        "请等前一条结束，或先 cdtk-doctor --no-sweep 查看是否有残留会话。"
                        % wait)
                if not announced:
                    print("[cdtk] 另一条 cdtk 会话正在使用设备，排队等待…", file=sys.stderr)
                    announced = True
                await asyncio.sleep(0.2)
        try:
            os.ftruncate(self._fd, 0)
            os.write(self._fd, b"%d\n" % os.getpid())
        except Exception:
            pass
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(self._fd)
        except Exception:
            pass
        self._fd = None

def session_lock(timeout=None, path=None):
    """返回 SessionLock 上下文（给裸连路径用；CoreDeviceSession 内部已自动持锁）。"""
    return SessionLock(timeout=timeout, path=path)

def _read_port_cache(host):
    try:
        with open(PORT_CACHE_FILE) as f:
            d = json.load(f)
        return int(d["port"]) if d.get("host") == host else None
    except Exception:
        return None

def _write_port_cache(host, port):
    try:
        tmp = PORT_CACHE_FILE + ".%d.tmp" % os.getpid()
        with open(tmp, "w") as f:
            json.dump({"host": host, "port": port, "ts": time.time()}, f)
        os.replace(tmp, PORT_CACHE_FILE)
    except Exception:
        pass

def control_port_candidates(host=None):
    """返回 [(port, source)]，按尝试顺序排列。"""
    host = host or HOST
    if PORT_EXPLICIT:
        return [(PORT, "env")]
    out = []
    cached = _read_port_cache(host)
    for src, p in (("cache", cached), ("preferred", PORT)):
        if p and p not in [q for q, _ in out]:
            out.append((p, src))
    return out

def host_handshake_uuid(record=None):
    """RSD 握手要出示的 host UUID —— 必须与 pair-verify 里的身份一致（issue #1 缺陷 1）。

    remoted 的规则：同一个 peer 记住它见过的握手 UUID，一旦新握手带着**不同的** UUID 就来一次
    re-attach —— 该 peer 通告过的所有 service listener 全部关闭，每个端口都拒连。而 pair-verify
    出示的是配对记录的 `identifier`，RSD 握手默认却是 `uuid3(DNS, hostname)`（iSH 下恒为
    localhost，所有人同一个值）。两边不一致 ⇒ 每次会话都在主动触发 re-attach。

    所以这里统一取配对记录的 identifier：优先 env `CDTK_HOST_UUID`，其次配对记录，
    最后才退回全局默认（此时会与身份不一致，但至少不会崩）。
    """
    raw = os.environ.get("CDTK_HOST_UUID")
    if raw:
        try:
            return uuid.UUID(raw)
        except Exception:
            print("[cdtk] CDTK_HOST_UUID 不是合法 UUID，已忽略: %r" % raw, file=sys.stderr)
    if record:
        ident = record.get("identifier")
        if ident:
            try:
                return uuid.UUID(str(ident))
            except Exception:
                print("[cdtk] 配对记录 identifier 无法解析为 UUID: %r" % (ident,), file=sys.stderr)
    return default_handshake_uuid()


def _is_port_level_failure(err):
    """端口层失败（该扫端口） vs 设备层失败（端口活着但没醒，别扫）。"""
    if isinstance(err, asyncio.TimeoutError):
        return False
    text = "%s %r" % (type(err).__name__, err)
    return any(k in text for k in ("Refused", "ConnectionReset", "IncompleteReadError",
                                  "0 bytes read", "ConnectionError", "OSError",
                                  "Cannot connect", "unreachable"))

async def _tcp_probe(host, port, timeout):
    w = None
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        return True
    except Exception:
        return False
    finally:
        if w is not None:
            try:
                w.close()
            except Exception:
                pass

async def rsd_fingerprint(host, port, timeout=1.5):
    """真指纹：发一个 RPPairing 握手帧，只有回 RPPairing 魔数才算 remoted listener 活着。
    纯 TCP connect 不够 —— reflect 层会把连接接住再沉默（issue #1 记录的第二种失败形态）。
    这里只发握手第一帧、不做 pair-verify，不涉及身份 UUID，不会触发 re-attach。"""
    w = None
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        body = json.dumps({
            "message": {"plain": {"_0": {"request": {"_0": {"handshake": {"_0": {
                "hostOptions": {"attemptPairVerify": True}, "wireProtocolVersion": 19}}}}}}},
            "originatedBy": "host", "sequenceNumber": 0,
        }).encode()
        w.write(b"RPPairing" + struct.pack(">H", len(body)) + body)
        await w.drain()
        magic = await asyncio.wait_for(r.readexactly(9), timeout=timeout)
        return magic == b"RPPairing"
    except Exception:
        return False
    finally:
        if w is not None:
            try:
                w.close()
            except Exception:
                pass

SCAN_BUDGET = _env_float("CDTK_SCAN_BUDGET", 60.0, lo=1.0)

async def scan_for_rsd_port(host=None, skip=()):
    """分块扫描 49152-65535，先批量 TCP 探活、再对候选做 RPPairing 指纹。
    分块是为了不让 iSH 一次性创建上万协程；找到即返回。
    总耗时受 CDTK_SCAN_BUDGET（默认 60 秒）约束，超时返回 None，避免静默卡几分钟。"""
    host = host or HOST
    lo, hi = PORT_SCAN_RANGE
    skip = set(skip)
    deadline = asyncio.get_running_loop().time() + SCAN_BUDGET
    loop = asyncio.get_running_loop()
    for start in range(lo, hi, PORT_SCAN_CHUNK):
        if SCAN_BUDGET and loop.time() > deadline:
            print("[cdtk] 端口扫描超过 %ds 预算，停止（可用 CDTK_SCAN_BUDGET 调整或 CDTK_RSD_PORT 指定）"
                  % int(SCAN_BUDGET), file=sys.stderr)
            return None
        if start > lo:
            print("[cdtk] 已扫描到端口 %d…" % start, file=sys.stderr)
        found = []
        sem = asyncio.Semaphore(PORT_SCAN_CONCURRENCY)

        async def _probe(p):
            async with sem:
                if SCAN_BUDGET and loop.time() > deadline:
                    return
                if await _tcp_probe(host, p, PORT_SCAN_TIMEOUT):
                    found.append(p)

        await asyncio.gather(*[_probe(p) for p in range(start, min(start + PORT_SCAN_CHUNK, hi))],
                             return_exceptions=True)
        for p in sorted(found):
            if p in skip:
                continue
            if await rsd_fingerprint(host, p):
                return p
    return None

SCRIPT_DIR = Path(__file__).resolve().parent

def get_node_proxy_script():
    """定位 tls_psk_proxy.js。安装后它与本模块同放在 site-packages。"""
    env_script = os.environ.get("CDTK_NODE_PROXY")
    if env_script:
        p = Path(env_script)
        if p.is_file():
            return str(p)
        raise FileNotFoundError(f"CDTK_NODE_PROXY 指向的文件不存在: {env_script}")

    bundled = SCRIPT_DIR / "tls_psk_proxy.js"
    if bundled.is_file():
        return str(bundled)

    raise FileNotFoundError(
        "未找到 tls_psk_proxy.js。请重新运行 src/setup.sh，"
        "或设置 CDTK_NODE_PROXY=/path/to/tls_psk_proxy.js。"
    )

def find_pairing_file():
    env_p = os.environ.get("CDTK_PAIRING_FILE")
    if env_p:
        if os.path.exists(env_p):
            return env_p
        raise SystemExit("❌ CDTK_PAIRING_FILE 指向的文件不存在: %s" % env_p)

    # 默认只搜索受控目录。当前工作目录可能包含无关的 pairing 文件，
    # 仅在显式设置 CDTK_ALLOW_CWD_PAIRING=1 时纳入搜索。
    search_dirs = [
        "/root/.cdtk/pairing",
        "/var/minis/workspace/cdtk",
    ]
    if os.environ.get("CDTK_ALLOW_CWD_PAIRING") == "1":
        search_dirs.append(str(Path.cwd()))

    candidates = []
    for sdir in search_dirs:
        p = Path(sdir)
        if not p.is_dir():
            continue
        for f in p.glob("*.plist"):
            candidates.append(str(f))

    for cand in candidates:
        try:
            with open(cand, "rb") as fp:
                pl = plistlib.load(fp)
            if isinstance(pl, dict) and "identifier" in pl and "private_key" in pl and "public_key" in pl:
                return cand
        except Exception:
            continue
    return None

def load_pairing(pairing_path=None, isolate=True):
    target = pairing_path or find_pairing_file()
    if not target or not os.path.exists(target):
        raise FileNotFoundError(
            "未找到可用的设备配对记录 (.plist)！\n"
            "安全说明：为防止误用不相关凭证，CDTK 仅从以下位置安全加载：\n"
            "  1. 环境变量 CDTK_PAIRING_FILE 指向文件；\n"
            "  2. 环境变量 export CDTK_PAIRING_FILE=/path/to/pairing.plist；\n"
            "  3. 专用受控目录 /root/.cdtk/pairing/*.plist 或 /var/minis/workspace/cdtk/*.plist；\n"
            "  4. 当前工作目录（需显式开启 export CDTK_ALLOW_CWD_PAIRING=1）。\n"
            "请将配对文件存放在非云端同步目录，并设置 chmod 600。"
        )

    # 安全强隔离：配对文件含有 Ed25519 签名私钥，严禁群组或其它用户读取
    st = os.stat(target)
    if st.st_mode & 0o077:
        try:
            os.chmod(target, 0o600)
            st = os.stat(target)
        except Exception:
            pass

        if st.st_mode & 0o077 and not isolate:
            print(
                f"警告: 配对文件权限过宽 ({oct(st.st_mode & 0o777)})，"
                "且当前文件系统不支持 chmod，建议手动收紧权限。",
                file=sys.stderr,
            )

        # 若底层宿主文件系统忽略了 chmod (如部分外部挂载卷/共享目录)，
        # 则自动安全隔离复制到属主独占的 0700 私有沙盒目录并强制 chmod 600，杜绝权限阻断
        if st.st_mode & 0o077 and isolate:
            secure_dir = Path("/root/.cdtk/pairing")
            secure_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            try: os.chmod(secure_dir, 0o700)
            except Exception: pass
            
            isolated_target = secure_dir / Path(target).name
            if os.path.abspath(target) != str(isolated_target):
                tmp_path = str(isolated_target) + ".tmp.%d" % os.getpid()
                try:
                    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
                except OSError as e:
                    if e.errno == getattr(__import__("errno"), "ELOOP"):
                        raise SystemExit("❌ 隔离目录里已存在同名符号链接，请先删除: %s" % isolated_target)
                    raise
                try:
                    os.fchmod(fd, 0o600)
                    with open(target, "rb") as src, os.fdopen(os.dup(fd), "wb") as dst:
                        shutil.copyfileobj(src, dst)
                finally:
                    os.close(fd)
                os.replace(tmp_path, isolated_target)
            target = str(isolated_target)

    with open(target, "rb") as f:
        pl = plistlib.load(f)

    if not isinstance(pl, dict) or "identifier" not in pl or "private_key" not in pl or "public_key" not in pl:
        raise KeyError(
            f"配对文件 {target} 格式不合规，缺少必需字段 (identifier / private_key / public_key)。\n"
            "说明：iOS 远程配对握手必须提供配对身份标识符 (identifier)。\n"
            "若该文件通过电脑端 pymobiledevice3 生成，可能缺少 identifier。\n"
            "推荐在 iOS 端使用 StikPair 导出合规配对文件（详见 references/PAIRING_GUIDE.md）。"
        )

    return {
        "path": target,
        "identifier": pl["identifier"],
        "private_key": pl["private_key"][:32],
        "public_key": pl["public_key"][:32],
        "alt_irk": pl.get("alt_irk", b"")
    }

def encode_tlv8(entries):
    parts = []
    for t, d in entries:
        offset = 0
        while offset < len(d):
            chunk = d[offset:offset+255]
            parts.append(bytes([t, len(chunk)]) + chunk)
            offset += len(chunk)
    return b"".join(parts)

def decode_tlv8(data):
    res = {}
    idx = 0
    while idx < len(data):
        t = data[idx]
        l = data[idx+1]
        v = data[idx+2:idx+2+l]
        res[t] = res.get(t, b"") + v
        idx += 2 + l
    return res

async def do_pair_verify(reader, writer, record):
    async def send_plain(val, seq):
        b = json.dumps({"message": {"plain": {"_0": val}}, "originatedBy": "host", "sequenceNumber": seq}).encode()
        writer.write(b"RPPairing" + struct.pack(">H", len(b)) + b)
        await writer.drain()

    async def recv_plain():
        magic = await reader.readexactly(9)
        if magic != b"RPPairing":
            raise RuntimeError(f"意外的协议头: {magic!r}")
        l = struct.unpack(">H", await reader.readexactly(2))[0]
        body = json.loads((await reader.readexactly(l)).decode())
        return body["message"]["plain"]["_0"]

    await send_plain({"request": {"_0": {"handshake": {"_0": {"hostOptions": {"attemptPairVerify": True}, "wireProtocolVersion": 19}}}}}, 0)
    await recv_plain()

    ephem = X25519PrivateKey.generate()
    m1_tlv = encode_tlv8([(6, b"\x01"), (3, ephem.public_key().public_bytes_raw())])
    await send_plain({"event": {"_0": {"pairingData": {"_0": {"data": base64.b64encode(m1_tlv).decode(), "kind": "verifyManualPairing", "startNewSession": True}}}}}, 1)

    res_m2 = await recv_plain()
    d2 = base64.b64decode(res_m2["event"]["_0"]["pairingData"]["_0"]["data"])
    m2_tlv = decode_tlv8(d2)
    device_pub = m2_tlv[3]
    dev_x25519 = X25519PublicKey.from_public_bytes(device_pub)

    shared_secret = ephem.exchange(dev_x25519)
    session_key = HKDF(algorithm=hashes.SHA512(), length=32, salt=b"Pair-Verify-Encrypt-Salt", info=b"Pair-Verify-Encrypt-Info").derive(shared_secret)

    id_bytes = record["identifier"].encode()
    sig_mat = ephem.public_key().public_bytes_raw() + id_bytes + device_pub
    ed_priv = Ed25519PrivateKey.from_private_bytes(record["private_key"])
    sig = ed_priv.sign(sig_mat)
    inner = encode_tlv8([(1, id_bytes), (10, sig)])
    nonce3 = b"\x00\x00\x00\x00PV-Msg03"
    cipher3 = ChaCha20Poly1305(session_key).encrypt(nonce3, inner, b"")
    m3_tlv = encode_tlv8([(6, b"\x03"), (5, cipher3)])
    await send_plain({"event": {"_0": {"pairingData": {"_0": {"data": base64.b64encode(m3_tlv).decode(), "kind": "verifyManualPairing", "startNewSession": False}}}}}, 2)

    res_m4 = await recv_plain()
    d4 = base64.b64decode(res_m4["event"]["_0"]["pairingData"]["_0"]["data"])
    m4_tlv = decode_tlv8(d4)
    if m4_tlv.get(6) != b"\x04":
        raise RuntimeError("Pair-Verify failed! 设备配对校验未通过")

    client_key = HKDF(algorithm=hashes.SHA512(), length=32, salt=None, info=b"ClientEncrypt-main").derive(shared_secret)
    server_key = HKDF(algorithm=hashes.SHA512(), length=32, salt=None, info=b"ServerEncrypt-main").derive(shared_secret)
    return shared_secret, client_key, server_key

async def create_listener(reader, writer, psk, client_key, server_key):
    req_body = {
        "request": {
            "_0": {
                "createListener": {
                    "key": base64.b64encode(psk).decode(),
                    "transportProtocolType": "tcp",
                    "peerConnectionsInfo": [{"owningPID": os.getpid(), "owningProcessName": "CoreDeviceService"}]
                }
            }
        }
    }
    nonce = struct.pack("<Q", 0) + b"\x00\x00\x00\x00"
    cipher = ChaCha20Poly1305(client_key).encrypt(nonce, json.dumps(req_body).encode(), b"")
    
    env = {
        "message": {"streamEncrypted": {"_0": base64.b64encode(cipher).decode()}},
        "originatedBy": "host",
        "sequenceNumber": 3
    }
    b = json.dumps(env).encode()
    writer.write(b"RPPairing" + struct.pack(">H", len(b)) + b)
    await writer.drain()

    magic = await reader.readexactly(9)
    if magic != b"RPPairing":
        raise RuntimeError(f"createListener 收到意外的协议头: {magic!r}")
    l = struct.unpack(">H", await reader.readexactly(2))[0]
    res_env = json.loads((await reader.readexactly(l)).decode())
    enc_data = base64.b64decode(res_env["message"]["streamEncrypted"]["_0"])
    plain_resp = ChaCha20Poly1305(server_key).decrypt(nonce, enc_data, b"")
    res_obj = json.loads(plain_resp.decode())
    return res_obj["response"]["_1"]["createListener"]["port"]

class CoreDeviceSession:
    """
    CoreDevice RSD 异步会话上下文管理器 (cdtk)
    
    用法：
        async with CoreDeviceSession() as s:
            print("连接成功:", s.rsd.name)
    """
    def __init__(self, pairing_file=None):
        self.pairing_file = pairing_file
        self.node_proc = None
        self._stdout_fd = None
        self._stderr_fd = None
        self._node_stdout_buf = bytearray()
        self._node_stderr_buf = bytearray()
        self.tmp_dir = None
        self.sock_path = None
        self.userspace_tun = None
        self.tun = None
        self.dial_plane = None
        self.read_task = None
        self.tun_read_task = None
        self.writer = None
        self._lock = None

    def _close_ctrl(self):
        w = getattr(self, "writer", None)
        if w is not None:
            try:
                w.close()
            except Exception:
                pass

    async def _release_lock(self):
        if self._lock is not None:
            try:
                await self._lock.__aexit__(None, None, None)
            except Exception:
                pass
            self._lock = None

    async def release_lock(self):
        """提前释放会话锁（长任务结束后想让别的命令插进来时用）。"""
        await self._release_lock()

    async def _pair_verify_once(self, record, ctl_port):
        """在指定控制端口完成 connect + pair-verify + createListener，返回隧道监听端口。"""
        self.handshake_uuid = host_handshake_uuid(record)
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(HOST, ctl_port), timeout=5.0
        )
        psk, c_key, s_key = await asyncio.wait_for(
            do_pair_verify(self.reader, self.writer, record),
            timeout=HANDSHAKE_TIMEOUT,
        )
        listener_port = await asyncio.wait_for(
            create_listener(self.reader, self.writer, psk, c_key, s_key),
            timeout=HANDSHAKE_TIMEOUT,
        )
        return psk, c_key, s_key, listener_port

    async def __aenter__(self):
        # 先拿跨进程锁：remoted 会按源地址替换连接，两条命令同时跑必然互踢。
        if os.environ.get("CDTK_NO_LOCK") != "1":
            self._lock = SessionLock()
            await self._lock.__aenter__()
        try:
            return await self._aenter_tunnel()
        except BaseException:
            # 任何阶段失败都不能把锁带走（否则后续命令全部排队到超时）
            await self._release_lock()
            raise

    async def _aenter_tunnel(self):
        record = load_pairing(self.pairing_file)
        queue = control_port_candidates()
        tried, scan_done, last_err = [], False, None
        while queue:
            ctl_port, source = queue.pop(0)
            tried.append(ctl_port)
            try:
                psk, c_key, s_key, port = await self._pair_verify_once(record, ctl_port)
            except Exception as e:
                last_err = e
                self._close_ctrl()
                if not queue and not scan_done:
                    scan_done = True
                    if _port_scan_enabled() and not PORT_EXPLICIT and _is_port_level_failure(e):
                        print("[cdtk] 控制端口 %d 无 RSD 响应（%s），扫描 49152-65535 定位 remoted listener…"
                              % (ctl_port, type(e).__name__), file=sys.stderr)
                        found = await scan_for_rsd_port(HOST, skip=tried)
                        if found is not None:
                            print("[cdtk] 发现 RSD 监听端口 %d，已写入缓存" % found, file=sys.stderr)
                            queue.append((found, "scan"))
                continue
            self.ctl_port, self.ctl_port_source = ctl_port, source
            _write_port_cache(HOST, ctl_port)
            if source == "scan":
                print("[cdtk] 使用扫描发现的控制端口 %d" % ctl_port, file=sys.stderr)
            break
        else:
            msg = (
                f"无法连接到 CoreDevice RSD 本地回环 ({HOST}:{','.join(str(p) for p in tried) or PORT}): {last_err}\n"
                "连接握手失败，请逐项检查以下要点：\n"
                "  ① 代理软件本地回环：确认 Surge 已开启 10.7.0.1 = reflect 本地回环反射\n"
                "     (并配置 tun-included-routes = 10.7.0.1/32)；若自定义了端口，请同步设置\n"
                "     export CDTK_RSD_HOST=... / export CDTK_RSD_PORT=... 覆盖目标地址；\n"
                "  ② 系统【开发者模式】：确认【设置 ➡️ 隐私与安全性 ➡️ 开发者模式】已开启，\n"
                "     否则内核 remoted 守护进程不会监听 RSD 端口；\n"
                "  ③ 【iPhone 是否处于解锁亮屏状态】：锁屏会导致内核 RSD 端口被系统临时\n"
                "     挂起/挂断，连接失败。请解锁并保持屏幕常亮后重试！\n"
                "  ④ 已试端口: %s。若 49152-65535 范围内一个 RSD listener 都找不到，\n"
                "     说明 remoted 的 listener 已被关闭（双身份 re-attach / 锁屏挂起 /\n"
                "     长时间没有 paired-host 事件）。唯一可靠恢复是用数据线重插 USB\n"
                "     触发一次 paired-host 事件；重启手机无效。\n"
            ) % (", ".join(str(p) for p in tried) or str(PORT))
            await self._release_lock()
            if isinstance(last_err, asyncio.TimeoutError):
                raise TimeoutError(msg) from last_err
            raise ConnectionError(msg) from last_err

        proxy_script = get_node_proxy_script()
        
        # 安全加固：创建 0700 权限的隔离专属临时目录
        self.tmp_dir = tempfile.mkdtemp(prefix="cdtk_")
        os.chmod(self.tmp_dir, 0o700)
        self.sock_path = os.path.join(self.tmp_dir, "relay.sock")
        try:  # 供 cdtk-doctor 判活用：清理时绝不碰仍在运行的会话
            with open(os.path.join(self.tmp_dir, "pid"), "w") as f:
                f.write(str(os.getpid()))
        except Exception:
            pass

        try:
            # 安全加固：PSK 绝不通过 argv 传递 (ps 可见)，改由 stdin 安全管道直接输入
            # 采用二进制管道 + 非阻塞分块读取，根治阻塞式同步 IO 死锁隐患
            self.node_proc = subprocess.Popen(
                ["node", proxy_script, HOST, str(port), self.sock_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                self.node_proc.stdin.write((psk.hex() + "\n").encode())
                self.node_proc.stdin.flush()
            except Exception as e:
                raise RuntimeError(f"向 Node.js 代理发送握手凭据失败: {e}")

            # 健壮性：带 10 秒超时判定，杜绝无限阻塞死锁 (异步安全非阻塞读取)
            await self._wait_node_ready(timeout=10.0)

            self.r_sock, self.w_sock = await asyncio.open_unix_connection(self.sock_path)
            self.tcp_tunnel = RemotePairingTcpTunnel(self.r_sock, self.w_sock)
            handshake_res = await self.tcp_tunnel.request_tunnel_establish()

            server_addr = handshake_res["serverAddress"]
            server_port = handshake_res["serverRSDPort"]
            client_params = handshake_res["clientParameters"]
            
            tunnel_service.USE_USERSPACE_TUNNEL = True
            self._set_userspace_flag = True
            self.userspace_tun = UserspaceTun()
            self.userspace_tun.addr = client_params["address"]
            self.userspace_tun.mtu = client_params["mtu"]
            await self.userspace_tun.up()
            self.userspace_tun.set_peer(server_addr)
            self.tcp_tunnel.tun = self.userspace_tun
            
            self.read_task = asyncio.create_task(self.tcp_tunnel.sock_read_task())
            self.tun_read_task = asyncio.create_task(self.tcp_tunnel.tun_read_task())

            self.dial_plane = UserspaceDialPlane(self.userspace_tun, server_addr)
            await self.dial_plane.__aenter__()

            if os.environ.get("CDTK_DEBUG") == "1":
                print("[cdtk] RSD handshake uuid = %s（与 pair-verify 身份一致）" % self.handshake_uuid,
                      file=sys.stderr)
            self.rsd = RemoteServiceDiscoveryService(
                (server_addr, server_port),
                open_connection=self.dial_plane.dial,
                handshake_uuid=self.handshake_uuid,
            )
            await self.rsd.connect()

            # 登记为当前进程的活动用户态隧道：触控 (touch_session)、投屏等由设备主动推流的服务
            # 据此把 UDP 接收端开在 pytcp 栈上；不登记会退回内核 socket，报 local_address is unavailable
            self.tun = self.userspace_tun
            userspace_tunnel._active_tunnel = self
            userspace_tunnel.USERSPACE_ACTIVE = True
            return self
        except Exception:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 严谨防御性资源回收：避免单个异常导致子进程与 Socket 泄漏
        if getattr(userspace_tunnel, "_active_tunnel", None) is self:
            userspace_tunnel._active_tunnel = None
            userspace_tunnel.USERSPACE_ACTIVE = False
        if getattr(self, "_set_userspace_flag", False):
            try: tunnel_service.USE_USERSPACE_TUNNEL = False
            except Exception: pass
            self._set_userspace_flag = False
        self.tun = None

        if self._stdout_fd is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.remove_reader(self._stdout_fd)
            except Exception:
                pass
            self._stdout_fd = None

        if self._stderr_fd is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.remove_reader(self._stderr_fd)
            except Exception:
                pass
            self._stderr_fd = None

        if self.dial_plane:
            try:
                await self.dial_plane.__aexit__(None, None, None)
            except Exception:
                pass

        for task in [self.read_task, self.tun_read_task]:
            if task and not task.done():
                task.cancel()

        if self.userspace_tun:
            try:
                await self.userspace_tun.close()
            except Exception:
                pass

        if getattr(self, "tcp_tunnel", None):
            try:
                await self.tcp_tunnel.stop_tunnel()
            except Exception:
                pass

        if self.node_proc:
            try:
                self.node_proc.terminate()
                try:
                    self.node_proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.node_proc.kill()
            except Exception:
                pass

        if self.tmp_dir and os.path.exists(self.tmp_dir):
            try:
                shutil.rmtree(self.tmp_dir, ignore_errors=True)
            except Exception:
                pass

        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass

        # 锁放在最后释放：隧道真正关干净之前不让下一条命令进来（源地址替换会踩到残留连接）
        await self._release_lock()

    async def _wait_node_ready(self, timeout=10.0):
        """
        以异步事件驱动 + 非阻塞 IO 读取 Node.js 桥接进程的 stdout，
        严格在 timeout 秒内等待 'READY' 信号，杜绝同步 readline 导致的事件循环死锁。
        在 READY 信号就绪后，持续在后台排空管道（配合 16KB 上限循环缓冲区），
        彻底杜绝 Node 桥接进程在长会话中因日志/警告填满 ~64KB 管道缓冲区导致写阻塞挂死。
        """
        loop = asyncio.get_running_loop()
        self._stdout_fd = self.node_proc.stdout.fileno()
        self._stderr_fd = self.node_proc.stderr.fileno()

        # 设置管道描述符为非阻塞
        for fd in (self._stdout_fd, self._stderr_fd):
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        ready_event = asyncio.Event()

        def on_stdout():
            try:
                chunk = os.read(self._stdout_fd, 4096)
                if chunk:
                    self._node_stdout_buf.extend(chunk)
                    if len(self._node_stdout_buf) > 16384:
                        del self._node_stdout_buf[:-8192]
                    if b"READY" in self._node_stdout_buf:
                        ready_event.set()
                else:
                    # 遇到 EOF 时主动注销 reader
                    try:
                        loop.remove_reader(self._stdout_fd)
                    except Exception:
                        pass
            except (BlockingIOError, InterruptedError):
                pass
            except Exception:
                try:
                    loop.remove_reader(self._stdout_fd)
                except Exception:
                    pass
                ready_event.set()

        def on_stderr():
            try:
                chunk = os.read(self._stderr_fd, 4096)
                if chunk:
                    self._node_stderr_buf.extend(chunk)
                    if len(self._node_stderr_buf) > 16384:
                        del self._node_stderr_buf[:-8192]
                else:
                    # 遇到 EOF 时主动注销 reader
                    try:
                        loop.remove_reader(self._stderr_fd)
                    except Exception:
                        pass
            except (BlockingIOError, InterruptedError):
                pass
            except Exception:
                try:
                    loop.remove_reader(self._stderr_fd)
                except Exception:
                    pass

        loop.add_reader(self._stdout_fd, on_stdout)
        loop.add_reader(self._stderr_fd, on_stderr)

        start_time = time.monotonic()
        while not ready_event.is_set():
            if self.node_proc.poll() is not None:
                # 进程已提前退出，收集剩余 stderr
                on_stderr()
                err_msg = self._node_stderr_buf.decode(errors="replace").strip()
                raise RuntimeError(f"Node.js TLS PSK 桥接进程异常退出 (exit code {self.node_proc.returncode}): {err_msg}")

            remaining = timeout - (time.monotonic() - start_time)
            if remaining <= 0:
                raise TimeoutError(f"等待 Node.js TLS PSK 桥接就绪超时 ({timeout}s)")

            try:
                await asyncio.wait_for(ready_event.wait(), timeout=min(remaining, 0.2))
            except asyncio.TimeoutError:
                pass

