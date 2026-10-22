# account.md — From Apple ID to a development certificate / provisioning profile (GrandSlam + developer services)

> ## ⚠️ Free Apple IDs only; do not take this path with a paid developer account
> This uses reverse-engineered **private endpoints** (the Xcode channel). Apple may change them at any time, and on free accounts we have hit both rate limiting (`-22421`) and outright rejection (`-80045`) in practice. **We do not support taking a paid account down this path**: if the account gets flagged by risk controls, the fallout is bigger than for a free account (we have no evidence of the specific consequences, and cannot rule them out).
> - **Paid accounts**: create the certificate and profile yourself, export the p12, set `IOSDEV_P12_PASS`, and sign directly with `mk.py` — **no login, no private endpoints**. Steps are in `signing.md`, "Bring your own p12 (paid accounts)". `devsvc.py` refuses by default when it detects a paid team and only proceeds with an explicit `--i-know-the-risk`.
> - **Free accounts**: this is the flow for them. Use an account you don't mind getting restricted; do not use your main account.
> Never put the password in a file or on a command line: read it only from the `APPLE_ID` / `APPLE_PASSWORD` environment variables and never print it. The login session and token live only in `~/.ios-signer/` (600).

## Flow overview
```
gsa.py  login (SRP + 2FA) ──► xcode_token.json + session.json
devsvc.py whoami          ──► account/team/paid-or-free
devsvc.py all             ──► certificates / devices / App IDs / profiles listing (read-only)
devsvc.py add-device      ──► register the phone UDID
openssl generate key+CSR ─► devsvc.py create-cert ─► assemble p12
devsvc.py create-appid ─► create-profile      ─► *.mobileprovision
```

## 1. Login with gsa.py
```sh
export APPLE_ID=… APPLE_PASSWORD=…          # set these on the Minis environment-variable page; don't paste them into chat
cd scripts && python3 gsa.py                # the first run asks for a verification code
python3 gsa.py --reuse                      # reuse the saved session, no new SMS
```
The verification code handshake is interactive: the script waits in the background for `~/.ios-signer/code.txt`, and the appearance of `~/.ios-signer/need_code` means it is waiting for a code. Write the 6-digit code you receive with `printf '%s' 123456 > ~/.ios-signer/code.txt`. **The code expires quickly — write it the moment you get it.**

