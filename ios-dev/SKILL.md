---
name: ios-dev
description: >
  Build, sign and install iOS apps entirely on a phone running Minis (iSH) -- no Mac, no Xcode.
  Compile ObjC/C with clang+lld from a declarative project.yaml, package an IPA, obtain a
  development certificate and provisioning profile with a free Apple ID (or bring your own p12
  for a paid account), sign, then install onto your own iPhone over a local loopback VPN
  (Surge or LocalDevVPN) using a RemotePairing file, and read the app list back to verify.
  Use when the user wants to build an IPA on the phone, sideload or re-sign an app, get a free
  7-day development certificate, renew an expiring profile, put a Hello World on their own
  device, or debug "won't install", wrong verification code, 409, -80045, -21669 or a
  loopback that does not work. For what to do on the device after install (logs, battery,
  crash reports, SpringBoard, sandbox files) use the coredevice-toolkit skill instead.
---

# ios-dev — On-device iOS build → sign → install

Everything runs on the phone (iSH), with **no dependency on Xcode and no dependency on a computer** (the one exception is obtaining the pairing file for the first time — see below).

## Prerequisites (read this before deciding to use the skill)
| Prerequisite | Notes |
|---|---|
| **Runtime environment** | Minis' iSH (Alpine, aarch64). Most scripts also run on ordinary Linux, but **loopback handshakes, `minis-bonjour`, and "phone pairing with itself" only make sense on a phone** |
| **Target device** | **iOS 17+ (RemotePairing)**; tested on iPhone19,2 / iOS 27.0.1. Anything below iOS 18 is **untested** |
| **Account** | **Free Apple ID**: the login flow in this skill can obtain a certificate automatically (7-day profile, restricted App ID). **Paid developer account**: **logging in is not supported** — bring your own p12 + provisioning profile, set `IOSDEV_P12_PASS`, and sign directly with `mk.py` (see `references/signing.md`, "Bring your own p12"). Only the signing half of the paid path has been verified; it has not been tested with a real paid certificate |
| **Network** | The phone **must be on Wi-Fi**; a loopback VPN is required (Surge ≥5.23.0 or LocalDevVPN). Only one VPN can be active at a time |
| **Compilable languages** | ObjC / C only. No Swift, no Storyboard/Asset Catalog compiler |
| **Minis-specific command** | Route 2 in `references/pairing.md` uses `minis-bonjour` (requires a Minis build with the bridge); the other scripts do not depend on it |

## Risks and disclaimer
- The account section (`gsa.py`/`devsvc.py`/`anisette.py`) talks to **Apple's private endpoints** (reverse-engineered from xtool). **Apple may change them at any time, breaking this**; it also depends on third-party public Anisette services that may be unavailable or rate-limited.
- **Do not log in with a paid developer account in this skill**: `devsvc.py` refuses by default when it detects a paid team (`--i-know-the-risk` overrides — at your own risk). For paid accounts, bring your own p12 and stay away from the private endpoints.
- Frequent or failed logins may trigger Apple's rate limiting or risk controls (we have observed `-22421` and `-80045` in practice). **Use an account you don't mind getting throttled; do not use your main account; run only one complete pass at a time.**
- This skill **creates** certificates, App IDs, provisioning profiles, and device records on your Apple account (every write is previewed first and only sent with `--yes`). Device records on a free account **cannot be freely deleted**.
- Credentials stay on-device in `~/.ios-signer/` (mode 600); **do not sync or upload this directory, the pairing file, or the p12**.
- The author is not responsible for account restrictions, device issues, data loss, or similar consequences. Using this skill means you understand these risks. See `LICENSE` and `THIRD_PARTY.md` for licensing and third-party sources.

```
compile (clang+lld) → package IPA → sign (dev cert + profile) → install via local loopback (pymobiledevice3) → read back and verify
                                   ▲                                       ▲
              Apple ID → Xcode token → developer services        pairing file (RemotePairing)
```

## First step: self-check
```sh
python3 scripts/doctor.py            # toolchain/deps/SDK/p12/token/profile/Surge/pairing file, read-only
python3 scripts/doctor.py --device   # then run one real on-device loopback handshake
```
Every item reports ✅/⚠️/❌ with a fix hint. **If anything later goes wrong, run this first.**

