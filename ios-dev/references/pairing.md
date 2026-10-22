# pairing.md — How to obtain a pairing file (RemotePairing plist)

A pairing file = the record containing the private key that the host receives after the phone records "some host identity's Ed25519 public key" in its trust list.
**The loopback is only the transport; it does not provide trust. Without the pairing file, Pair-Verify cannot succeed.** The file contains a private key: mode 600, never upload, sync, or paste it into chat.
It becomes invalid after the device is erased/reset or the computer is removed in Settings.

## Choose a route first (try them in order, move on when one fails)
```
Phone on iOS 27+ and connected to Wi-Fi?
 ├─ Yes → Route 1  StikPair (phone pairs with itself, zero computer)   ← preferred
 │        doesn't work (no "Pair with StikPair" in Settings)
 │        → Route 2  Publish via minis-bonjour (phone pairs with itself, no extra app)
 │               doesn't work
 │               → Route 3  Computer + iloader export, then import (verified fallback)
 └─ No (iOS <27) → Route 3 only (device-initiated pairing only exists in iOS 27)
```
**Whichever route you take, validate and import with the same command at the end** (see "Import and validation").

> Current status (measured on this iPhone, iOS 27.0.1): for routes 1 and 2 the **broadcast is emitted and discovered by the phone itself, but no "Pair with …" entry ever appears in Settings**, so neither has ever completed; the equivalent approach for route 3 (running idevice's `pair_host` on a Mac) **has succeeded**. So routes 1 and 2 are worth trying first (zero cost), but **don't count on them working** — keep route 3 as the fallback.

---
## Route 1: StikPair (phone pairs with itself)
- Source: `github.com/StikDebug/StikPair`, the official Release IPA (v1.2.0, 7.7 MB, no entitlements). **License is MIT non-commercial**: re-signing it for your own use is fine, but you cannot ship or distribute it as part of a product.
- **Install** (re-sign with this skill's signing flow; the Bundle ID must be changed to your team's):
  ```sh
  gh release download v1.2.0 -R StikDebug/StikPair -p StikPair.ipa -D /tmp/sp
  # unpack → change CFBundleIdentifier and BGTaskSchedulerPermittedIdentifiers[0]=<id>.pairing
  # → add embedded.mobileprovision → rcodesign sign (only the entitlements the profile allows) → zip → install_ipa.py
  ```
  See "Re-signing a third-party IPA" in `signing.md` for details. Note: **one profile is bound to one App ID**, so installing StikPair means either creating a dedicated App ID or reusing an existing one (which overwrites the app previously installed under it).
- **Usage** (combined from the README and issues; every one of these conditions is required):
  1. The phone is on **Wi-Fi** (not cellular); Developer Mode is enabled
  2. Open StikPair and **enable a background mode inside the app** (silent audio or background location; off by default — the author explicitly requires this in issue #6), and grant the "Local Network" prompt
  3. Tap **Pair iPhone or iPad** and **keep StikPair in the foreground**
  4. Go to **Settings › Privacy & Security › Developer Mode → [scroll down] → tap "Pair with StikPair"**
  5. Enter your **lock-screen passcode** first (issue #9: many people mistake this for the PIN), then the 6-digit PIN **shown in the Live Activity**
  6. Wait for the "Pairing complete" notification → go back to StikPair → **Export Pairing File**
- **Known issues**: the entry **comes and goes** (issue #3: one user saw it "one time in three"; the author says it "only appears while an mDNS/Bonjour broadcast is in progress"); some users also hit a tap that does nothing or a terminated connection. **Try several times, and each time cancel in StikPair first and tap Pair again to generate a new identity.**
- How it works (verified by reading the source): Rust only implements the protocol (TCP listener + SRP); when publishing it calls back into Swift and uses `NetService.publish` so the system mDNSResponder advertises on its behalf, so the multicast entitlement is **not** needed; the model is only defaulted to `Mac17,7` and idevice's source does not validate it.
- After you get the file: the export is `rp_pairing_file.plist`; copy it to the phone and then go through "Import and validation". **There are reports of StikPair exports occasionally failing to import into StikDebug (iPadOS 27.0)**, so always do the handshake validation — never just check that the file exists.

---
## Route 2: Publish via minis-bonjour (phone pairs with itself, no extra app)
**Why this is needed**: `pair_host` (the static Linux build) can run the protocol inside iSH, but the multicast it sends itself via mdns-sd is rejected by iOS (`EHOSTUNREACH`, missing multicast entitlement) — the log looks fine while the broadcast never leaves the phone. `minis-bonjour advertise` publishes on its behalf from Minis' app layer (Network.framework), which is not restricted.
```sh
python3 scripts/pair_via_bonjour.py --dry-run     # only check preconditions first (Wi-Fi, type declared, no leftovers in the bridge, Minis in foreground)
python3 scripts/pair_via_bonjour.py               # start pair_host → get port/TXT → advertise → wait for your pairing → validate and save
```
The script prints "now go to Settings › Privacy & Security › Developer Mode (scroll down) and look for Pair with <name>", and watches the log for the connection and the 6-digit PIN. The steps are the same as steps 4–5 of route 1.
**Hard requirements**
- `pair_host` binary: `apk add pair-host` (installs to `/usr/local/bin/pair_host`; obtaining it is described under "Obtaining pair_host" below)
- **The instance name must equal the identifier** (source `responder.rs`, around lines 89–94); all 7 TXT keys must be present: `name identifier authTag model flags ver minVer`
- **Publish immediately after the same start**: `pair_host` **regenerates the entire identity set on every run** (source comment: "regenerates them each run"), so `authTag` changes with it — after a restart you must re-publish and re-pair
- **Minis must be in the foreground**: in the background the system withdraws the broadcast (it resumes automatically when you come back)
- **Don't test your own broadcast with `resolve/connect`**: that makes pair_host receive an incomplete handshake and panic (`early eof`)
**Status**: the broadcast has been verified visible to `dns-sd -B/-L` on a Mac on the same subnet, with the TXT record matching byte for byte; **whether Settings lists it and whether the PIN flow can complete — has not worked on this device**.

---
## Route 3: Computer + iloader export, then import (the verified fallback)
Applies when: routes 1 and 2 show no entry; or the phone is not on iOS 27 (in which case pairing goes through the old USB lockdown flow).
**iloader** (`github.com/nab138/iloader`, v2.3.10; the only official download sources are this repo and iloader.app):
1. Install usbmuxd on the computer: **iTunes** on Windows, built into macOS, distro package on Linux (`apt install usbmuxd`, etc.)
2. Install the package for your platform from Releases (`iloader-darwin-universal.dmg`, `iloader-linux-{amd64,aarch64}.AppImage/.deb/.rpm`, a Windows installer)
3. **Connect the phone with a USB cable**, tap "Trust This Computer" on the phone, and enter the lock-screen passcode
4. Open iloader → sign in with your Apple ID → choose **Manage pairing files** (this can export to / place files into StikDebug, SideStore, and similar apps)
   - It places **both rppairing and lockdown** pairing files; **we only need the rppairing one** (containing `identifier/private_key/public_key`)
5. Transfer the rppairing `.plist` to the phone: AirDrop / Files app / iCloud / `scp` all work
6. Import and validate on the phone (next section)
**You don't have to use iloader**: you can run idevice's `pair_host` directly on a Mac (this is the approach that actually worked for us):
```sh
git clone https://github.com/jkcoxson/idevice && cd idevice
cargo run --release -p tools --bin pair_host -- --name Mac-Pair --out ~/new_phone.plist
# the phone and the Mac must be on the same subnet (mDNS does not cross subnets). The terminal prints the 6-digit PIN
# phone: Settings › Privacy & Security › Developer Mode (scroll down) › Pair with Mac-Pair → lock-screen passcode → PIN
```
(edition 2024 needs Rust ≥1.85. **The cargo 1.83 in iSH cannot build it**, so you must build on a Mac/Linux.)

---
## Import and validation (shared by all routes)
```sh
python3 scripts/pairing_import.py <source plist>                  # validate + chmod 600 + place at ~/.cdtk/pairing/new_phone.plist + real-device handshake
python3 scripts/pairing_import.py <source plist> --no-handshake   # validate and save only, when not on Wi-Fi
export IOSDEV_PAIRING_FILE=~/.cdtk/pairing/new_phone.plist   # the old name CDTK_PAIRING_FILE is still supported
python3 scripts/doctor.py --device                           # full loopback + handshake self-check
```
`pairing_import.py` will reject the file and explain why: legacy lockdown record, missing fields, `public_key`/`private_key` not exactly 32 bytes, or the public key not derived from the private key (corrupted/tampered file).

## File format (verified against idevice's `rp_pairing_file.rs`)
XML plist with a fixed key order and four keys:
| Key | Type | Source |
|---|---|---|
| `public_key` | Data 32B | The Ed25519 public key generated when the host starts |
| `private_key` | Data 32B | The corresponding private key (**the most sensitive field**) |
| `identifier` | String | Host identity, UUID **v3** (DNS namespace + host name) |
| `alt_irk` | Data 16B, **optional** | The **phone's** IRK, sent by the phone at pairing step M6 (not the host's own) |
- The file contains **no** device UDID, model, or phone public key; the phone-side trust record lives on the phone.
- `write_to_file` **does not set permissions**, so `chmod 600` it yourself (`pairing_import.py` already does).
- Legacy lockdown records (`HostID/SystemBUID/HostCertificate/EscrowBag`) **cannot** be used for the loopback handshake; what iloader/SideStore export is a combined "full" file whose RemotePairing part is usable.

## How the protocol works (why it's set up this way)
Starting with iOS 27, **the device initiates pairing**: ① the host advertises mDNS `_remotepairing-pairable-host._tcp`; ② the user taps "Pair with …" in Settings and the phone opens **plain TCP** to the resolved address and port; ③ roles flip — the phone becomes the rppairing host — then **SRP-6a** (password = the 6-digit PIN, username fixed as `Pair-Setup`, 3072-bit group, the PIN never goes over the network), followed by ChaCha20-Poly1305-encrypted exchange of the long-term Ed25519 public key/identifier/altIRK; ④ the host writes the file to disk.
**Only step ① uses multicast**; steps ②–④ are all TCP. So "bypassing multicast" just means letting the system mDNSResponder do the advertising (StikPair's NetService, our minis-bonjour).

## Obtaining pair_host (the apk is recommended; no need to build it yourself)
OpenMinis publishes prebuilt iSH (aarch64 musl static) packages at <https://github.com/OpenMinis/ish-pkgs>, **built from unmodified upstream `jkcoxson/idevice` sources** (MIT). Each package's `/usr/share/doc/<package>/PROVENANCE.txt` records the upstream tag, commit, and toolchain, with `modifications: NONE` meaning no patches were applied.
```sh
U=https://raw.githubusercontent.com/OpenMinis/ish-pkgs/main
wget -O /tmp/ish-pkgs.rsa.pub $U/ish-pkgs.rsa.pub
sha256sum /tmp/ish-pkgs.rsa.pub     # must be 2db5bb598e9b98596be896a43117d4614e8c07f243ba476eeee9d89679022fdd — stop if it differs
cp /tmp/ish-pkgs.rsa.pub /etc/apk/keys/ish-pkgs.rsa.pub
echo "$U" >> /etc/apk/repositories
apk update && apk add pair-host        # just pair_host (~0.85MB)
```
- Upgrade: `apk update && apk upgrade`; uninstall: `apk del pair-host`.
- `apk add idevice-tools` also installs `idevice_id/iproxy/pair_apple_tv`, but these need usbmuxd, which iSH does not have — `idevice_id` simply aborts — so they are **generally not needed**.
- What we actually tested: installing the package, running `--help`, pulling in dependencies, and a clean uninstall; we have **not** completed a real pairing on a device with it.

## Appendix: building pair_host yourself (when there is no apk repo or you need another version)
> `pkgs/idevice-tools/build.sh` in the `ish-pkgs` repo is the scripted version of this flow (pins the upstream tag, strips build-machine paths, generates PROVENANCE). The manual steps are below:
- **Native on a Mac**: `cargo build --release -p tools --bin pair_host`
- **Cross-compile a static Linux build on a Mac for the phone** (verified):
  ```sh
  brew install zig && rustup target add aarch64-unknown-linux-musl
  # write /tmp/zigcc/cc:#!/bin/sh \n exec zig cc -target aarch64-linux-musl "$@"   (chmod +x)
  export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER=/tmp/zigcc/cc CC_aarch64_unknown_linux_musl=/tmp/zigcc/cc
  export RUSTFLAGS="-C link-self-contained=no"      # otherwise Rust's bundled musl startup files collide with zig's and linking fails
  cargo build --release --target aarch64-unknown-linux-musl --bin pair_host
  ```
  The artifact is about 1.5 MB; copy it to the phone as `/root/idev-bin/pair_host` and `chmod +x` it.
- It cannot be built on the phone itself (Rust is too old).

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| No "Pair with …" in Settings | Wi-Fi not connected / broadcast not emitted / not kept alive / intermittent. First confirm the broadcast exists with `minis-bonjour browse _remotepairing-pairable-host._tcp`; then switch routes |
| mDNS outside (a Mac) cannot see the phone's broadcast | **First confirm the phone and the Mac are on the same LAN** (mDNS simply cannot cross networks, e.g. the phone is on another Wi-Fi or on cellular) |
| pair_host panics with `early eof` | Something made an incomplete connection to it (e.g. your own `resolve/connect`); restart pair_host and publish again |
| Pairing succeeds but the handshake fails | Developer Mode off / not on Wi-Fi / loopback VPN not running; see `loopback.md` |
| Settings asks for a "password" rather than a PIN | Normal: enter the lock-screen passcode first; the PIN is shown on the host side |
