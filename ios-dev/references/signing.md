# signing.md — Compiling, signing, installing, renewing, and re-signing third-party IPAs

## Project (declarative project.yaml, no Xcode / Tuist needed)
Templates live in `assets/hello` (mixed ObjC+C) and `assets/swipe` (portrait paging demo). Copy `src/` and write a `project.yaml`:
```yaml
name: Hello
display_name: Hello Pika
bundle_id: XTL-<team ID>.com.example.hello   # must match the profile's App ID
version: "1.0"
build: "1"
min_ios: "14.0"
sdk: ~/.ios-sdk/iPhoneOS26.5.sdk
sources: [src/*.m, src/*.c]
frameworks: [UIKit, Foundation]
cflags: ["-O1"]
pch: "#import <UIKit/UIKit.h>"          # precompiled header, 13–29× faster compiles
device_family: [1]
info: {UILaunchScreen: {}}
sign:
  mode: p12                              # adhoc | p12
  p12: ~/.ios-signer/keys/dev.p12
  password_env: IOSDEV_P12_PASS           # password comes from an env var, never the command line
  profile: ~/.ios-signer/keys/dev.mobileprovision
  udid: <phone UDID>                      # optional: pre-check that the device is in the profile
```
```sh
export IOSDEV_P12_PASS="$(cat ~/.ios-signer/keys/p12.pass)"
python3 mk.py <project dir> --check            # pre-flight only: expired / Bundle ID mismatch / device missing / password missing — blocked before signing
python3 mk.py <project dir> [--clean]          # build + sign + package IPA
python3 mk.py <project dir> --install          # then install over loopback and read back to verify
```

## SDK: iOS 26 by default
- If `project.yaml` has no `sdk`, `mk.py` picks the **highest version** in `~/.ios-sdk`; if there isn't one it tells you to run `python3 scripts/install_sdk.py` (installs `iPhoneOS26.5.sdk`, ~330 MB, from the third-party mirror xybp888/iOS-SDKs — not an official Apple source).
- What the 26 SDK buys you: the binary gets `LC_BUILD_VERSION.sdk=26.5` (`minos` stays at `min_ios`), so you can use iOS 26 APIs such as `UIGlassEffect` / `UIGlassContainerEffect` / `cornerConfiguration` directly (**no** `NSClassFromString` needed), and the system renders appearance according to the newer SDK.
- The 26 SDK's UIKit headers reference `<UIUtilities/UIDefines.h>` under `System/Library/SubFrameworks`; `mk.py` already adds the `-F` for it.
- When using APIs that only exist in iOS 26 with a `min_ios` below 26, guard them with `@available(iOS 26.0, *)`/`if (@available(iOS 26.0, *))`, or older systems will crash.
- Glass in practice: use `UIGlassEffect` + `cornerConfiguration = capsuleConfiguration` instead of hand-drawing `cornerRadius`/`clipsToBounds`/shadows/strokes; multiple glass elements only merge when placed in a `UIGlassContainerEffect` visual effect view.
- To pin a specific version, write `sdk: ~/.ios-sdk/iPhoneOS16.5.sdk` in the yaml.

## Performance (measured, 6-core iSH)
- Without PCH: 6–11 s per file (all of it parsing UIKit headers); 31 files serially take 351 s.
- With PCH: 0.26 s per file, 31 files in parallel in 12 s; **an incremental change to one file takes about 3 s**.
- `mk.py` uses `-Wno-everything` by default and swallows every warning, so **"it compiles" does not mean it works** — also run `clang -Wall -Wextra -fsyntax-only` to check.

