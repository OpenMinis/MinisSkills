#!/usr/bin/env python3
"""
coredevice_session: iOS CoreDevice RSD 本地回环隧道会话核心库 (cdtk)
基于 Surge 10.7.0.1 本地回环反射 + Node.js TLS-PSK + pmd-pytcp 纯用户态协议栈
"""

import asyncio
import base64
import json
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

import pymobiledevice3.remote.tunnel_service as tunnel_service
from pymobiledevice3.remote.tunnel_service import RemotePairingTcpTunnel
from pymobiledevice3.remote.userspace_tunnel import UserspaceTun, UserspaceDialPlane
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService

HOST = "10.7.0.1"
PORT = 49152

SCRIPT_DIR = Path(__file__).resolve().parent

def get_node_proxy_script():
    bundled = SCRIPT_DIR / "tls_psk_proxy.js"
    if bundled.exists():
        return str(bundled)
    # 兼容回退：若作为独立 site-package 安装，尝试从本文件同级目录获取
    alt = Path(__file__).resolve().parent / "tls_psk_proxy.js"
    if alt.exists():
        return str(alt)
    raise FileNotFoundError("未找到 tls_psk_proxy.js 桥接脚本，请确认工具链完整安装。")

def find_pairing_file():
    env_p = os.environ.get("CDTK_PAIRING_FILE")
    if env_p and os.path.exists(env_p):
        return env_p

    # 安全收敛范围：仅在专属子目录或当前工作目录检索，禁止全盘盲目遍历
    search_dirs = [
        "/var/minis/workspace/cdtk",
        str(Path.cwd()),
    ]

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

def load_pairing(pairing_path=None):
    target = pairing_path or find_pairing_file()
    if not target or not os.path.exists(target):
        raise FileNotFoundError(
            "未找到可用的设备配对记录 (.plist)！\n"
            "安全说明：为防止误用不相关凭证，CDTK 仅从以下位置安全加载：\n"
            "  1. 显式参数 --pairing / path；\n"
            "  2. 环境变量 export CDTK_PAIRING_FILE=/path/to/pairing.plist；\n"
            "  3. 专用受控目录 /var/minis/workspace/cdtk/*.plist 或当前目录。\n"
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

        # 若底层宿主文件系统忽略了 chmod (如部分外部挂载卷/共享目录)，
        # 则自动安全隔离复制到属主独占的 0700 私有沙盒目录并强制 chmod 600，杜绝权限阻断
        if st.st_mode & 0o077:
            secure_dir = Path("/root/.cdtk/pairing")
            secure_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            try: os.chmod(secure_dir, 0o700)
            except Exception: pass
            
            isolated_target = secure_dir / Path(target).name
            shutil.copyfile(target, isolated_target)
            try: os.chmod(isolated_target, 0o600)
            except Exception: pass
            target = str(isolated_target)

    with open(target, "rb") as f:
        pl = plistlib.load(f)
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
        self.tmp_dir = None
        self.sock_path = None
        self.userspace_tun = None
        self.dial_plane = None
        self.read_task = None
        self.tun_read_task = None
        self.writer = None

    async def __aenter__(self):
        record = load_pairing(self.pairing_file)
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(HOST, PORT), timeout=5.0
            )
        except Exception as e:
            raise ConnectionError(
                f"无法连接到 CoreDevice RSD 本地回环 ({HOST}:{PORT}): {e}\n"
                "常见排查要点:\n"
                "1. 请确认 Surge 本地回环已生效 (配置中包含 10.7.0.1 = reflect 与 tun-included-routes = 10.7.0.1/32)；\n"
                "2. 请确认系统【设置 ➡️ 隐私与安全性】已开启「开发者模式」；\n"
                "3. 系统兼容性注意：本功能已在 iOS 18+ 真机实测通过。部分 iOS 17.x 早期系统 remoted 守护进程可能仅监听纯 IPv6 或端口发生漂移。"
            ) from e

        psk, c_key, s_key = await do_pair_verify(self.reader, self.writer, record)
        port = await create_listener(self.reader, self.writer, psk, c_key, s_key)

        proxy_script = get_node_proxy_script()
        
        # 安全加固：创建 0700 权限的隔离专属临时目录
        self.tmp_dir = tempfile.mkdtemp(prefix="cdtk_")
        os.chmod(self.tmp_dir, 0o700)
        self.sock_path = os.path.join(self.tmp_dir, "relay.sock")

        # 安全加固：PSK 绝不通过 argv 传递 (ps 可见)，改由 stdin 安全管道直接输入
        self.node_proc = subprocess.Popen(
            ["node", proxy_script, HOST, str(port), self.sock_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            self.node_proc.stdin.write(psk.hex() + "\n")
            self.node_proc.stdin.flush()
        except Exception as e:
            raise RuntimeError(f"向 Node.js 代理发送握手凭据失败: {e}")

        # 健壮性：带 10 秒超时判定，杜绝无限阻塞死锁
        start_t = time.time()
        ready = False
        while time.time() - start_t < 10.0:
            if self.node_proc.poll() is not None:
                err_msg = self.node_proc.stderr.read() if self.node_proc.stderr else ""
                raise RuntimeError(f"Node.js TLS PSK 桥接进程异常退出: {err_msg.strip()}")
            line = self.node_proc.stdout.readline()
            if "READY" in line:
                ready = True
                break
            await asyncio.sleep(0.05)

        if not ready:
            raise TimeoutError("等待 Node.js TLS PSK 桥接就绪超时 (10s)")

        self.r_sock, self.w_sock = await asyncio.open_unix_connection(self.sock_path)
        self.tcp_tunnel = RemotePairingTcpTunnel(self.r_sock, self.w_sock)
        handshake_res = await self.tcp_tunnel.request_tunnel_establish()

        server_addr = handshake_res["serverAddress"]
        server_port = handshake_res["serverRSDPort"]
        client_params = handshake_res["clientParameters"]
        
        tunnel_service.USE_USERSPACE_TUNNEL = True
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

        self.rsd = RemoteServiceDiscoveryService((server_addr, server_port), open_connection=self.dial_plane.dial)
        await self.rsd.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 严谨防御性资源回收：避免单个异常导致子进程与 Socket 泄漏
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
