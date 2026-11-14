---
name: coredevice-toolkit
description: "On-device CoreDevice RSD toolchain (CDTK) for iPhone — no Mac, no jailbreak. Builds Apple's developer tunnel inside the phone (loopback reflect + TLS-PSK + userspace TCP/IP): sideload IPAs, inject taps, read sandboxes, manage profiles, crash/battery diagnostics. Triggers: cdtk, CoreDevice."
compatibility: "iOS 18.0+ (verified on iOS 27.3) · Minis/iSH (Alpine aarch64) · Node.js 18+ · Python 3.10+ · pymobiledevice3 >=11.34,<12 · Surge >=5.23 for loopback"
---

# CoreDevice RSD toolchain (CDTK)

Operate the iPhone's own CoreDevice/RSD developer services **from the phone itself** —
no cable, no Mac, no Xcode, no jailbreak. Everything below runs inside Minis/iSH and
talks to the device's `remoted` over a local loopback.

## When to use it

- Sideload, re-sign or uninstall an IPA on this phone → `cdtk-install`
- Launch apps, list processes, inject taps/swipes → `cdtk-ctrl`
- Read an app sandbox (`Documents`/`Library`) or the media partition → `cdtk-fs`
- Crash reports, battery health, system logs → `cdtk-crash`, `cdtk-diag`
- Configuration profiles, home-screen layout, Jetsam exemption → `cdtk-profile`, `cdtk-springboard`, `cdtk-proc`
- "Is the tunnel working at all?" → `cdtk-doctor`

Use `ictrl-phone-control` instead when the task is *tap this button by its label*; CDTK's
`tap` is a blind coordinate injection with no view tree.

## How it works

```
 cdtk-* CLI  →  coredevice_session.py  →  node tls_psk_proxy.js (TLS-PSK, key via stdin)
             →  pmd-pytcp (userspace TCP/IP, no root, no utun device)
             →  10.7.0.1:49152   ←  Surge `10.7.0.1 = reflect` bounces it back to remoted
```

`remoted` listens on the device itself; the loopback makes it reachable without an
entitlement Apple would otherwise require. `pymobiledevice3` supplies the RSD client,
`pmd-pytcp` supplies the in-memory L2 stack (a non-jailbroken process cannot create `utun`).

## Prerequisites (all four need a human)

1. iPhone with **Developer Mode** on (Settings → Privacy & Security → Developer Mode).
2. A local-loopback rule: Surge `10.7.0.1 = reflect` + `tun-included-routes = 10.7.0.1/32`
   — see `references/SURGE_LOOPBACK.md`. Any VPN that can reflect `10.7.0.1/32` back to the
   device works; WireGuard-style clients have no equivalent and will fail with
   `ConnectionRefusedError` on every command.
3. A RemotePairing record exported **on the device** (StikPair, or wloc on a computer) —
   see `references/PAIRING_GUIDE.md`. Put it at `/root/.cdtk/pairing/`, mode `0600`.
   It contains an Ed25519 private key: never commit it, never put it in a synced folder.
4. Minis host (iSH / Alpine aarch64), `node` ≥ 18 and `python3` ≥ 3.10.

## Install and verify

```bash
sh scripts/setup.sh     # installs deps, copies the shared library, registers cdtk-* in /usr/local/bin
cdtk-doctor             # six steps; the last one creates a real tunnel
```

`setup.sh` is an *installing* action: it copies `coredevice_session.py` and
`tls_psk_proxy.js` into site-packages and overwrites `/usr/local/bin/cdtk-*`. Do not re-run it
on a working install. Alpine's Python is PEP-668 managed, so the script passes
`--break-system-packages` when pip supports it, and installs `pymobiledevice3` with
`--no-deps` — `sslpsk-pmd3` has no musl/aarch64 wheel and would otherwise compile and fail.

`cdtk-doctor` checks, in order: runtimes · Python modules · pairing file and its mode ·
loopback port (with an `RPPairing` fingerprint) · Pair-Verify · `createListener`. **Only step 6
proves the channel works** — Pair-Verify merely validates the host signature, so a green
steps 1–5 can still send zero bytes. Each failure prints the fix command.

Expected shape of a healthy run (redacted):

