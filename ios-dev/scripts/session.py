"""session.py — Connect to the local iOS RemoteXPC (RSD) service through a loopback such as Surge/LocalDevVPN (10.7.0.1).

Flow:
  1. TCP connect to 10.7.0.1:49152 (the device's own remoted), do Pair-Verify with the pairing record (rppairing.py)
  2. createListener: the device opens a TLS-PSK channel on a new port
  3. Start the Node bridge (psk_bridge.js) to turn that TLS-PSK channel into a local Unix socket (the PSK goes over stdin, never argv)
  4. On that channel, use pymobiledevice3's "userspace tunnel" to obtain an RSD, after which its various services are available (install, logs, ...)

Usage:
    async with CoreDeviceSession() as s:
        apps = await InstallationProxyService(s.rsd).get_apps()

Callers only rely on `.rsd`. The pairing file is located by the rules in rppairing.find_pairing_file.
"""
import asyncio
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import rppairing as rp

HOST = os.environ.get("IOSDEV_RSD_HOST", "10.7.0.1")
PORT = int(os.environ.get("IOSDEV_RSD_PORT", "49152"))
HERE = Path(__file__).resolve().parent
BRIDGE = HERE / "psk_bridge.js"


class SessionError(Exception):
    """Failed to establish the session. The message includes troubleshooting hints."""


def _diagnose_connect(exc):
    return (
        f"Cannot connect to the local loopback {HOST}:{PORT} ({type(exc).__name__}: {exc}). Check in order:\n"
        "  1. The phone must be connected to Wi-Fi (this port is not open on cellular);\n"
        "  2. The loopback VPN must be enabled (the Surge >= 5.23.0 module, or LocalDevVPN); only one VPN can be active at a time;\n"
        "  3. Settings > Privacy & Security > Developer Mode must be turned on;\n"
        "  4. Use `python3 doctor.py` and look at item 7: the loopback is only healthy if 49152 is reachable while a non-existent port is refused.")


class CoreDeviceSession:
    def __init__(self, pairing_file=None):
        self.pairing_file = pairing_file
        self.rsd = None
        self._reader = self._writer = None
        self._node = None
        self._tmp = None
        self._tun = self._plane = self._tcp_tunnel = None
        self._tasks = []

    async def __aenter__(self):
        try:
            await self._open()
        except BaseException:
            await self.__aexit__(None, None, None)    # clean up subprocesses and sockets even if it fails midway
            raise
        return self

    async def _open(self):
        # Deferred imports: pymobiledevice3 is only needed when actually building a session, so rppairing stays usable and testable on its own
        import pymobiledevice3.remote.tunnel_service as tunnel_service
        from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
        from pymobiledevice3.remote.tunnel_service import RemotePairingTcpTunnel
        from pymobiledevice3.remote.userspace_tunnel import UserspaceDialPlane, UserspaceTun

        record = rp.load_pairing(self.pairing_file)
        try:
            self._reader, self._writer = await asyncio.wait_for(asyncio.open_connection(HOST, PORT), 5.0)
        except Exception as e:
            raise SessionError(_diagnose_connect(e)) from e

        try:
            _, ck, sk = await asyncio.wait_for(rp.pair_verify(self._reader, self._writer, record), 15.0)
            psk = os.urandom(32)
            lport = await asyncio.wait_for(rp.create_listener(self._reader, self._writer, psk, ck, sk), 15.0)
        except asyncio.TimeoutError as e:
            raise SessionError("The device did not answer the handshake within 15 seconds. The loopback works (TCP connects) but remoted is not responding: "
                               "usually happens right after unlocking/sleeping, wait a few seconds and retry; if it persists, restart the loopback VPN.") from e
        except asyncio.IncompleteReadError as e:
            raise SessionError("The device disconnected midway through the handshake (the peer closed the connection). Most likely the pairing record was deleted "
                               "on the phone or belongs to another device, so re-pairing is required.") from e

        if not BRIDGE.is_file():
            raise SessionError(f"Missing {BRIDGE}")
        node = shutil.which("node")
        if not node:
            raise SessionError("node not found. Install it: apk add nodejs (Python 3.12's ssl does not support TLS-PSK, so Node is needed for this small piece)")

        self._tmp = tempfile.mkdtemp(prefix="iosdev_")
        os.chmod(self._tmp, 0o700)
        sock = os.path.join(self._tmp, "relay.sock")
        self._node = subprocess.Popen([node, str(BRIDGE), HOST, str(lport), sock],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self._node.stdin.write(psk.hex() + "\n")
        self._node.stdin.flush()

        loop = asyncio.get_running_loop()
        deadline = time.time() + 12
        ready = False
        while time.time() < deadline:
            if self._node.poll() is not None:
                err = (self._node.stderr.read() or "").strip()
                raise SessionError(f"TLS-PSK bridge exited (exit code {self._node.returncode}): {err[:200]}")
            line = await loop.run_in_executor(None, self._readline_nonblock)
            if line and "READY" in line:
                ready = True
                break
            await asyncio.sleep(0.05)
        if not ready:
            raise SessionError("Waited more than 12 seconds for the TLS-PSK bridge to become ready")

        r, w = await asyncio.open_unix_connection(sock)
        self._tcp_tunnel = RemotePairingTcpTunnel(r, w)
        hs = await asyncio.wait_for(self._tcp_tunnel.request_tunnel_establish(), 15.0)

        tunnel_service.USE_USERSPACE_TUNNEL = True
        self._tun = UserspaceTun()
        self._tun.addr = hs["clientParameters"]["address"]
        self._tun.mtu = hs["clientParameters"]["mtu"]
        await self._tun.up()
        self._tun.set_peer(hs["serverAddress"])
        self._tcp_tunnel.tun = self._tun
        self._tasks = [asyncio.create_task(self._tcp_tunnel.sock_read_task()),
                       asyncio.create_task(self._tcp_tunnel.tun_read_task())]

        self._plane = UserspaceDialPlane(self._tun, hs["serverAddress"])
        await self._plane.__aenter__()
        self.rsd = RemoteServiceDiscoveryService((hs["serverAddress"], hs["serverRSDPort"]),
                                                 open_connection=self._plane.dial)
        await self.rsd.connect()

    def _readline_nonblock(self):
        import select
        r, _, _ = select.select([self._node.stdout], [], [], 0.2)
        return self._node.stdout.readline() if r else ""

    async def __aexit__(self, *exc):
        # Each step is guarded separately: a failure in any one must not skip the cleanup that follows
        async def quiet(coro):
            try:
                await coro
            except Exception:
                pass
        if self.rsd:
            await quiet(self.rsd.close())
        if self._plane:
            await quiet(self._plane.__aexit__(None, None, None))
        for t in self._tasks:
            if not t.done():
                t.cancel()
        if self._tun:
            await quiet(self._tun.close()) if hasattr(self._tun, "close") else None
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
        if self._node and self._node.poll() is None:
            try:
                self._node.stdin.close()          # the bridge exits by itself when it sees stdin closed
                self._node.wait(timeout=3)
            except Exception:
                self._node.kill()
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)
        self.rsd = None
        return False
