# Third-party software and references

This skill's own code (scripts/, references/, assets/) is MIT-licensed (see LICENSE).
It stands on the work of the projects listed below; thank you to their authors.
Nothing below is copied into this directory. Only projects whose **source code** we read or used are listed under
"Reference"; software that is merely run or documentation that was merely read is not. "Reference" means we read the source to learn
a protocol or behaviour and then wrote our own implementation.

## Reference only (no code copied)

| Project | License | What we used it for |
|---|---|---|
| [xtool](https://github.com/xtool-org/xtool) — Copyright (c) 2024 Kabir Oberai | MIT | Read `Sources/XKit/GrandSlam`, `Sources/XKit/DeveloperServices` and `Sources/DeveloperAPI` to learn Apple's developer-services flow (GrandSlam login, certificates, App IDs, provisioning profiles). `gsa.py`, `anisette.py`, `srp_client.py`, `devsvc.py` are independent Python implementations of that flow. |
| [idevice](https://github.com/jkcoxson/idevice) — Copyright 2026 Jackson Coxson | MIT | Read `idevice/src/remote_pairing/` (`responder.rs`, `rp_pairing_file.rs`, `peer_device.rs`) and `tools/src/pair_host.rs` to learn the RemotePairing wire protocol (Pair-Verify, createListener) and the pairing-file layout. `rppairing.py` implements it independently and was checked against a real device. The `pair-host` binary mentioned in `references/pairing.md` is distributed separately (see ish-pkgs) with idevice's license text. |
| [OpenMinis/MinisSkills `coredevice-toolkit`](https://github.com/OpenMinis/MinisSkills) | MIT | An earlier version of this skill used its session code. It has been replaced by `session.py`, `rppairing.py` and `psk_bridge.js`; no file from it remains here. |
| [StikPair](https://github.com/StikDebug/StikPair) — Copyright (c) 2026 StephenDev0 | **MIT, Non-Commercial** (its own LICENSE; GitHub shows "other") | Read to understand how an iOS app can host RemotePairing on the device itself (publishing the pairable-host service through the system mDNS responder, PIN display, background keep-alive). **No code was copied**; the licence forbids commercial use, so do not copy from it into a commercial product. We re-signed the upstream IPA once for on-device testing only. |
| [LocalDevVPN](https://github.com/SiamSadik/LocalDevVPN) (fork with a `/32` peer-route fix) | not declared | Read `PacketTunnelProvider.swift` to understand the `10.7.0.0` ↔ `10.7.0.1` address-rewrite loopback, so `references/loopback.md` can describe how other VPN apps achieve the same thing. No code copied. |

## Runtime dependencies (installed by the user, not distributed here)

| Package | License | Used by |
|---|---|---|
| [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) 11.x | **GPL-3.0-or-later** | `session.py` imports its tunnel/RSD classes; `install_ipa.py` imports `InstallationProxyService`. |
| [pmd-pytcp](https://github.com/ccie18643/PyTCP) 0.3.8 | **GPL-3.0-or-later** | Imported by pymobiledevice3 (user-space TCP/IP stack). |
| cryptography 44.x | Apache-2.0 OR BSD-3-Clause | `rppairing.py`, `gsa.py`, `srp_client.py` |
| websockets 16.x | BSD-3-Clause | `anisette.py` |
| PyYAML 6.x | MIT | `mk.py` |

**About the two GPL packages.** This skill does not include or modify their code; the user installs
them with pip and our scripts call their public API at run time. Whether calling a GPL library from
separately licensed scripts creates obligations is a question reasonable people answer differently,
and this is not legal advice. If you redistribute a bundle that *contains* these packages, or you
need a compliance statement, check with someone qualified. Everything else in this skill works
without them (they are only needed for the device-connection and install steps).

## Tools the scripts call (not distributed here)

clang / ld64.lld (LLVM, Apache-2.0 with LLVM exceptions), rcodesign ([apple-codesign](https://github.com/indygreg/apple-platform-rs), MPL-2.0),
openssl, Node.js (MIT), Surge or LocalDevVPN (the loopback VPN; their own terms).

## Data the scripts fetch at run time

- **iOS SDK**: `doctor.py` suggests cloning [theos/sdks](https://github.com/theos/sdks). We do not bundle
  or redistribute any Apple SDK; you are responsible for complying with the terms that apply to the
  SDK you use.
- **Apple Root CA** (`scripts/AppleRoot.pem`): Apple's public root certificate, included so TLS to
  `gsa.apple.com` can be verified on systems whose trust store lacks it. Its SHA-256 fingerprint is listed in `references/account.md` so you can check it against Apple's published value.
- **Anisette data**: `anisette.py` talks to a public V3 anisette server (default `https://ani.sidestore.io`,
  override with `ANISETTE_URL`). It is run by a third party, can be rate-limited or down, and sees
  that a login is happening (it does not see your password).