```
4. Checking Loopback Network Connectivity (10.7.0.1:49152):
  ✅ Loopback port reachable
  ✅ RSD listener answers RPPairing on 49152
5. Checking Handshake with iOS Remote Services:
  ✅ RSD handshake identity matches pairing record (xxxxxxxx…)
  ✅ Apple Pair-Verify protocol handshake successful (PSK negotiated)
6. Establishing Real Tunnel (createListener):
  ✅ Tunnel listener created on device (port xxxxx) — encrypted channel verified
```

## Tools

| Command | Purpose |
| --- | --- |
| `cdtk-doctor` | Six-step environment check; the only honest "does it work" test |
| `cdtk-install` | `list` / `info` / `install` / `uninstall` IPAs, local re-sign |
| `cdtk-ctrl` | `launch` / `procs` / `hid-list` / `tap` / `swipe` |
| `cdtk-fs` | `media` and `app` sandbox: `ls` / `cat` / `pull` |
| `cdtk-diag` | `battery` / `hw` / `log` / `perf` |
| `cdtk-crash` | `list` / `view` / `pull` / `latest` — system-wide `.ips` reports |
| `cdtk-profile` | `list` / `install` / `remove` configuration profiles |
| `cdtk-springboard` | `backup` / `apply` home-screen layout |
| `cdtk-proc` | `mem` (Jetsam waiver) / `signal` (stop, cont, term, kill) |
| `cdtk-inspect` | `list` / `eval` / `dump` / `nav` WebKit pages — `eval` needs `-y` |
| `cdtk-notify` | `start` / `step` / `done` banners; needs Minis' `apple-notification`, exits 3 without it |

## Common commands

```bash
cdtk-install list                       # user apps; -a includes system apps, -f filters
cdtk-install info com.example.app       # sandbox path, signing identity, App Groups
cdtk-install install app.ipa -y         # sign locally and install; falls back to rcodesign
cdtk-install install app.ipa -b com.example.app2 -n "Second copy" -y
cdtk-install uninstall com.example.app -y

cdtk-ctrl procs --apps-only             # running apps
cdtk-ctrl tap 585 642                   # pixel coords, native portrait, matches a screenshot
cdtk-ctrl swipe 585 1200 585 1800
cdtk-ctrl launch com.apple.Preferences  # --no-kill activates instead of restarting

cdtk-fs app pull com.example.app Library/Preferences/x.plist ./x.plist
cdtk-crash latest -s                    # parse the newest crash, save it under workspace
cdtk-springboard backup layout.plist    # always back up before apply
```

`tap`/`swipe` take **pixels** and convert to HID (0..65535) using the primary display's
`nativeSize`; `--hid` passes raw values through. Out-of-range coordinates exit non-zero
without injecting anything — a mis-scaled tap would otherwise land silently in the wrong place.

## Safety rules

Destructive or credential-touching subcommands require `-y/--yes`: `cdtk-install install|uninstall`,
`cdtk-profile install|remove`, `cdtk-proc signal`, `cdtk-springboard apply`, `cdtk-inspect eval`.
Without the flag they print what they *would* do and exit 1.

Ask the human before running any of them, and say the exact target out loud — a profile install
can add a root CA or an MDM enrollment, `springboard apply` replaces every page, and a single
`tap` on a Settings/erase screen can wipe the device.

`cdtk-ctrl tap|swipe|launch` have no `-y` gate (they are the point of the tool): state the
coordinates and the intended control first, and never inject input while a setup, restore or
payment screen is frontmost.

## Troubleshooting

**Every command fails with `ConnectionRefusedError 10.7.0.1:49152`, or connects and reads 0 bytes.**
Two shapes: `RST/Refused` means nothing listens; TCP connect then silence means the loopback layer
accepted the connection but `remoted` never answered (Surge < 5.23 drops `[IP Rewrite]` silently).
`coredevice_session` probes for the `RPPairing` magic to tell a live listener from a silent one, and
resolves the port as `CDTK_RSD_PORT` → `/tmp/.cdtk_rsd_port.json` → 49152 → a scan with fingerprints
(`CDTK_SCAN_BUDGET`, default 60 s).

