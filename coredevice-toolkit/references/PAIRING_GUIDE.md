# Device Pairing Record Guide & Security Specification

**[English](PAIRING_GUIDE.md)** | **[中文说明](PAIRING_GUIDE_zh.md)**

Connecting to the CoreDevice RSD tunnel requires a valid remote pairing record
(`.plist`) to authenticate via Apple's RemotePairing SRP/TLS handshakes.

---

## ⚠️ Important Security Warning

> **Pairing records contain highly sensitive device credentials**:
> A pairing file contains the device's **Ed25519 private signing key** and pairing tokens. Anyone with access to this file possesses developer-level debugging access to the device.
>
> - **Never publish publicly**: Never upload your `.plist` to GitHub, public cloud storage, or untrusted sync providers;
> - **Strict Permissions Required**: Always set permissions to owner read/write only:
>   ```bash
>   chmod 600 /path/to/pairing.plist
>   ```
> - **Session Protection**: CDTK does not log pairing private keys or PSKs. Note that
>   `cdtk-install --password` is passed to `zsign` on its command line, so the
>   certificate password (not the pairing key) may briefly appear in `ps`.

---

## Required Format

CDTK's `load_pairing()` reads exactly three top-level keys:

```text
identifier   (string)
private_key  (bytes / data)
public_key   (bytes / data)
```

A record missing any of these is skipped by `find_pairing_file()`.

You can inspect a candidate file with:

```bash
python3 -c "import plistlib;print(sorted(plistlib.load(open('pairing.plist','rb')).keys()))"
```

---

## How to Obtain a Pairing Record (Choose One)

### Method 1: SideStore / SideInstaller (On-Device)
If **SideStore** or **SideInstaller** is installed on your device:
1. Open the app and generate a local pairing file;
2. Export the generated `pairing.plist`;
3. Place it in a supported CDTK search path (see below).

This is the easiest route and produces the correct format.

---

### Method 2: Generate on a Computer with `pymobiledevice3`
Connect the iPhone by USB, then on the computer:

```bash
pip install pymobiledevice3
pymobiledevice3 remote pair
```

Copy the generated `.plist` to the device. Check that it contains
`identifier`, `private_key`, and `public_key` before using it.

---

### Not Supported: macOS `lockdown` records
Files under `/var/db/lockdown/<UDID>.plist` are **lockdown** records
(`HostCertificate`, `HostPrivateKey`, `RootCertificate`, ...). They do **not**
contain `identifier` / `private_key` / `public_key`, so CDTK cannot use them.
Do not copy them into the pairing directory.

---

## Safe Storage Paths & Discovery Priority

CDTK searches in this order:

1. **Explicit CLI argument** (e.g. `cdtk-install --pairing /path/to/pairing.plist`);
2. **Environment variable `CDTK_PAIRING_FILE`**;
3. **Private secure sandbox**: `/root/.cdtk/pairing/*.plist`;
4. **Dedicated workspace folder**: `/var/minis/workspace/cdtk/*.plist`.

The current working directory is **not** searched by default. Set
`CDTK_ALLOW_CWD_PAIRING=1` if you deliberately keep the record there.

> ⚠️ **Permission Requirement**:
> If a pairing file has loose permissions (`0644`), CDTK tries to tighten it to
> `0600`. If the underlying filesystem ignores `chmod` (some external mounts),
> the record is copied into `/root/.cdtk/pairing/` with `0600`.