### Login pitfalls we have already hit (all handled in the scripts; read this before modifying them)
1. **Anisette**: uses a public V3 server (SideStore's list, WebSocket + three-step HTTP provisioning). Occasional 502s/timeouts → retries added. **A missing `User-Agent` yields 401**, so use the one the server returns.
2. **Certificate chain**: the root for `gsa.apple.com` is not in the system trust store, so `AppleRoot.pem` must be trusted explicitly.
3. **`-80045` (network-wide since 2026-10-12)**: GSA's `init/complete` `X-MMe-Client-Info` must be `<PC> <Windows;6.2(0,0);9200> <com.apple.AuthKit/1 (com.apple.akd/1.0)>`; **the 2FA endpoints `/auth/verify/*` and `validate` must use the Mac value** (the Windows value yields 403). Source: Dadoum/anisette-v3-server#61.
4. **The SRP username must be lowercase**; the server's spd is sometimes a **bare `<dict>` (no plist header)**, so add the header before parsing.
5. **2FA must be routed by channel** (matching xtool's `GrandSlamTwoFactorAuthenticateOperation`):
   - Login response `url == secondaryAuth` → **SMS**: `POST /auth/verify/phone/put?mode=sms` to send the code, `POST /auth/verify/phone/securitycode?referrer=/auth/verify/phone/put` to verify (body `securityCode.code` + `serverInfo{mode:sms, phoneNumber.id:"1"}`)
   - `trustedDeviceSecondaryAuth` → trusted-device push, verified with `validateCode` (header `security-code`)
   - `None` → Apple already sent a code automatically, use `validateCode`
   - **Root cause of the earlier run of 409s / `-21669 incorrect verification code`**: the SMS code was being sent to `validateCode`. The code was correct and unexpired — only the endpoint was wrong.
6. A failed `validate` is **HTTP 200 with an `ec` in the plist body**, so you must parse the body to know it failed.
7. **After verification the device identity becomes trusted**: subsequent logins usually no longer need an SMS.
8. **Rate limiting**: repeated attempts yield `-22421`. Run one complete pass at a time; on failure read the cause first instead of firing again.
9. Fetching the Xcode token: decrypt the `apptokens` `et` with the session `sk` using AES-GCM (aad=et[:3], iv=et[3:19], tag=et[-16:]); the plaintext may be a bare dict, so parse leniently.

## 2. Developer services with devsvc.py
Protocol (from reading xtool's source):
- Legacy endpoints (plist): `POST https://developerservices2.apple.com/services/QH65B2/<action>.action?clientId=XABBG36SBA`, actions `viewDeveloper`, `listTeams`.
- New endpoints (JSON:API, same paths as ASC): base `https://developerservices2.apple.com/services`, paths `/v1/certificates|devices|bundleIds|profiles`.
- Auth headers: `X-Apple-I-Identity-Id=<adsid>`, `X-Apple-GS-Token=<token>`, `X-Apple-App-Info=com.apple.gs.xcode.auth`, `User-Agent: Xcode`, `X-Xcode-Version: 26.5 (17F42)`, `X-MMe-Client-Info`, `Accept-Encoding: gzip`, plus the Anisette headers.
- **GET/DELETE must be wrapped as POST**: put the real method in `X-HTTP-Method-Override` and the query parameters in the JSON body as `{"urlEncodedQueryParams":"…"}`, with `teamId`; for POST/PATCH inject `teamId` into `data.attributes`.
- **Responses are gzip**, and urllib does not decompress automatically, so handle it yourself (otherwise you get an invalid plist error).
- Follow pagination via `links.next`'s `cursor/limit`; `filter[identifier]` is a **prefix match**, so compare exactly after fetching.
- Free or paid: check whether `listTeams`' memberships contain the iOS "Apple Developer Program"; free accounts show `Xcode Free Provisioning Program`.

**Write allowlist**: `devsvc.py`'s `WRITE_ALLOWED` only permits `POST /v1/devices|certificates|bundleIds|profiles` and **contains no DELETE/PATCH** — revoking a certificate must be implemented separately and confirmed by the user for each certificate. Every write command only previews without `--yes`.

```sh
python3 devsvc.py whoami
python3 devsvc.py all                                   # all read-only listings
python3 devsvc.py add-device <team> "<name>" <UDID> [--yes]
python3 devsvc.py create-cert <team> ~/.ios-signer/keys/dev.csr ~/.ios-signer/keys/dev.cer.der [--yes]
python3 devsvc.py create-appid <team> <bundleId> "<display name>" [--yes]
python3 devsvc.py create-profile <team> <appIdId> <certId> ~/.ios-signer/keys/dev.mobileprovision [--yes]
```

## 3. Generating a certificate (the private key never leaves the device)
```sh
umask 077; mkdir -p ~/.ios-signer/keys; cd ~/.ios-signer/keys
openssl genrsa -out dev.key 2048                                   # Apple development certificates require RSA2048
openssl req -new -sha1 -key dev.key -subj "/C=US/CN=minis-ios-signer" -out dev.csr
python3 …/devsvc.py create-cert <team> dev.csr dev.cer.der --yes   # returns the DER certificate (certificateType=DEVELOPMENT)
openssl x509 -inform DER -in dev.cer.der -out dev.cer.pem
openssl rand -hex 16 > p12.pass && chmod 600 p12.pass
openssl pkcs12 -export -legacy -inkey dev.key -in dev.cer.pem -name "Minis Dev" -out dev.p12 -passout file:p12.pass
```
- **The p12 must be created with `-legacy`**: `rcodesign 0.29` cannot read OpenSSL 3's default format (AES-256/PBKDF2), and it **reports `incorrect password`** even though the password is correct.
- To check that the certificate matches the private key: the MD5 of `openssl x509 -modulus` and `openssl rsa -modulus` must be identical.
- **Creating a new certificate does not require revoking the old one** (in this test, a free account with 2 existing certificates still issued a 3rd). **Revocation is irreversible and invalidates other devices signed with that certificate — only do it after the user confirms each one.**
- A certificate's private key only exists on the machine that generated it; Apple does not store it. Certificates left behind by other tools on the account (SideStore, etc.) have private keys you don't hold, so they can't be used for signing.

## 4. App IDs and profiles
- **App IDs on free accounts are globally unique**: mimic xtool by prefixing `XTL-<team ID>.` (for example `XTL-<team ID>.com.example.hello`; the team ID is in the `devsvc.py whoami` output). Use that full string as the project's `bundle_id`.
- Profile binding: `IOS_APP_DEVELOPMENT` + a specific certificate + all ENABLED iOS devices. Pick the certificate **whose private key you hold**.
- **Free accounts: certificates last about a year, but profiles only 7 days**, so regenerate before expiry (see renewal in signing.md). **The same App ID can be reused — switching apps does not require a new App ID**, only that `project.yaml`'s `bundle_id` matches the profile.
- Old App IDs on the account (e.g. SideStore's) may be reclaimed automatically by the server (in practice they were gone after we created new App IDs — not deleted by us), so don't rely on them existing.

## 5. Making sure "the object is the right one"
An `asc` API Key belongs to some team, while the `APPLE_ID` environment variable may be **a different account**. Before acting (especially before revoking), check the team ID with both `devsvc.py whoami` and `asc` to confirm you have not mixed them up.

## Apple Root CA (scripts/AppleRoot.pem)
The certificate chain for `gsa.apple.com` is issued by Apple Root CA, and that root is not necessarily in iSH's trust store, so the scripts ship it explicitly.
- Subject: `C=US, O=Apple Inc., OU=Apple Certification Authority, CN=Apple Root CA`
- SHA-256 fingerprint: `B0:B1:73:0E:CB:C7:FF:45:05:14:2C:49:F1:29:5E:6E:DA:6B:CA:ED:7E:2C:68:C5:BE:91:B5:A1:10:01:F0:24`
- To verify yourself: `openssl x509 -in scripts/AppleRoot.pem -noout -fingerprint -sha256`, and compare it against the Apple Root CA fingerprint published at <https://www.apple.com/certificateauthority/> — if they differ, don't use it.
