# loopback.md — Local loopback (making 10.7.0.1 point back to the phone itself) and the RSD handshake

## Purpose and shared constraints
Send packets destined for `10.7.0.1` back to the phone itself, so programs on the phone can reach the local `remoted` (RSD, `10.7.0.1:49152`). Even with the channel up, **you still need a pairing file** to pass Pair-Verify.

**Hard constraints shared by every approach**
- **The phone must be on Wi-Fi**: iOS only opens lockdownd/RSD when associated with Wi-Fi (the repos' READMEs all claim 62078/49152 are closed on cellular; on this device every port on `10.7.0.1` returned `ConnectionRefused` on cellular).
- iOS can only run one VPN (NetworkExtension) at a time: once you pick a loopback approach you cannot run another VPN, unless it doubles as one itself (Surge/Clash Mi and the like).
- Developer Mode is enabled; the pairing file is valid.
- Our handshake layer (`session.py`, protocol in `rppairing.py`) **hardcodes `10.7.0.1:49152`**. Note: newer SideStore's minimuxer uses "the active VPN interface's utun address + 1" instead — that is SideStore's behavior and **does not affect this skill**.

## Options at a glance (pick one — **Surge is not required**)
| Option | How it works | Status |
|---|---|---|
| **LocalDevVPN** (free on the App Store, `SiamSadik/LocalDevVPN` etc.) | `NEPacketTunnelProvider`: utun local address `10.7.0.0/32`, routing only `10.7.0.1/32`, performs **address rewriting** on each packet (`10.7.0.0 ↔ 10.7.0.1`) and writes it back; the newest version switched to a `/32` utun + `/32` peer route, no longer occupying a LAN subnet (an iOS 26.4+ fix) | Verified by reading the source (`TunnelProv/PacketTunnelProvider.swift`); **not tested on this device** |
| **Surge ≥5.23.0** | `[IP Rewrite]` section with `10.7.0.1 = reflect` (swap source/destination and bounce back to the sender), together with `tun-included-routes` | **Tested and working on this device** (see below) |
| **Clash Mi** | Implemented with an override config; the README claims it mitigates some carriers' hostility toward `gsa.apple.com` | README only, **unverified** |
| Tailscale reflector / WireGuard reflector | Requires a server (Docker) to fold `10.7.0.1` back; the WireGuard README says it is "only needed in mainland China — if LocalDevVPN works, don't use this" | Aimed at SideStore's new architecture; **adaptation to this skill is unverified** |

> Difference between address rewriting (LocalDevVPN) and reflect (Surge): the former changes the packet's destination to the local address and sends it back, the latter swaps source/destination and sends it back to the sender. **Our handshake has only ever been tested with Surge's reflect**; if you switch to LocalDevVPN, first use the "Verification" section below to confirm the channel works before going further. I once inferred from the code that reflect "might not apply" — it turned out to be a version problem (Surge 5.22.1), not a principle problem, so don't substitute reasoning for hands-on testing.

## Verifying the channel (independent of the approach)
```sh
python3 scripts/doctor.py --device
```
Signs the channel works: `CoreDeviceSession` is established and `InstallationProxyService.get_apps` can list apps.
Manual comparison: connect to `10.7.0.1:49152` and to a nonexistent port (e.g. 1) —
- Both refused: the channel isn't up (not on Wi-Fi / VPN not running / routes not configured)
- Both "connect instantly" but no data: the tunnel is accepting TCP itself and not sending packets back to the phone (Surge <5.23.0 behaves this way)
- 49152 works, the rest are refused: normal

## Concrete Surge configuration (references/CoreDevice-Loopback.sgmodule)
```ini
[General]
ipv6-vif = disabled
tun-included-routes = %INSERT% 10.7.0.1/32
[IP Rewrite]
10.7.0.1 = reflect
```
- **Surge iOS ≥5.23.0 (2026-10-12) is required**. 5.22.1 does not understand `[IP Rewrite]` and silently drops it — you won't find it in the effective config.
- When `skip-proxy` contains `10.0.0.0/8`, `tun-included-routes` is mandatory.
- Some third-party tutorials omit `ipv6-vif = disabled`; it's in Surge's official manual. It isn't required for our handshake, but following the official form is safest.
- Making it a module lets you toggle it independently; **do not edit `Mobile.conf` directly**. After importing, **restart the Surge VPN once**.
- Verify against the "effective config": read `http-api = <key>@<addr>` from `Mobile.conf` and send the `x-key` header; `GET /v1/environment` shows the `X-Surge-Version` response header, `GET /v1/modules` shows the enabled list, and `GET /v1/profiles/current?sensitive=0` shows the merged config (the JSON escapes `/` as `\/`, so replace that before comparing).

## The 4 handshake steps (scripts/session.py + rppairing.py)
1. TCP connect to `10.7.0.1:49152`, plaintext handshake
2. **Pair-Verify**: X25519 plus a signature from the pairing file's Ed25519 private key; the device checks the public key
3. `createListener`: negotiate a PSK, and the device opens a new port
4. Node's `psk_bridge.js` connects over TLS-PSK plus `pmd-pytcp` userspace TCP/IP, and retrieves the RSD service list
Dependencies: Node ≥18, `pymobiledevice3>=11.34`, `pmd-pytcp` (import name `pmd_pytcp`), cryptography.

## Troubleshooting quick reference
| Symptom | Cause |
|---|---|
| Any port connects in 1 ms but no data | Surge <5.23.0, or the module isn't enabled / the VPN wasn't restarted |
| Both 49152 and a nonexistent port return `ConnectionRefused` | **Not on Wi-Fi** (only cellular `pdp_ip0`), or the loopback VPN isn't running |
| Handshake fails with `No pairing file found` / `pairing file does not exist` | `IOSDEV_PAIRING_FILE` (or the legacy `CDTK_PAIRING_FILE`) is not set |
| Handshake times out | Developer Mode off / pairing file invalid (device erased or trust removed) |
| `local_address is unavailable over an in-process (userspace) tunnel` | You are on a userspace tunnel; services that need the tunnel's local address (such as hardware touch injection) are unavailable — unrelated to the app |
- On the phone, `pgrep -x` cannot see processes; use `ps | grep '[.]/name'`.