## Workflow and the matching documents
| # | Stage | What to do | Details |
|---|---|---|---|
| 0 | Environment | `apk add clang lld llvm19 openssl zip nodejs py3-yaml py3-cryptography`; `pip install websockets 'pymobiledevice3>=11.34' pmd-pytcp`; `rcodesign`; iOS SDK: `python3 scripts/install_sdk.py` installs `iPhoneOS26.5.sdk` into `~/.ios-sdk/` in one shot (26 is the default, giving access to newer APIs such as UIGlassEffect) | hints from `doctor.py` |
| 1 | Loopback | **Pick one** VPN that routes `10.7.0.1` back to the phone itself: Surge ≥5.23.0 (import `references/CoreDevice-Loopback.sgmodule`) or LocalDevVPN (free on the App Store), etc.; **phone on Wi-Fi**, Developer Mode enabled | `references/loopback.md` |
| 2 | Pairing file | Obtain a RemotePairing plist (`~/.cdtk/pairing/*.plist`, 600, `IOSDEV_PAIRING_FILE`) | `references/pairing.md` |
| 3 | Account → certificate (**free Apple ID only**; skip for paid accounts, bring your own p12 — see `signing.md`) | `gsa.py` login → `devsvc.py` list/register device/generate key+CSR/request certificate/create App ID/generate profile/assemble p12 | `references/account.md` |
| 4 | Build, sign, install | `mk.py <project> --check` → `mk.py <project> --install`, which pre-flights, signs, installs, and reads back automatically | `references/signing.md` |
| 5 | Renewal / re-signing | Free-account profiles last **7 days**; re-sign third-party IPAs | `references/signing.md` |

Shortest path (when you already have a p12 / profile / pairing file):
```sh
export IOSDEV_P12_PASS="$(cat ~/.ios-signer/keys/p12.pass)" IOSDEV_PAIRING_FILE=~/.cdtk/pairing/<name>.plist   # the old name CDTK_PAIRING_FILE is still supported
cp -r assets/hello /tmp/myapp && $EDITOR /tmp/myapp/project.yaml   # see the project.yaml template in signing.md
python3 scripts/mk.py /tmp/myapp --install
```
Sample projects: `assets/hello` (mixed ObjC+C) and `assets/swipe` (portrait paging, UIScrollView paging + double-tap to like, **the content is a simulated gradient — no real video**).