**Two cdtk commands at once — one of them drops mid-way or reads 0 bytes.**
`remoted` replaces a peer **by source address**, before reading any handshake. Over a single-device
loopback every process shares that address, so only one RSD session can be live at a time; a port scan
replaces peers thousands of times and will kill whatever else is running. `CoreDeviceSession`
therefore holds `/tmp/.cdtk_session.lock` (`flock`) for the whole tunnel and `cdtk-doctor` steps 4–6
share it — a second command prints "another cdtk session is using the device, queueing…" and waits.
`CDTK_LOCK_TIMEOUT` (default 120 s, `0` = wait forever) bounds the wait, `CDTK_NO_LOCK=1` opts out.
Automation that needs several commands should call them **in series**, not with `&`. Real parallelism
requires a different loopback source address per session.

**The loopback answers RPPairing but there is still no listener.**
`remoted` closed it: dual-identity re-attach, lock-screen suspend, or an evicted concurrent session.
Unlocking, rebooting and reconnecting the proxy do not restore it — replugging USB once does.

**Pair-Verify passes but `createListener` returns 0 bytes — the pairing record is stale.**
Changing the **lock screen passcode** (or restoring / re-pairing) drops every host that was registered under the
other passcode state. The old record still signs, so steps 1–5 of `cdtk-doctor` stay green and only the real tunnel
fails, with `0 bytes read on a total of 9 expected bytes`. Export a fresh record and confirm the identity actually
changed before suspecting the loopback; `references/PAIRING_GUIDE.md` has the details.

**Handshake identity.**
`remoted` remembers each peer's handshake UUID; a different UUID triggers re-attach, which closes
every listener that peer advertised. Both Pair-Verify and the RSD handshake therefore present the
pairing record's `identifier`. `CDTK_HOST_UUID` overrides it, `CDTK_DEBUG=1` prints what is used, and
`cdtk-doctor` step 5 fails if the two disagree.

**`cdtk-ctrl launch <the host app's own bundle id>` kills the host.**
`launch` defaults to `kill_existing=True`: it terminates the target before starting it, so launching
the app that runs this toolchain is suicide (PID changes, no `.ips`). Use `--no-kill` to only activate.

**Does a finished command keep the tunnel open?**
No. Each command is its own process; the RSD session and the Node child are released on exit (no
leftover process, no listening port one second later). A session killed with `timeout`/SIGKILL leaves
a `cdtk_*` directory containing `relay.sock`; `cdtk-doctor` sweeps those older than a day whose pid is
gone (`--no-sweep` skips it). The port cache is kept by design.

## Environment variables

| Variable | Effect |
| --- | --- |
| `CDTK_PAIRING_FILE` | Explicit pairing record (skips the search) |
| `CDTK_RSD_HOST` / `CDTK_RSD_PORT` | Loopback address / pin the control port |
| `CDTK_RSD_SCAN=0`, `CDTK_RSD_SCAN_RANGE`, `CDTK_SCAN_BUDGET` | Port discovery tuning |
| `CDTK_RSD_PORT_CACHE` | Where the discovered port is cached |
| `CDTK_HOST_UUID` | Override the handshake identity |
| `CDTK_LOCK_TIMEOUT` / `CDTK_LOCK_FILE` / `CDTK_NO_LOCK=1` | Session lock |
| `CDTK_NODE_PROXY` | Explicit `tls_psk_proxy.js` path |
| `CDTK_SIGN_CERT` / `CDTK_SIGN_PROV` / `CDTK_SIGN_PASS` | Signing assets for `cdtk-install` |
| `CDTK_DEBUG=1` | Debug output (handshake UUID, port resolution) |

## Testing without a device

```bash
python3 tests/test_cdtk_ctrl.py   # coordinate conversion: 8 cases, no device, no pymobiledevice3
sh tests/smoke.sh                 # guards docs-vs-code drift and the session lock
```

## Notes and limits

- Verified on iPhone 14 / iOS 27.3 with Minis 1.16. Other versions are untested; iOS 17.x is
  experimental (some builds only listen on IPv6 link-local).
- `cdtk-install` needs signing assets (`--cert`, `--prov`, `--password` or `CDTK_SIGN_*`). Unsigned
  third-party IPAs can usually be installed with a forced re-sign; App Store IPAs cannot.
- `cdtk-fs` and `cdtk-inspect` can read credentials a site or app stores. Read only what the task
  needs, and never print tokens or cookies into the transcript.
- The toolchain drives Apple-private services. It works today on the versions above and may break on
  an OS update; `cdtk-doctor` is the first thing to run when it does.
