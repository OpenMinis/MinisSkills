#!/usr/bin/env python3
"""Install an already signed IPA using install_from_local from pymobiledevice3 11.x (pymobiledevice3 11.x no longer has the old .install() call)."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from session import CoreDeviceSession
from pymobiledevice3.services.installation_proxy import InstallationProxyService

async def main(ipa):
    last = [-1]
    def on_progress(pct, *a):
        p = int(pct)
        if p // 10 != last[0] // 10 or p >= 100:
            print(f"  progress {p}%", flush=True); last[0] = p
    async with CoreDeviceSession() as sess:
        print("📱 Tunnel established, starting install", os.path.basename(ipa), flush=True)
        inst = InstallationProxyService(sess.rsd)
        await inst.install_from_local(ipa, handler=on_progress)
        print("✅ install_from_local returned without exceptions", flush=True)

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python3 install_ipa.py <signed .ipa>\n"
              "Installs the IPA onto this device over the local loopback (10.7.0.1); requires: pairing file, loopback VPN, phone connected to Wi-Fi.\n"
              "Run python3 doctor.py --device first to check that the environment is ready.")
        sys.exit(0 if len(sys.argv) == 2 else 2)
    if not os.path.isfile(sys.argv[1]):
        sys.exit(f"❌ file not found: {sys.argv[1]}")
    asyncio.run(main(sys.argv[1]))