## Key facts (so you don't step on the same rakes)
- **Surge is not the only loopback option**: NetworkExtension-based apps such as LocalDevVPN work too. The shared constraint is that the **phone must be on Wi-Fi** (49152 is closed on cellular) and only one VPN may run at a time. **Only the Surge approach has been verified on-device here**; LocalDevVPN's source was read but never tested. Surge **<5.23.0 silently drops `[IP Rewrite]`** (symptom: any port connects in 1 ms but no data flows).
- **The pairing file** must be in RemotePairing format (`identifier/private_key/public_key`); legacy lockdown records do not work. **The most reliable way to get one is to borrow a Mac and run idevice's `pair_host`**; it can also be installed on the phone (`apk add pair-host`, source in `references/pairing.md` under "Obtaining pair_host"), but the mDNS broadcast it emits itself gets blocked by iOS (missing multicast entitlement), so it needs `minis-bonjour` to publish. StikPair **has never succeeded** on this device's iOS 27.0.1.
- **2FA has to be routed by channel**: `secondaryAuth` means SMS via `phone/securitycode`, not `validateCode`. This once caused a run of 409/`-21669`.
- **`-80045`**: GSA init/complete use the Windows client-info; the 2FA endpoints use the Mac one.
- **Developer services responses are gzip**, so you have to decompress them yourself.
- **The p12 must be exported with `-legacy`**, otherwise rcodesign wrongly reports a "wrong password". `rcodesign` cannot read the password from `/dev/stdin`.
- **Free accounts**: certificates last about 1 year, **profiles only 7 days**; App IDs are globally unique, so use `XTL-<team ID>.…` for the project `bundle_id`; **creating a new certificate does not require revoking the old one**; the same App ID can be reused across different apps.
- **You do not need to install coredevice-toolkit**: the handshake layer is implemented here (`rppairing.py` protocol + `session.py` session + `psk_bridge.js` TLS-PSK bridge). Install with `scripts/install_ipa.py` (do not use cdtk's `install` subcommand — the `.install()` it calls no longer exists in pymobiledevice3 11.x); **after installing you must read back with `get_apps`**.
- **Two protocol constraints can only be verified on a real device**: Pair-Verify's M1 requires `startNewSession=true` and M3 requires `false`; get them backwards and the device just drops the connection. `rppairing.py`'s offline self-test asserts this.
- On iSH: `shutil.copy2` fails (use `copyfile`); `cp` occasionally reports "file replaced" (use Python reads/writes); `pgrep -x` cannot see processes (use `ps | grep '[.]/x'`).
- The phone can only compile **ObjC/C**, no Swift. `mk.py` swallows all warnings by default, so "it compiles" ≠ "it's fine".

## Safety and irreversible operations (mandatory)
- Passwords/verification codes go only through environment variables and local 600 files — **never print them, never put them on a command line, never log them**. The pairing file and private keys contain secrets: do not upload or sync them.
- **Preview writes first; only send with `--yes`**; `devsvc.py`'s allowlist only permits POST devices/certificates/bundleIds/profiles plus "delete profile" — **there is no revoke certificate/delete device/delete App ID**.
- **Revoking a certificate is irreversible** (it invalidates other devices signed with that certificate). Only do it after the user confirms each one individually, and first confirm **which account you are operating on** (an `asc` API Key belongs to a team, while the `APPLE_ID` env var may be a different account — we have mixed these up before).
- Installing **overwrites an existing app with the same Bundle ID**; explain this before touching the user's primary phone.
- When the user explicitly says "don't use machine X's keychain/certificates/profiles", leave them alone.
- On failure, do not retry the login repeatedly (it causes `-22421` throttling); run only one complete pass at a time.
- Before concluding "the outside can/cannot see it", first confirm **whether the phone and the peer are on the same subnet and whether the phone is on Wi-Fi**.

## Verified / unverified (an honest list)
**Tested on a real device**: compile → p12 signing → install → read back; Surge loopback; Apple ID login (SMS 2FA) → Xcode token; registering a device, creating certificates, App IDs, profiles; loopback handshake and `installation_proxy`; re-signing and installing StikPair; generating a pairing file with `pair_host` on a Mac.
**Only tested locally/with fake data, never sent to a real account**: `devsvc.py renew-profile` (delete the old profile, then create).
**Unverified/never succeeded**: LocalDevVPN/Clash Mi as the loopback (only source/README read); the phone's Settings page discovering this host's broadcast "Pair with …" entry (StikPair/bridge approach); scripted touch injection (unavailable under a userspace tunnel); Swift builds; equivalent flows on Android/Windows.
**Versions at verification time** (no guarantees across versions): iOS 27.0.1 · Surge 5.23.0 · pymobiledevice3 11.35.0 · pmd-pytcp 0.3.8 · rcodesign 0.29.0 · clang 19.1.4 · Node 22 · Python 3.12 · SDK `iPhoneOS26.5.sdk` (AppConnect tested) / 16.5 (early Hello, Swipe) · Alpine/iSH aarch64.
**Out of our control**: Apple may change private endpoints at any time; public Anisette servers are occasionally unavailable; Apple automatically reclaims old App IDs on free accounts (in practice, 2 of SideStore's disappeared).

## Relationship to coredevice-toolkit
The two skills are different things that share one mechanism (the 10.7.0.1 loopback and the RSD handshake).
**ios-dev** covers the build chain: compile, package, get a certificate, sign, install, read back.
**coredevice-toolkit** covers working with the device once it is reachable: process control, logs, battery,
crash reports, SpringBoard layout, app-sandbox files. Use ios-dev to produce and install the app, then
coredevice-toolkit to manage the device. They do not need each other: ios-dev ships its own handshake layer
(`rppairing.py`, `session.py`, `psk_bridge.js`), so you can install either one alone. If you have both, they can share one pairing file: both read the
default `~/.cdtk/pairing/*.plist` location, and both honour `CDTK_PAIRING_FILE` (ios-dev also accepts
`IOSDEV_PAIRING_FILE`, which coredevice-toolkit ignores).

## Credits and licensing
Written for this skill and MIT-licensed (`LICENSE`). It was built by studying the source of xtool, idevice, StikPair and LocalDevVPN (no code copied; see `THIRD_PARTY.md` for what each was used for and under which licence), and it needs pymobiledevice3 and pmd-pytcp (GPL-3.0) installed by the user.

## Layout
```
ios-dev/
├── SKILL.md  LICENSE  THIRD_PARTY.md
├── scripts/   doctor.py  mk.py  profile.py  gsa.py  anisette.py  srp_client.py  devsvc.py
│              install_ipa.py  session.py  rppairing.py  psk_bridge.js
│              pairing_import.py  pair_via_bonjour.py  install_sdk.py  AppleRoot.pem
├── references/  loopback.md  pairing.md  account.md  signing.md  CoreDevice-Loopback.sgmodule
└── assets/    hello/src  swipe/src
```
