# Pairing Record Guide

**English | [中文](PAIRING_GUIDE_zh.md)**

The RSD tunnel authenticates with a RemotePairing record (`.plist`) over SRP / TLS. Treat that file as a device
credential.

---

## Format

`load_pairing()` accepts three top-level keys and skips any file missing one:

- `identifier` — pairing ID, also used as the RSD handshake UUID
- `private_key` — Ed25519 private key
- `public_key` — Ed25519 public key

Check a candidate file:

```bash
python3 -c "import plistlib;print(sorted(plistlib.load(open('pairing.plist','rb'))))"
```

---

## Getting one

Enable Developer Mode on the phone, pair with either app below, then export the record:

- **StikPair** — pair, then export the `.plist` from the app
- **wloc** — reported to export one too; not reproduced here

The exported file should contain the three keys above. Other ways (for example `pymobiledevice3 remote pair` on a
computer) are not verified by this repository — try them yourself if you need to.

> A `lockdown` record (`/var/db/lockdown/<UDID>.plist`) is not a pairing record: it carries `HostCertificate` /
> `HostPrivateKey` / `RootCertificate` and none of the three keys above.

### When a record goes stale

Changing the **lock screen passcode** is enough to invalidate it. The device drops every host that was registered
while the passcode state was different, so the old record still signs correctly but no longer derives a session key.
Observed on iOS 27.3: a record exported before a passcode was set failed afterwards with

```
cdtk-doctor step 6: Pair-Verify passed, but the device tears down every encrypted request (0 bytes)
cdtk-install list:  0 bytes read on a total of 9 expected bytes
```

Pair-Verify only checks the host signature, so a stale record passes steps 1–5 and fails at `createListener`.
Export a fresh record after any passcode change (and after restore / re-pair), then confirm the identity really
changed before blaming the loopback:

```bash
python3 -c "import plistlib;print(plistlib.load(open('/root/.cdtk/pairing/rp_pairing_file.plist','rb'))['identifier'])"
```

The `identifier` is a stable UUID, not the device UDID. If the new export carries a different one, that is the
proof the old record was dead — keep a copy of it aside and install the new file at `0600`.


---

## Where it is looked up

`find_pairing_file()` searches in this order:

1. the file named by `CDTK_PAIRING_FILE` (recommended)
2. `/root/.cdtk/pairing/*.plist`
3. `/var/minis/workspace/cdtk/*.plist`
4. the current working directory, only when `CDTK_ALLOW_CWD_PAIRING=1`

Entry 3 is a directory shared by every session inside Minis (`0755`); a key stored there is readable by other sessions.
Prefer 1 or 2, and keep the file at `0600`.

---

## Permissions

- `0600`: used as is;
- too open (e.g. `0644`): tightened to `0600` when `chmod` works;
- filesystem ignores `chmod`: copied to `/root/.cdtk/pairing/` and locked to `0600`.

---

## Security

- The record holds the device's signing key; anyone with the file has developer-level debug access. Never commit it or
  upload it anywhere.
- CDTK never prints the private key or the PSK. `cdtk-install --password` does pass the **certificate** password (not the
  pairing key) to `zsign` on the command line, so it can show up in `ps` for a moment.
- `cdtk-doctor` masks the device identifier by default; `--show-udid` prints it in full. When pasting its output into an
  issue, drop section 3 anyway.