## Language limits
- iSH on the phone can only compile **ObjC and C** (Alpine has no Swift and no aarch64-musl host toolchain). Swift requires the swift.org toolchain on a Mac/Linux plus an SDK extracted from Xcode.xip (xtool's approach), with the output copied back for signing and installing.
- The iOS 26.5 SDK is the default (installed by `install_sdk.py`, no `.swiftmodule`); there is no actool/ibtool, so icons/Storyboards/Asset Catalogs are unsupported.

## Signing notes
- `rcodesign` takes `--p12-file` + `--p12-password-file` (**it cannot read from `/dev/stdin`** — it reports "No such file"); mk.py uses a 0600 temp file and deletes it afterwards.
- entitlements should contain only the minimum the profile allows: `application-identifier = <team ID>.<bundle_id>`, `com.apple.developer.team-identifier`, `get-task-allow` (plus `keychain-access-groups` for wildcard profiles). Extra entries still install but the app is refused at launch.
- **On iSH, `shutil.copy2` fails on `utime`** (FileNotFoundError), so use `copyfile` for file copies.
- Free-account profiles last **7 days**; `doctor.py` and `mk.py --check` warn when fewer than 14 days remain.

## Installing
```sh
export IOSDEV_PAIRING_FILE=~/.cdtk/pairing/<name>.plist      # the old name CDTK_PAIRING_FILE is still supported
python3 scripts/install_ipa.py <signed.ipa>
```
- Install with `install_ipa.py`, which calls pymobiledevice3's `install_from_local`. **Do not** use `InstallationProxyService.install()` from older tutorials — that method no longer exists in 11.x (you get an `AttributeError`).
- **Always read back after installing**: `get_apps(bundle_identifiers=[…])` to verify the name, version, and `SignerIdentity`; "returned no exception" does not mean it installed (`mk.py --install` already reads back automatically).
- Only one app per Bundle ID: a new app **overwrites** the old one.
- Launch and liveness check: after installing, tap it open on the phone; to script it, you can use pymobiledevice3's `DvtSecureSocketProxyService`/`ProcessControl` inside a `session.py` session to launch it and check whether the process is still alive (there is no built-in script — **we have not wrapped or validated this step as a general workflow**). Crash logs are under Settings › Privacy & Security › Analytics & Improvements › Analytics Data.
- Touch injection **does not work** under a userspace tunnel (`local_address is unavailable over an in-process (userspace) tunnel`), so you cannot script taps/swipes for UI verification.

## Bring your own p12 (the paid-account path)

**Do not log in to an Apple ID with a paid developer account in this skill** (`gsa.py` / `devsvc.py` refuse by default when they detect a paid team; see the risk notes at the top of `account.md`).
A paid account only needs two things prepared by you, plus one password environment variable:

1. **p12** (certificate + private key): create a development certificate in Xcode (Settings → Accounts → Manage Certificates) or on developer.apple.com, export it from the keychain as `.p12`, and set a password during export.
2. **Provisioning profile** (`.mobileprovision`): on developer.apple.com → Profiles create an iOS App Development profile, selecting the App ID, certificate, and your devices. A wildcard App ID (`<team ID>.*`) can sign any Bundle ID; for paid accounts do **not** add the `XTL-` prefix used for free accounts.

Copy them to the phone (with tight permissions), set the password variable, and fill in `project.yaml`:
```sh
mkdir -p ~/.ios-signer/keys && chmod 700 ~/.ios-signer ~/.ios-signer/keys
# copy my.p12 / my.mobileprovision there (not via cloud drives or chat logs), then:
chmod 600 ~/.ios-signer/keys/my.p12 ~/.ios-signer/keys/my.mobileprovision
export IOSDEV_P12_PASS='<p12 password>'       # env var only; never write it to a file or command line
```
```yaml
bundle_id: com.yourcompany.hello           # must match the App ID in the profile (wildcards are fine)
sign:
  mode: p12
  p12: ~/.ios-signer/keys/my.p12
  profile: ~/.ios-signer/keys/my.mobileprovision
  udid: <phone UDID>                        # optional: pre-check that the device is in the profile
```
```sh
python3 mk.py <project dir> --check    # pre-flight first: expired / Bundle ID mismatch / device missing / password missing — blocked before signing
python3 mk.py <project dir> --install  # build + sign + install + read back
```

**The pitfall you will most likely hit: the p12 format.** `rcodesign` cannot read the encryption OpenSSL uses by default in newer versions (AES+PBKDF2), and it reports
`incorrect password given when decrypting PFX data`, **even though the password is correct**. Convert it with the old algorithm (verified: `rcodesign sign` failed before conversion and succeeded after):
```sh
openssl pkcs12 -in my.p12 -nodes -out /tmp/all.pem            # prompts for the p12 password
openssl pkcs12 -export -legacy -in /tmp/all.pem -out my.legacy.p12   # set a password again (can be the same)
shred -u /tmp/all.pem 2>/dev/null || rm -f /tmp/all.pem        # the intermediate file holds a plaintext private key — delete it immediately
```
p12 files exported from the macOS keychain are usually already in the legacy format and work as-is; ones exported by newer openssl/Xcode may need conversion.

**Limitations of the paid path (stated honestly):** only the **signing half** of "bring your own p12 + profile → sign → install" has been verified
(we validated `mk.py`'s pre-flight and signing using a p12 and profile we generated ourselves). **It has not been tested with a real paid-account certificate.**
Profile validity is one year rather than 7 days, and renewal is just re-downloading a fresh profile from developer.apple.com to replace the file.

## Renewal (free accounts every 7 days; paid accounts yearly, see the previous section)
Before the profile expires: `devsvc.py create-profile <team> <appIdId> <certId> ~/.ios-signer/keys/dev.mobileprovision --yes` (same App ID, same certificate), then `mk.py --install` to re-sign and reinstall. The login session can be reused with `gsa.py --reuse`; the token lasts about a year.
(Note: the old profile needs to be replaced first; if Apple complains about a duplicate name, follow its prompts. Revoking/deleting counts as an irreversible operation — ask the user first.)

## Re-signing a third-party IPA (e.g. StikPair)
1. Unpack `Payload/X.app`, use `PlistBuddy` to change `CFBundleIdentifier` to your `XTL-…`, and if `BGTaskSchedulerPermittedIdentifiers` exists change it too (code commonly builds it dynamically as `bundleId + ".pairing"`).
2. Drop in `embedded.mobileprovision`, generate minimal entitlements, then `rcodesign sign --p12-file … --p12-password-file … --entitlements-xml-file … X.app`.
3. Verify: `rcodesign print-signature-info`; package with `zip -qry`; install with `install_ipa.py`; read back with `get_apps`.
4. Mind the license (StikPair is MIT non-commercial — personal use only).
5. If there's a ready keychain certificate on a Mac, `codesign --sign <SHA1> --entitlements ent.plist` also works, **but if the user asked you not to borrow the Mac, do not touch that Mac's keychain/certificates/profiles**.

## Other platform differences (Android/Windows)
For cross-platform conventions beyond `references/loopback.md`: the `minis-bonjour` interface is the same on all three platforms, but iOS is constrained by `NSBonjourServices` and the multicast entitlement, while Android/Windows are not (see the MinisApp repo's `src/shared/cli/bonjour.md`).

## Signing with a third-party distribution certificate (Ad Hoc / enterprise)

Common with purchased signing services; the bundle usually contains `cert file.p12` + `profile.mobileprovision` + `password.txt`.

```sh
# 1) See what type the profile really is, which devices it is bound to, and what the App ID is
openssl smime -inform DER -verify -noverify -in profile.mobileprovision \
  | python3 -c 'import plistlib,sys; p=plistlib.loads(sys.stdin.buffer.read()); \
print(p["Name"], p["TeamIdentifier"], p["Entitlements"]["application-identifier"], \
len(p.get("ProvisionedDevices") or []), p["ExpirationDate"], p["Entitlements"].get("get-task-allow"))'
```

**Several pitfalls you will hit**

| Symptom | Cause / fix |
| --- | --- |
| `Mac verify error: invalid password?` | `password.txt` often includes the label along with the value (contents `password:1`, real password `1`); inspect the raw bytes of the file before retrying |
| `rcodesign 0.29` cannot read the p12 | Usually PBES2 (AES-256/PBKDF2). `mk.py` now converts to the old format automatically before signing; for manual conversion see above |
| Install fails with `ApplicationVerificationFailed` / installs but won't launch | `bundle_id` must **equal** the profile's App ID (distribution certificates almost never allow wildcards). The `XTL-` prefix is free-account-only — do not mix them |
| Only one device can install | An Ad Hoc profile's `ProvisionedDevices` is a fixed list; switching devices means downloading a new profile |
| `get-task-allow = false` | Normal for distribution/Ad Hoc builds: no debugging, but it installs and runs |

**Multiple identities for one project**: copy `project.yaml` (e.g. `project-paid.yaml`), change `bundle_id` and `sign.*`, then build with:

```sh
python3 scripts/mk.py <project dir> --config project-paid.yaml --clean --install
```

Without `--config` it still reads `project.yaml`. The two identities install as **two separate apps** (different Bundle IDs) and do not share data/Cookies.
