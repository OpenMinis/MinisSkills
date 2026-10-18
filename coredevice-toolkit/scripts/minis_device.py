#!/usr/bin/env python3
"""
minis_device: iOS CoreDevice RSD 本地回环隧道会话核心库
基于 Surge 10.7.0.1 本地回环反射 + Node.js TLS-PSK + pmd-pytcp 纯用户态协议栈
"""

import asyncio
import base64
import json
import os
import plistlib
import struct
import subprocess
import sys
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

NODE_TLS_PROXY_CODE = """
const tls = require('tls');
const net = require('net');
const fs = require('fs');

const host = process.argv[2] || '10.7.0.1';
const port = parseInt(process.argv[3], 10);
const pskHex = process.argv[4];
const unixSock = process.argv[5] || '/tmp/tls_relay.sock';

if (!port || !pskHex) {
  console.error("Usage: node tls_psk_proxy.js <host> <port> <psk_hex> [unix_sock]");
  process.exit(1);
}

const psk = Buffer.from(pskHex, 'hex');

if (fs.existsSync(unixSock)) {
  try { fs.unlinkSync(unixSock); } catch(e) {}
}

const tlsSocket = tls.connect({
  host: host,
  port: port,
  ciphers: 'PSK-AES128-GCM-SHA256:PSK-AES256-GCM-SHA384:PSK-CHACHA20-POLY1305:PSK-AES128-CBC-SHA256:PSK-AES256-CBC-SHA384:PSK-AES128-CBC-SHA:PSK-AES256-CBC-SHA:PSK',
  minVersion: 'TLSv1.2',
  maxVersion: 'TLSv1.2',
  checkServerIdentity: () => undefined,
  rejectUnauthorized: false,
  pskCallback: (hint) => {
    return { psk: psk, identity: '' };
  }
}, () => {
  console.log('READY');
});

tlsSocket.on('error', (err) => {
  console.error('TLS Socket Error:', err.message);
  process.exit(1);
});

const server = net.createServer((clientSocket) => {
  clientSocket.pipe(tlsSocket);
  tlsSocket.pipe(clientSocket);
  clientSocket.on('error', () => {});
  tlsSocket.on('error', () => {});
});

server.listen(unixSock, () => {});
"""

def ensure_node_proxy_script():
    proxy_path = "/tmp/tls_psk_proxy.js"
    if not os.path.exists(proxy_path):
        with open(proxy_path, "w", encoding="utf-8") as f:
            f.write(NODE_TLS_PROXY_CODE.strip())
    return proxy_path

def find_pairing_file():
    env_p = os.environ.get("MINIS_PAIRING_FILE")
    if env_p and os.path.exists(env_p):
        return env_p

    search_dirs = [
        "/var/minis/workspace",
        "/var/minis/shared",
        "/var/minis/mounts",
        "/root",
    ]

    candidates = []
    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        for root, _, files in os.walk(sdir):
            for f in files:
                if f.endswith(".plist"):
                    candidates.append(os.path.join(root, f))

    candidates.sort(key=lambda x: (0 if "pair" in os.path.basename(x).lower() else 1, len(x)))

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
            "未找到可用的设备配对文件 (.plist)！\n"
            "请将电脑配对文件或 SideStore 导出的 pairing.plist 放入 /var/minis/workspace/ 或挂载目录，\n"
            "或设置环境变量 export MINIS_PAIRING_FILE=/path/to/pairing.plist"
        )
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

class MinisDeviceSession:
    """
    CoreDevice RSD 异步会话上下文管理器
    
    用法：
        async with MinisDeviceSession() as s:
            print("连接成功:", s.rsd.name)
    """
    def __init__(self, pairing_file=None):
        self.pairing_file = pairing_file
        self.node_proc = None
        self.sock_path = f"/tmp/tls_relay_{os.getpid()}.sock"

    async def __aenter__(self):
        record = load_pairing(self.pairing_file)
        self.reader, self.writer = await asyncio.open_connection(HOST, PORT)
        psk, c_key, s_key = await do_pair_verify(self.reader, self.writer, record)
        port = await create_listener(self.reader, self.writer, psk, c_key, s_key)

        proxy_script = ensure_node_proxy_script()
        if os.path.exists(self.sock_path):
            try: os.unlink(self.sock_path)
            except Exception: pass

        self.node_proc = subprocess.Popen(
            ["node", proxy_script, HOST, str(port), psk.hex(), self.sock_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        while True:
            line = self.node_proc.stdout.readline()
            if "READY" in line:
                break
            if not line and self.node_proc.poll() is not None:
                raise RuntimeError("Node.js TLS PSK 桥接进程异常退出")

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
        try:
            await self.dial_plane.__aexit__(None, None, None)
            self.read_task.cancel()
            self.tun_read_task.cancel()
            await self.userspace_tun.close()
            if self.node_proc:
                self.node_proc.terminate()
            if os.path.exists(self.sock_path):
                try: os.unlink(self.sock_path)
                except Exception: pass
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass
