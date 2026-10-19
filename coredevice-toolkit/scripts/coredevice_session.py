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
import select
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

# 网络容错：支持通过环境变量覆盖目标 Host / Port，默认指向 Surge 本地回环反射。
HOST = os.environ.get("CDTK_RSD_HOST", "10.7.0.1")
PORT = int(os.environ.get("CDTK_RSD_PORT", "49152"))
HANDSHAKE_TIMEOUT = float(os.environ.get("CDTK_HANDSHAKE_TIMEOUT", "10"))

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
    if env_p and os.path.exists(env_p):
        return env_p

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
            "  1. 显式参数 --pairing / path；\n"
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
            shutil.copyfile(target, isolated_target)
            try: os.chmod(isolated_target, 0o600)
            except Exception: pass
            target = str(isolated_target)

    with open(target, "rb") as f:
        pl = plistlib.load(f)

    if not isinstance(pl, dict) or "identifier" not in pl or "private_key" not in pl or "public_key" not in pl:
        raise KeyError(
            f"配对文件 {target} 格式不合规，缺少必需字段 (identifier / private_key / public_key)。\n"
            "说明：iOS 远程配对握手必须提供配对身份标识符 (identifier)。\n"
            "若该文件通过电脑端 pymobiledevice3 生成，可能缺少 identifier。\n"
            "推荐在 iOS 端使用 SideStore / SideInstaller 导出合规配对文件（详见 references/PAIRING_GUIDE.md）。"
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
                "连接握手失败，请逐项检查以下三大要点：\n"
                "  ① 代理软件本地回环：确认 Surge 已开启 10.7.0.1 = reflect 本地回环反射\n"
                "     (并配置 tun-included-routes = 10.7.0.1/32)；若自定义了端口，请同步设置\n"
                "     export CDTK_RSD_HOST=... / export CDTK_RSD_PORT=... 覆盖目标地址；\n"
                "  ② 系统【开发者模式】：确认【设置 ➡️ 隐私与安全性 ➡️ 开发者模式】已开启，\n"
                "     否则内核 remoted 守护进程不会监听 RSD 端口；\n"
                "  ③ 【iPhone 是否处于解锁亮屏状态】：锁屏会导致内核 RSD 端口被系统临时\n"
                "     挂起/挂断，连接失败。请解锁并保持屏幕常亮后重试！"
            ) from e

        try:
            psk, c_key, s_key = await asyncio.wait_for(
                do_pair_verify(self.reader, self.writer, record),
                timeout=HANDSHAKE_TIMEOUT,
            )
            port = await asyncio.wait_for(
                create_listener(self.reader, self.writer, psk, c_key, s_key),
                timeout=HANDSHAKE_TIMEOUT,
            )
        except asyncio.TimeoutError as e:
            if hasattr(self, "writer") and self.writer:
                try:
                    self.writer.close()
                except Exception:
                    pass
            raise TimeoutError(
                f"CoreDevice 握手超时（{HANDSHAKE_TIMEOUT:.0f}s）。"
                "请确认设备已解锁、开发者模式已开启，且回环规则生效。"
            ) from e
        except Exception:
            if hasattr(self, "writer") and self.writer:
                try:
                    self.writer.close()
                except Exception:
                    pass
            raise

        proxy_script = get_node_proxy_script()
        
        # 安全加固：创建 0700 权限的隔离专属临时目录
        self.tmp_dir = tempfile.mkdtemp(prefix="cdtk_")
        os.chmod(self.tmp_dir, 0o700)
        self.sock_path = os.path.join(self.tmp_dir, "relay.sock")

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
        except Exception:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 严谨防御性资源回收：避免单个异常导致子进程与 Socket 泄漏
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

